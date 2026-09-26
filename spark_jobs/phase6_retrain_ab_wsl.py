"""Full-data, class-weighted Phase 6 recovery training for Tasks A and B.

Run one task at a time from the WSL tmux launcher.  Validation selects the
depth (and, for Task B, probability threshold); test remains untouched until
the selected model is evaluated.
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from pyspark import StorageLevel
from pyspark.ml import Pipeline
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.feature import Imputer, StringIndexer, VectorAssembler
from pyspark.ml.functions import vector_to_array
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from spark_jobs.common import PROJECT_ROOT, get_logger, get_spark, hdfs_uri


BASE_NUMERIC = [
    "hour", "day_of_week", "weekend_indicator", "peak_hour_indicator_asof",
    "historical_delay_average", "n_stops", "distance_km", "travel_time_min",
    "demand_wow_growth",
]
SAFE_EXTRA_NUMERIC = [
    "planned_runtime_min", "headway_min", "headway_minutes",
    "historical_demand_average", "peak_hour_share_asof", "demand_mom_growth",
]


def scored(pred, labels):
    """Return accuracy, Spark weighted-F1, true macro-F1, per-class F1, matrix."""
    grouped = pred.groupBy("label", "prediction").count().collect()
    matrix = {(int(r["label"]), int(r["prediction"])): int(r["count"]) for r in grouped}
    total = sum(matrix.values())
    correct = sum(v for (actual, predicted), v in matrix.items() if actual == predicted)
    per_class = {}
    for idx, name in enumerate(labels):
        tp = matrix.get((idx, idx), 0)
        fp = sum(v for (actual, predicted), v in matrix.items() if actual != idx and predicted == idx)
        fn = sum(v for (actual, predicted), v in matrix.items() if actual == idx and predicted != idx)
        denom = 2 * tp + fp + fn
        per_class[name] = round(0.0 if not denom else 2 * tp / denom, 6)
    weighted = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName="f1").evaluate(pred)
    rows = [{"actual": labels[a], "predicted": labels[p], "count": n} for (a, p), n in sorted(matrix.items())]
    return {
        "accuracy": round(correct / total, 6),
        "weighted_f1": round(weighted, 6),
        "macro_f1": round(sum(per_class.values()) / len(per_class), 6),
        "per_class_f1": per_class,
        "confusion_matrix_long": rows,
        "rows": total,
    }


def with_threshold(pred, threshold):
    return pred.withColumn("prediction", F.when(vector_to_array("probability")[1] >= threshold, F.lit(1.0)).otherwise(F.lit(0.0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=("a", "b"), required=True)
    ap.add_argument("--trees", type=int, default=80)
    ap.add_argument("--depths", default="6,8")
    ap.add_argument("--enhanced", action="store_true", help="Use scheduled fields and strictly-prior route/time history only.")
    ap.add_argument("--weight-power", type=float, default=1.0, help="Exponent on inverse-frequency class weights; 1.0 is balanced, .5 is square-root balancing.")
    ap.add_argument("--run-name", default=None, help="Separate model/metric suffix, e.g. enhanced_v3_sqrt_weights.")
    args = ap.parse_args()
    depths = [int(x) for x in args.depths.split(",")]
    log, _ = get_logger(f"phase6_task{args.task.upper()}_full_rf")
    spark = get_spark(f"phase6-task{args.task}-full-rf")
    spark.sparkContext.setLogLevel("WARN")

    trip = spark.read.parquet(hdfs_uri("full", "features", "trip_features"))
    route = spark.read.parquet(hdfs_uri("full", "features", "route_features")).select("route_id", "n_stops")
    base = (trip.join(route, "route_id", "left")
            .withColumn("weekend_indicator", F.col("weekend_indicator").cast("double"))
            .withColumn("peak_hour_indicator_asof", F.col("peak_hour_indicator_asof").cast("double")))

    if args.task == "a":
        task, target, numeric = "delay_severity", "delay_severity", BASE_NUMERIC + ["occupancy_pct"]
        work = base.filter(F.col(target).isNotNull())
        if args.enhanced:
            prior = Window.partitionBy("route_id", "direction", "hour").orderBy("scheduled_departure", "trip_id").rowsBetween(-56, -1)
            work = work.withColumn("prior_route_hour_delay_mean", F.avg("delay_minutes").over(prior))
            numeric += SAFE_EXTRA_NUMERIC + ["prior_route_hour_delay_mean"]
        index_label = True
    else:
        task, target = "crowding_flag", "crowding_flag"
        # Strictly prior features; the contemporaneous occupancy value is excluded.
        w = Window.partitionBy("route_id").orderBy("scheduled_departure", "trip_id")
        work = (base.filter(F.col(target).isNotNull())
                .withColumn("rolling_28_mean_occupancy", F.avg("occupancy_pct").over(w.rowsBetween(-28, -1)))
                .withColumn("lag_7_occupancy", F.lag("occupancy_pct", 7).over(w))
                .withColumn("label", F.col(target).cast("double")))
        numeric = BASE_NUMERIC + ["rolling_28_mean_occupancy", "lag_7_occupancy"]
        if args.enhanced:
            prior = Window.partitionBy("route_id", "direction", "hour").orderBy("scheduled_departure", "trip_id").rowsBetween(-56, -1)
            work = work.withColumn("prior_route_hour_crowding_rate", F.avg(F.col("crowding_flag").cast("double")).over(prior))
            numeric += SAFE_EXTRA_NUMERIC + ["prior_route_hour_crowding_rate"]
        index_label = False

    raw = {s: work.filter(F.col("split") == s) for s in ("train", "validation", "test")}
    dates = {s: [str(r["lo"]), str(r["hi"])] for s, r in ((s, raw[s].agg(F.min("service_date").alias("lo"), F.max("service_date").alias("hi")).first()) for s in raw)}
    stages = []
    if index_label:
        stages.append(StringIndexer(inputCol=target, outputCol="label", handleInvalid="error"))
    categorical = ["route_id", "vehicle_id"] + (["direction", "route_type"] if args.enhanced else [])
    stages += [
        Imputer(inputCols=numeric, outputCols=[f"{c}_imputed" for c in numeric], strategy="median"),
    ]
    encoded = []
    for column in categorical:
        output_col = f"{column}_encoded"
        stages.append(StringIndexer(inputCol=column, outputCol=output_col, handleInvalid="keep"))
        encoded.append(output_col)
    stages.append(VectorAssembler(inputCols=[f"{c}_imputed" for c in numeric] + encoded, outputCol="features"))
    prep = Pipeline(stages=stages).fit(raw["train"])
    if index_label:
        labels = prep.stages[0].labels
    else:
        labels = ["False", "True"]

    def transform(frame):
        return prep.transform(frame).select("trip_id", "route_id", "service_date", target, "label", "features")

    # Full transformed trip data cannot safely fit in the 8 GB WSL JVM heap.
    # Disk-backed persistence avoids recomputation without competing for heap with RF trees.
    train = transform(raw["train"]).persist(StorageLevel.DISK_ONLY)
    validation = transform(raw["validation"]).persist(StorageLevel.DISK_ONLY)
    test = transform(raw["test"])
    counts = {int(r["label"]): int(r["count"]) for r in train.groupBy("label").count().collect()}
    n_classes, total = len(labels), sum(counts.values())
    weights = {str(i): round((total / (n_classes * count)) ** args.weight_power, 8) for i, count in counts.items()}
    weight_pairs = [item for k, v in weights.items() for item in (F.lit(int(k)), F.lit(v))]
    train = train.withColumn("weight", F.create_map(*weight_pairs)[F.col("label").cast("int")]).persist(StorageLevel.DISK_ONLY)
    log.info("TASK_%s full train=%s validation=%s test=%s class_counts=%s weights=%s", args.task.upper(), train.count(), validation.count(), test.count(), counts, weights)

    trials, best = [], None
    thresholds = [0.20, 0.30, 0.40, 0.50] if args.task == "b" else [None]
    for depth in depths:
        model = RandomForestClassifier(seed=42, numTrees=args.trees, maxDepth=depth, maxBins=1024, weightCol="weight").fit(train)
        raw_val = model.transform(validation)
        choices = []
        for threshold in thresholds:
            value = scored(with_threshold(raw_val, threshold) if threshold is not None else raw_val, labels)
            choices.append({"threshold": threshold, "metrics": value})
        choice = max(choices, key=lambda x: x["metrics"]["macro_f1"])
        trial = {"params": {"numTrees": args.trees, "maxDepth": depth}, "threshold": choice["threshold"], "validation": choice["metrics"], "threshold_trials": choices}
        trials.append(trial)
        log.info("TASK_%s trial=%s", args.task.upper(), json.dumps(trial))
        if best is None or trial["validation"]["macro_f1"] > best[0]["validation"]["macro_f1"]:
            best = (trial, model)

    selected, model = best
    threshold = selected["threshold"]
    def apply(frame):
        p = model.transform(frame)
        return with_threshold(p, threshold) if threshold is not None else p
    version = args.run_name or ("enhanced_v2" if args.enhanced else "v1")
    output = PROJECT_ROOT / "models" / "spark" / task / f"random_forest_full_weighted_{version}"
    output.mkdir(parents=True, exist_ok=True)
    prep.write().overwrite().save(str(output / "preprocessing"))
    model.write().overwrite().save(str(output / "classifier"))
    result = {
        "task": task, "algorithm": "random_forest_full_weighted", "model_scope": "full chronological training split; validation-only selection; untouched test split",
        "feature_set": "enhanced_safe_prior_history" if args.enhanced else "baseline_safe_features",
        "numeric_features": numeric, "categorical_features": categorical,
        "selected_params": selected["params"], "threshold": threshold, "class_counts_train": counts, "class_weights": weights, "weight_power": args.weight_power,
        "validation_trials": trials, "metrics": {"train": scored(apply(train), labels), "validation": selected["validation"], "test": scored(apply(test), labels)},
        "labels": labels, "split_dates": dates,
        "macro_f1_definition": "unweighted mean of the separately calculated per-class F1 scores; Spark evaluator f1 is reported separately as weighted_f1.",
        "date": datetime.now(timezone.utc).date().isoformat(),
    }
    suffix = f"_{version}" if version != "v1" else ""
    metrics = PROJECT_ROOT / "models" / "spark" / "metrics" / f"{task}_random_forest_full_weighted{suffix}.json"
    metrics.write_text(json.dumps(result, indent=2), encoding="utf-8")
    pred = apply(test).select("trip_id", "route_id", "service_date", target, "prediction").orderBy("service_date", "route_id").limit(20).collect()
    sample = PROJECT_ROOT / "reports" / "spark_sample_predictions" / f"{task}_random_forest_full_weighted{suffix}.csv"
    with sample.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f); writer.writerow(["trip_id", "route_id", "service_date", target, "prediction"])
        writer.writerows([[r[c] for c in ("trip_id", "route_id", "service_date", target, "prediction")] for r in pred])
    log.info("TASK_%s COMPLETE test=%s metrics=%s", args.task.upper(), result["metrics"]["test"], metrics)
    spark.stop()


if __name__ == "__main__":
    main()
