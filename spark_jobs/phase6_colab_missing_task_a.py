"""Fast, documented Colab completion for the missing Phase 6 Task A tree models.

It uses a stratified sample for model selection/training so that a CPU-only Spark
GBT One-vs-Rest run is practical in Colab.  Test rows are never used for fitting
or selection; metrics use a true (unweighted) macro F1 calculation.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from pyspark import StorageLevel
from pyspark.ml import Pipeline
from pyspark.ml.classification import DecisionTreeClassifier, GBTClassifier, OneVsRest
from pyspark.ml.feature import Imputer, StringIndexer, VectorAssembler
from pyspark.mllib.evaluation import MulticlassMetrics
from pyspark.sql import SparkSession, functions as F


NUMERIC = [
    "hour", "day_of_week", "weekend_indicator", "peak_hour_indicator_asof",
    "historical_delay_average", "occupancy_pct", "n_stops", "distance_km",
    "travel_time_min", "demand_wow_growth",
]
CATEGORICAL = ["route_id", "vehicle_id"]


def score(pred):
    pairs = pred.select("prediction", "label").rdd.map(lambda r: (float(r[0]), float(r[1])))
    metrics = MulticlassMetrics(pairs)
    labels = sorted(float(r[0]) for r in pred.select("label").distinct().collect())
    return {
        "accuracy": round(pred.filter(F.col("prediction") == F.col("label")).count() / pred.count(), 6),
        "macro_f1": round(sum(metrics.fMeasure(label, 1.0) for label in labels) / len(labels), 6),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", default="/content/colab_export/features")
    parser.add_argument("--output", required=True)
    parser.add_argument("--fraction", type=float, default=0.10)
    args = parser.parse_args()

    out = Path(args.output)
    metrics_dir = out / "models" / "spark" / "metrics"
    sample_dir = out / "reports" / "spark_sample_predictions"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)

    spark = (SparkSession.builder.master("local[*]").appName("UrbanTransitIQ-Missing-TaskA")
             .config("spark.driver.memory", "12g").config("spark.sql.shuffle.partitions", "16").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    trip = spark.read.parquet(f"{args.features}/trip_features")
    route = spark.read.parquet(f"{args.features}/route_features").select("route_id", "n_stops")
    df = (trip.join(route, "route_id", "left").filter(F.col("delay_severity").isNotNull())
          .withColumn("weekend_indicator", F.col("weekend_indicator").cast("double"))
          .withColumn("peak_hour_indicator_asof", F.col("peak_hour_indicator_asof").cast("double")))
    frames = {s: df.filter(F.col("split") == s) for s in ("train", "validation", "test")}
    dates = {s: [str(r["lo"]), str(r["hi"])] for s, r in
             ((s, frames[s].agg(F.min("service_date").alias("lo"), F.max("service_date").alias("hi")).first())
             for s in frames)}
    assert dates["train"][1] < dates["validation"][0] < dates["test"][0], dates
    labels = [r[0] for r in frames["train"].select("delay_severity").distinct().collect()]
    fractions = {label: args.fraction for label in labels}
    train_sample = frames["train"].sampleBy("delay_severity", fractions, seed=42)
    val_sample = frames["validation"].sampleBy("delay_severity", fractions, seed=42)

    stages = [StringIndexer(inputCol="delay_severity", outputCol="label", handleInvalid="error"),
              Imputer(inputCols=NUMERIC, outputCols=[f"{c}_imputed" for c in NUMERIC], strategy="median"),
              StringIndexer(inputCol="route_id", outputCol="route_encoded", handleInvalid="keep"),
              StringIndexer(inputCol="vehicle_id", outputCol="vehicle_encoded", handleInvalid="keep"),
              VectorAssembler(inputCols=[f"{c}_imputed" for c in NUMERIC] + ["route_encoded", "vehicle_encoded"],
                              outputCol="features", handleInvalid="error")]
    prep = Pipeline(stages=stages).fit(train_sample)
    train = prep.transform(train_sample).select("trip_id", "route_id", "service_date", "delay_severity", "label", "features").persist(StorageLevel.MEMORY_AND_DISK)
    validation = prep.transform(val_sample).select("trip_id", "route_id", "service_date", "delay_severity", "label", "features").persist(StorageLevel.MEMORY_AND_DISK)
    test = prep.transform(frames["test"]).select("trip_id", "route_id", "service_date", "delay_severity", "label", "features").persist(StorageLevel.MEMORY_AND_DISK)
    row_counts = {"train_sample": train.count(), "validation_sample": validation.count(), "test_full": test.count()}
    print("LEAKAGE CHECK", json.dumps(dates), "ROWS", row_counts, flush=True)

    algorithms = {
        "gbt_one_vs_rest": [
            ({"maxIter": 30, "maxDepth": 5}, OneVsRest(classifier=GBTClassifier(seed=42, maxBins=1024, maxIter=30, maxDepth=5))),
            ({"maxIter": 50, "maxDepth": 6}, OneVsRest(classifier=GBTClassifier(seed=42, maxBins=1024, maxIter=50, maxDepth=6))),
        ],
        "decision_tree": [
            ({"maxDepth": 6}, DecisionTreeClassifier(seed=42, maxBins=1024, maxDepth=6)),
            ({"maxDepth": 10}, DecisionTreeClassifier(seed=42, maxBins=1024, maxDepth=10)),
        ],
    }
    for name, candidates in algorithms.items():
        trials, best = [], None
        for params, estimator in candidates:
            model = estimator.fit(train)
            validation_score = score(model.transform(validation))
            trial = {"params": params, "validation": validation_score}
            trials.append(trial)
            print(name, "trial", json.dumps(trial), flush=True)
            if best is None or validation_score["macro_f1"] > best[0]["validation"]["macro_f1"]:
                best = (trial, model)
        chosen, model = best
        test_pred = model.transform(test).cache()
        test_score = score(test_pred)
        model_path = out / "models" / "spark" / "delay_severity" / f"{name}_sample_v1"
        prep_path = model_path / "preprocessing"
        prep.write().overwrite().save(str(prep_path))
        model.write().overwrite().save(str(model_path / "classifier"))
        prediction = test_pred.select("trip_id", "route_id", "service_date", "delay_severity", "prediction").orderBy("service_date", "route_id").limit(20).toPandas()
        prediction.to_csv(sample_dir / f"delay_severity_{name}_sample.csv", index=False)
        record = {
            "task": "delay_severity", "algorithm": name, "model_scope": "stratified 10% train/validation sample; full held-out test",
            "training_fraction": args.fraction, "selected_params": chosen["params"], "validation_trials": trials,
            "metrics": {"validation_sample": chosen["validation"], "test_full": test_score},
            "rows": row_counts, "split_dates": dates,
            "macro_f1_definition": "unweighted mean of per-class F1 scores", "date": datetime.now(timezone.utc).date().isoformat(),
        }
        (metrics_dir / f"delay_severity_{name}_sample.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        print("SAVED", name, json.dumps(record, indent=2), flush=True)
        test_pred.unpersist()
    train.unpersist(); validation.unpersist(); test.unpersist(); spark.stop()


if __name__ == "__main__":
    main()
