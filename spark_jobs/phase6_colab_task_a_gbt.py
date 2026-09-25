"""Standalone Colab resume for Phase 6 Task A GBT only.

Run after feature Parquet has been copied to /content/features. It intentionally does
not run Logistic Regression or Random Forest, and never reads the test split while
choosing GBT hyperparameters.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from pyspark.ml import Pipeline
from pyspark.ml.classification import GBTClassifier, OneVsRest
from pyspark.ml.feature import Imputer, StringIndexer, VectorAssembler
from pyspark.mllib.evaluation import MulticlassMetrics
from pyspark.sql import SparkSession, functions as F


def macro_f1(pred):
    pairs = pred.select("prediction", "label").rdd.map(lambda r: (float(r[0]), float(r[1])))
    metrics = MulticlassMetrics(pairs)
    labels = sorted(float(x) for x in pred.select("label").distinct().rdd.map(lambda r: r[0]).collect())
    return sum(metrics.fMeasure(label, 1.0) for label in labels) / len(labels)


def scores(pred):
    return {
        "accuracy": round(pred.filter(F.col("prediction") == F.col("label")).count() / pred.count(), 6),
        "macro_f1": round(macro_f1(pred), 6),
    }


def pipeline(max_iter, max_depth):
    numeric = ["hour", "day_of_week", "weekend_indicator", "peak_hour_indicator_asof",
               "historical_delay_average", "occupancy_pct", "n_stops", "distance_km",
               "travel_time_min", "demand_wow_growth"]
    stages = [
        StringIndexer(inputCol="delay_severity", outputCol="label", handleInvalid="error"),
        Imputer(inputCols=numeric, outputCols=[f"{c}_imputed" for c in numeric], strategy="median"),
        StringIndexer(inputCol="route_id", outputCol="route_id_encoded", handleInvalid="keep"),
        StringIndexer(inputCol="vehicle_id", outputCol="vehicle_id_encoded", handleInvalid="keep"),
        VectorAssembler(inputCols=[f"{c}_imputed" for c in numeric] + ["route_id_encoded", "vehicle_id_encoded"],
                        outputCol="features", handleInvalid="error"),
        # maxBins covers the 763 encoded vehicle IDs.
        OneVsRest(classifier=GBTClassifier(maxIter=max_iter, maxDepth=max_depth, maxBins=1024,
                                           seed=42, featuresCol="features", labelCol="label"),
                   featuresCol="features", labelCol="label", predictionCol="prediction"),
    ]
    return Pipeline(stages=stages)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default="/content/features")
    ap.add_argument("--output", required=True, help="Google Drive output root")
    args = ap.parse_args()
    out = Path(args.output)
    (out / "models" / "spark" / "metrics").mkdir(parents=True, exist_ok=True)
    (out / "reports" / "spark_sample_predictions").mkdir(parents=True, exist_ok=True)
    spark = SparkSession.builder.getOrCreate()
    df = spark.read.parquet(f"{args.features}/trip_features")
    route = spark.read.parquet(f"{args.features}/route_features").select("route_id", "n_stops")
    df = (df.join(route, "route_id", "left")
            .filter(F.col("delay_severity").isNotNull())
            .withColumn("weekend_indicator", F.col("weekend_indicator").cast("double"))
            .withColumn("peak_hour_indicator_asof", F.col("peak_hour_indicator_asof").cast("double")))
    bounds = df.groupBy("split").agg(F.min("service_date").alias("min"), F.max("service_date").alias("max")).collect()
    dates = {r["split"]: {"min": str(r["min"]), "max": str(r["max"])} for r in bounds}
    assert dates["train"]["max"] < dates["validation"]["min"] < dates["test"]["min"], dates
    print("LEAKAGE CHECK", json.dumps(dates))
    train, val, test = (df.filter(F.col("split") == s) for s in ("train", "validation", "test"))
    trials = []
    # Validation-only selection. Test is not transformed until after one winner is selected.
    for max_iter in (30, 50, 80):
        for max_depth in (5, 6, 8):
            model = pipeline(max_iter, max_depth).fit(train)
            val_score = scores(model.transform(val))
            trials.append({"maxIter": max_iter, "maxDepth": max_depth, "validation": val_score})
            print("validation", trials[-1])
    best = max(trials, key=lambda x: x["validation"]["macro_f1"])
    final = pipeline(best["maxIter"], best["maxDepth"]).fit(train.unionByName(val))
    result = {
        "task": "delay_severity", "algorithm": "gbt_one_vs_rest", "date": datetime.now(timezone.utc).date().isoformat(),
        "selected_params": {"maxIter": best["maxIter"], "maxDepth": best["maxDepth"], "maxBins": 1024},
        "validation_trials": trials,
        "metrics": {"train": scores(final.transform(train)), "validation": scores(final.transform(val)), "test": scores(final.transform(test))},
        "split_dates": dates,
        "null_handling": "Median Imputer for numeric features; occupancy_pct and delay values were never zero-filled.",
    }
    metric = out / "models" / "spark" / "metrics" / "delay_severity_gbt_one_vs_rest.json"
    metric.write_text(json.dumps(result, indent=2), encoding="utf-8")
    final.write().overwrite().save(str(out / "models" / "spark" / "delay_severity" / "gbt_one_vs_rest_v1"))
    pred = final.transform(test).select("trip_id", "route_id", "service_date", "delay_severity", "prediction").orderBy("service_date", "route_id").limit(20)
    pred.toPandas().to_csv(out / "reports" / "spark_sample_predictions" / "delay_severity_gbt_one_vs_rest.csv", index=False)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
