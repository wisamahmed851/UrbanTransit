"""Phase 6 Colab Tasks C/D: demand forecasting, route clustering, and final report."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from pyspark.ml import Pipeline
from pyspark.ml.clustering import BisectingKMeans, GaussianMixture, KMeans
from pyspark.ml.evaluation import ClusteringEvaluator, RegressionEvaluator
from pyspark.ml.feature import Imputer, StandardScaler, StringIndexer, VectorAssembler
from pyspark.ml.regression import DecisionTreeRegressor, GBTRegressor, LinearRegression, RandomForestRegressor
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window


def regression_scores(pred):
    out = {}
    for metric in ("mae", "rmse", "r2"):
        out[metric] = round(RegressionEvaluator(labelCol="label", predictionCol="prediction", metricName=metric).evaluate(pred), 6)
    mape = pred.filter(F.col("label") != 0).select(F.avg(F.abs((F.col("label") - F.col("prediction")) / F.col("label"))).alias("mape")).first()["mape"]
    out["mape"] = None if mape is None else round(float(mape) * 100, 6)
    return out


def task_c(spark, features, out):
    metrics_dir, report_dir = out / "models" / "spark" / "metrics", out / "reports" / "spark_sample_predictions"
    demand = spark.read.parquet(f"{features}/route_daily_demand")
    window = Window.partitionBy("route_id").orderBy("service_date")
    data = (demand.withColumn("lag_1_demand", F.lag("estimated_daily_boardings", 1).over(window))
            .withColumn("lag_7_demand", F.lag("estimated_daily_boardings", 7).over(window))
            .withColumn("lag_28_demand", F.lag("estimated_daily_boardings", 28).over(window))
            .withColumn("rolling_7_mean", F.avg("estimated_daily_boardings").over(window.rowsBetween(-7, -1)))
            .withColumn("rolling_28_mean", F.avg("estimated_daily_boardings").over(window.rowsBetween(-28, -1)))
            .withColumn("month", F.month("service_date").cast("double"))
            .withColumn("day_of_week", F.col("day_of_week").cast("double"))
            .withColumn("weekend_indicator", F.col("weekend_indicator").cast("double"))
            .withColumn("label", F.col("estimated_daily_boardings").cast("double")))
    feats = ["lag_1_demand", "lag_7_demand", "lag_28_demand", "rolling_7_mean", "rolling_28_mean", "day_of_week", "weekend_indicator", "month"]
    frames = {s: data.filter(F.col("split") == s).select("route_id", "service_date", "split", "label", *feats) for s in ("train", "validation", "test")}
    dates = {s: [str(r["lo"]), str(r["hi"])] for s, r in ((s, frames[s].agg(F.min("service_date").alias("lo"), F.max("service_date").alias("hi")).first()) for s in frames)}
    assert dates["train"][1] < dates["validation"][0] < dates["test"][0], dates
    algorithms = {
        "linear_regression": [({"regParam": 0.0}, LinearRegression(regParam=0.0, maxIter=100)), ({"regParam": 0.1}, LinearRegression(regParam=0.1, maxIter=100))],
        "random_forest": [({"numTrees": 50, "maxDepth": 8}, RandomForestRegressor(seed=42, numTrees=50, maxDepth=8, maxBins=128)), ({"numTrees": 80, "maxDepth": 12}, RandomForestRegressor(seed=42, numTrees=80, maxDepth=12, maxBins=128))],
        "gbt": [({"maxIter": 40, "maxDepth": 5}, GBTRegressor(seed=42, maxIter=40, maxDepth=5, maxBins=128)), ({"maxIter": 70, "maxDepth": 7}, GBTRegressor(seed=42, maxIter=70, maxDepth=7, maxBins=128))],
        "decision_tree": [({"maxDepth": 6}, DecisionTreeRegressor(seed=42, maxDepth=6, maxBins=128)), ({"maxDepth": 10}, DecisionTreeRegressor(seed=42, maxDepth=10, maxBins=128))],
    }
    rows = {s: frames[s].count() for s in frames}
    print("TASK C LEAKAGE CHECK", json.dumps(dates), "ROWS", rows, flush=True)
    for name, candidates in algorithms.items():
        trials, best = [], None
        for params, estimator in candidates:
            pipe = Pipeline(stages=[Imputer(inputCols=feats, outputCols=[f"{c}_imputed" for c in feats], strategy="median"),
                                   StringIndexer(inputCol="route_id", outputCol="route_encoded", handleInvalid="keep"),
                                   VectorAssembler(inputCols=[f"{c}_imputed" for c in feats] + ["route_encoded"], outputCol="features"), estimator])
            fitted = pipe.fit(frames["train"])
            val_score = regression_scores(fitted.transform(frames["validation"]))
            trial = {"params": params, "validation": val_score}; trials.append(trial)
            print("daily_boardings", name, json.dumps(trial), flush=True)
            if best is None or val_score["rmse"] < best[0]["validation"]["rmse"]: best = (trial, params)
        params = best[1]
        estimator = next(est for candidate_params, est in candidates if candidate_params == params)
        pipe = Pipeline(stages=[Imputer(inputCols=feats, outputCols=[f"{c}_imputed" for c in feats], strategy="median"),
                               StringIndexer(inputCol="route_id", outputCol="route_encoded", handleInvalid="keep"),
                               VectorAssembler(inputCols=[f"{c}_imputed" for c in feats] + ["route_encoded"], outputCol="features"), estimator])
        final = pipe.fit(frames["train"].unionByName(frames["validation"]))
        all_scores = {s: regression_scores(final.transform(frames[s])) for s in frames}
        model_dir = out / "models" / "spark" / "daily_boardings" / f"{name}_v1"; final.write().overwrite().save(str(model_dir))
        final.transform(frames["test"]).select("route_id", "service_date", "label", "prediction").orderBy("service_date", "route_id").limit(20).toPandas().to_csv(report_dir / f"daily_boardings_{name}.csv", index=False)
        record = {"task": "daily_boardings", "algorithm": name, "selected_params": params, "validation_trials": trials,
                  "metrics": all_scores, "rows": rows, "split_dates": dates, "feature_rule": "All lag/rolling demand features end at the prior row; test was untouched until final evaluation.", "date": datetime.now(timezone.utc).date().isoformat()}
        (metrics_dir / f"daily_boardings_{name}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        print("SAVED", name, json.dumps(record, indent=2), flush=True)


def task_d(spark, features, out):
    metrics_dir, reports = out / "models" / "spark" / "metrics", out / "reports"
    route = spark.read.parquet(f"{features}/route_features")
    feats = ["route_load_factor", "route_reliability_delay_min", "trip_punctuality_rate", "avg_trip_boardings", "avg_daily_boardings", "crowding_rate", "bunching_rate", "arrival_delay_std_min"]
    data = route.filter(F.col("in_train_period")).dropna(subset=feats)
    raw = VectorAssembler(inputCols=feats, outputCol="raw_features").transform(data)
    scaled = Pipeline(stages=[StandardScaler(inputCol="raw_features", outputCol="features", withMean=True, withStd=True)]).fit(raw).transform(raw)
    evaluator = ClusteringEvaluator(featuresCol="features", predictionCol="prediction", metricName="silhouette")
    candidates = []
    for name, klass in (("kmeans", KMeans), ("bisecting_kmeans", BisectingKMeans), ("gaussian_mixture", GaussianMixture)):
        for k in (3, 4, 5):
            model = klass(k=k, seed=42, featuresCol="features", predictionCol="prediction").fit(scaled)
            pred = model.transform(scaled)
            actual_k = pred.select("prediction").distinct().count()
            if actual_k < 2:
                record = {"task": "route_clustering", "algorithm": name, "k": k, "status": "skipped_degenerate_solution", "actual_clusters": actual_k, "date": datetime.now(timezone.utc).date().isoformat()}
                (metrics_dir / f"route_clustering_{name}_k{k}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
                print("route_clustering SKIPPED", name, "k", k, "actual clusters", actual_k, flush=True)
                continue
            score = round(evaluator.evaluate(pred), 6)
            candidates.append((score, name, k, model, pred))
            (metrics_dir / f"route_clustering_{name}_k{k}.json").write_text(json.dumps({"task": "route_clustering", "algorithm": name, "k": k, "silhouette": score, "features": feats, "date": datetime.now(timezone.utc).date().isoformat()}, indent=2), encoding="utf-8")
            print("route_clustering", name, "k", k, "silhouette", score, flush=True)
    if not candidates: raise RuntimeError("No clustering candidate produced two or more clusters")
    score, name, k, model, pred = max(candidates, key=lambda x: x[0])
    model_dir = out / "models" / "spark" / "route_clustering" / f"{name}_k{k}_v1"; model.write().overwrite().save(str(model_dir))
    profiles = pred.groupBy("prediction").agg(*[F.avg(c).alias(c) for c in feats], F.count("*").alias("routes")).orderBy("prediction").toPandas()
    profiles["plain_language_label"] = ["High-demand reliable routes" if r.avg_daily_boardings >= profiles.avg_daily_boardings.median() and r.trip_punctuality_rate >= profiles.trip_punctuality_rate.median() else "Capacity or reliability needs review" for r in profiles.itertuples()]
    profiles.to_csv(reports / "phase6_cluster_profiles.csv", index=False)
    print("SAVED route_clustering", name, k, score, flush=True)


def final_report(out):
    metrics = []
    for path in sorted((out / "models" / "spark" / "metrics").glob("*.json")):
        try: metrics.append((path.name, json.loads(path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError: pass
    lines = ["# Phase 6 Completion Summary", "", "Generated from Colab output artifacts.", "", "| metric file | task | algorithm | test metric |", "|---|---|---|---|"]
    for name, item in metrics:
        test = item.get("metrics", {}).get("test_full") or item.get("metrics", {}).get("test") or "see file"
        lines.append(f"| {name} | {item.get('task', 'route_clustering')} | {item.get('algorithm', '')} | {test} |")
    lines += ["", "## Notes", "", "- Task A GBT and Decision Tree used a stratified 10% train/validation sample; their JSON files state this explicitly.", "- Task B excludes contemporaneous `occupancy_pct`, because it directly defines `crowding_flag`; it uses strictly prior rolling/lag occupancy features.", "- Task C uses strict-prior demand lag and rolling features. Task D clusters only train-period route profiles."]
    (out / "reports" / "phase6_completion_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--features", default="/content/colab_export/features"); ap.add_argument("--output", required=True); ap.add_argument("--task-d-only", action="store_true"); args = ap.parse_args()
    out = Path(args.output); (out / "reports").mkdir(parents=True, exist_ok=True); (out / "models" / "spark" / "metrics").mkdir(parents=True, exist_ok=True); (out / "reports" / "spark_sample_predictions").mkdir(parents=True, exist_ok=True)
    spark = (SparkSession.builder.master("local[*]").appName("UrbanTransitIQ-Phase6-CD").config("spark.driver.memory", "10g").config("spark.sql.shuffle.partitions", "16").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    if not args.task_d_only: task_c(spark, args.features, out)
    task_d(spark, args.features, out); spark.stop(); final_report(out)
    print("PHASE 6 TASKS C/D COMPLETE", flush=True)


if __name__ == "__main__": main()
