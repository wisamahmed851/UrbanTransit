"""Colab-only Phase 6 Task B: crowding classification without rerunning Task A.

Uses a stratified sample for fitting/tuning, chronological splits, positive-class
weights, true macro F1, and a full untouched test split.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from pyspark import StorageLevel
from pyspark.ml import Pipeline
from pyspark.ml.classification import GBTClassifier, LogisticRegression, RandomForestClassifier
from pyspark.ml.feature import Imputer, StringIndexer, VectorAssembler
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window


NUMERIC = ["hour", "day_of_week", "weekend_indicator", "peak_hour_indicator_asof",
           "historical_delay_average", "n_stops", "distance_km",
           "travel_time_min", "demand_wow_growth", "rolling_28_mean_occupancy", "lag_7_occupancy"]


def scores(pred):
    # One compact aggregation avoids caching the full prediction frame in driver memory.
    rows = pred.groupBy("label", "prediction").count().collect()
    labels = sorted({int(r["label"]) for r in rows})
    total = sum(r["count"] for r in rows)
    correct = sum(r["count"] for r in rows if int(r["label"]) == int(r["prediction"]))
    f1s = []
    for label in labels:
        tp = sum(r["count"] for r in rows if int(r["label"]) == label and int(r["prediction"]) == label)
        fp = sum(r["count"] for r in rows if int(r["label"]) != label and int(r["prediction"]) == label)
        fn = sum(r["count"] for r in rows if int(r["label"]) == label and int(r["prediction"]) != label)
        denom = 2 * tp + fp + fn
        f1s.append(0.0 if denom == 0 else 2 * tp / denom)
    return {"accuracy": round(correct / total, 6), "macro_f1": round(sum(f1s) / len(f1s), 6)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default="/content/colab_export/features")
    ap.add_argument("--output", required=True)
    ap.add_argument("--fraction", type=float, default=0.10)
    args = ap.parse_args()
    out = Path(args.output)
    metrics_dir = out / "models" / "spark" / "metrics"
    samples_dir = out / "reports" / "spark_sample_predictions"
    metrics_dir.mkdir(parents=True, exist_ok=True); samples_dir.mkdir(parents=True, exist_ok=True)

    spark = (SparkSession.builder.master("local[*]").appName("UrbanTransitIQ-TaskB")
             .config("spark.driver.memory", "12g").config("spark.sql.shuffle.partitions", "16").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    trip = spark.read.parquet(f"{args.features}/trip_features")
    route = spark.read.parquet(f"{args.features}/route_features").select("route_id", "n_stops")
    base = (trip.join(route, "route_id", "left").filter(F.col("crowding_flag").isNotNull())
            .withColumn("weekend_indicator", F.col("weekend_indicator").cast("double"))
            .withColumn("peak_hour_indicator_asof", F.col("peak_hour_indicator_asof").cast("double")))
    window = Window.partitionBy("route_id").orderBy("scheduled_departure", "trip_id")
    base = (base.withColumn("rolling_28_mean_occupancy", F.avg("occupancy_pct").over(window.rowsBetween(-28, -1)))
            .withColumn("lag_7_occupancy", F.lag("occupancy_pct", 7).over(window)))
    frames = {s: base.filter(F.col("split") == s) for s in ("train", "validation", "test")}
    dates = {s: [str(x["lo"]), str(x["hi"])] for s, x in ((s, frames[s].agg(F.min("service_date").alias("lo"), F.max("service_date").alias("hi")).first()) for s in frames)}
    assert dates["train"][1] < dates["validation"][0] < dates["test"][0], dates
    fractions = {bool(r[0]): args.fraction for r in frames["train"].select("crowding_flag").distinct().collect()}
    raw_train = frames["train"].sampleBy("crowding_flag", fractions, seed=42)
    raw_val = frames["validation"].sampleBy("crowding_flag", fractions, seed=42)
    prep = Pipeline(stages=[Imputer(inputCols=NUMERIC, outputCols=[f"{x}_imputed" for x in NUMERIC], strategy="median"),
                            StringIndexer(inputCol="route_id", outputCol="route_encoded", handleInvalid="keep"),
                            StringIndexer(inputCol="vehicle_id", outputCol="vehicle_encoded", handleInvalid="keep"),
                            VectorAssembler(inputCols=[f"{x}_imputed" for x in NUMERIC] + ["route_encoded", "vehicle_encoded"], outputCol="features", handleInvalid="error")]).fit(raw_train)

    def transform(data):
        return prep.transform(data).withColumn("label", F.col("crowding_flag").cast("double")).select("trip_id", "route_id", "service_date", "crowding_flag", "label", "features")
    train = transform(raw_train).persist(StorageLevel.MEMORY_AND_DISK)
    val = transform(raw_val).persist(StorageLevel.MEMORY_AND_DISK)
    # The full test split stays on disk/logical plan; it is never cached in JVM memory.
    test = transform(frames["test"])
    counts = {int(r["label"]): r["count"] for r in train.groupBy("label").count().collect()}
    if 0 not in counts or 1 not in counts: raise ValueError(f"Both classes required: {counts}")
    positive_weight = counts[0] / counts[1]
    train = train.withColumn("weight", F.when(F.col("label") == 1, F.lit(positive_weight)).otherwise(F.lit(1.0))).persist(StorageLevel.MEMORY_AND_DISK)
    row_counts = {"train_sample": train.count(), "validation_sample": val.count(), "test_full": test.count()}
    print("LEAKAGE CHECK occupancy_pct excluded", json.dumps(dates), "FEATURES", NUMERIC,
          "ROWS", row_counts, "POSITIVE_WEIGHT", positive_weight, flush=True)

    algorithms = {
        "logistic_regression": [({"regParam": .01}, LogisticRegression(maxIter=80, regParam=.01, weightCol="weight")),
                                ({"regParam": .1}, LogisticRegression(maxIter=80, regParam=.1, weightCol="weight"))],
        "random_forest": [({"numTrees": 50, "maxDepth": 8}, RandomForestClassifier(seed=42, numTrees=50, maxDepth=8, maxBins=1024, weightCol="weight")),
                          ({"numTrees": 100, "maxDepth": 10}, RandomForestClassifier(seed=42, numTrees=100, maxDepth=10, maxBins=1024, weightCol="weight"))],
        "gbt": [({"maxIter": 30, "maxDepth": 5}, GBTClassifier(seed=42, maxIter=30, maxDepth=5, maxBins=1024, weightCol="weight")),
                ({"maxIter": 50, "maxDepth": 6}, GBTClassifier(seed=42, maxIter=50, maxDepth=6, maxBins=1024, weightCol="weight"))],
    }
    for name, candidates in algorithms.items():
        trials, best = [], None
        for params, estimator in candidates:
            fitted = estimator.fit(train)
            value = scores(fitted.transform(val))
            trial = {"params": params, "validation": value}; trials.append(trial)
            print(name, "trial", json.dumps(trial), flush=True)
            if best is None or value["macro_f1"] > best[0]["validation"]["macro_f1"]: best = (trial, fitted)
        selected, model = best
        pred = model.transform(test); test_score = scores(pred)
        model_dir = out / "models" / "spark" / "crowding_flag" / f"{name}_sample_v1"
        prep.write().overwrite().save(str(model_dir / "preprocessing")); model.write().overwrite().save(str(model_dir / "classifier"))
        pred.select("trip_id", "route_id", "service_date", "crowding_flag", "prediction").orderBy("service_date", "route_id").limit(20).toPandas().to_csv(samples_dir / f"crowding_flag_{name}_sample.csv", index=False)
        record = {"task": "crowding_flag", "algorithm": name, "model_scope": "stratified 10% train/validation sample; full held-out test",
                  "training_fraction": args.fraction, "class_weight_positive": positive_weight, "selected_params": selected["params"],
                  "validation_trials": trials, "metrics": {"validation_sample": selected["validation"], "test_full": test_score},
                  "rows": row_counts, "split_dates": dates, "macro_f1_definition": "unweighted mean of per-class F1 scores", "date": datetime.now(timezone.utc).date().isoformat()}
        (metrics_dir / f"crowding_flag_{name}_sample.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        print("SAVED", name, json.dumps(record, indent=2), flush=True)
    spark.stop()


if __name__ == "__main__":
    main()
