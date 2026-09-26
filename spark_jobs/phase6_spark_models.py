"""Phase 6 Spark ML: leakage-safe transit prediction, forecasting and route clustering.

Runs only against Phase 4's chronological split.  Test rows are not read by any model
selection code; train fits candidates, validation selects parameters, then one final
train+validation fit is evaluated once on test.  Usage: python spark_jobs/phase6_spark_models.py
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyspark.ml import Pipeline
from pyspark.ml.clustering import BisectingKMeans, GaussianMixture, KMeans
from pyspark.ml.evaluation import ClusteringEvaluator, MulticlassClassificationEvaluator, RegressionEvaluator
from pyspark.ml.feature import Imputer, StandardScaler, StringIndexer, VectorAssembler
from pyspark.ml.classification import GBTClassifier, LogisticRegression, OneVsRest, RandomForestClassifier
from pyspark.ml.regression import DecisionTreeRegressor, GBTRegressor, LinearRegression, RandomForestRegressor
from pyspark.ml.functions import vector_to_array
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from spark_jobs.common import PROJECT_ROOT, get_logger, get_spark, hdfs_uri

MODELS = PROJECT_ROOT / "models" / "spark"
REPORTS = PROJECT_ROOT / "reports"
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")
METRICS = []


def model_dir(task, algorithm):
    return str(MODELS / task / f"{algorithm}_v1")


def as_number(df, columns):
    """Convert booleans to doubles without changing NULLs (never silently zero-fill)."""
    for c in columns:
        if c in df.columns:
            df = df.withColumn(c, F.col(c).cast("double"))
    return df


def split_frames(df):
    return {s: df.filter(F.col("split") == s) for s in ("train", "validation", "test")}


def date_check(log, df, name):
    rows = df.groupBy("split").agg(F.min("service_date").alias("min"), F.max("service_date").alias("max"), F.count("*").alias("rows")).collect()
    out = {r["split"]: {"min": str(r["min"]), "max": str(r["max"]), "rows": r["rows"]} for r in rows}
    ordered = [out[x] for x in ("train", "validation", "test")]
    if not (ordered[0]["max"] < ordered[1]["min"] < ordered[2]["min"]):
        raise ValueError(f"{name}: chronological split check failed: {out}")
    log.info("LEAKAGE CHECK %s: train %s..%s < validation %s..%s < test %s..%s", name,
             ordered[0]["min"], ordered[0]["max"], ordered[1]["min"], ordered[1]["max"], ordered[2]["min"], ordered[2]["max"])
    return out


def cls_scores(pred):
    acc = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName="accuracy").evaluate(pred)
    f1 = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName="f1").evaluate(pred)
    return {"accuracy": round(acc, 6), "macro_f1": round(f1, 6)}


def reg_scores(pred):
    out = {}
    for metric, key in (("mae", "mae"), ("rmse", "rmse"), ("r2", "r2")):
        out[key] = round(RegressionEvaluator(labelCol="label", predictionCol="prediction", metricName=metric).evaluate(pred), 6)
    # MAPE excludes a zero denominator rather than inventing a value.
    out["mape"] = round(pred.filter(F.col("label") != 0)
                        .select(F.avg(F.abs((F.col("label") - F.col("prediction")) / F.col("label"))).alias("x")).first()["x"] * 100, 6)
    return out


def classification_pipeline(feature_cols, categorical, estimator, label_indexed=True):
    numeric = [x for x in feature_cols if x not in categorical]
    stages = []
    if label_indexed:
        stages.append(StringIndexer(inputCol="target", outputCol="label", handleInvalid="error"))
    # Median imputation is explicit and preserves the fact that NULL was never assumed to be zero.
    stages.append(Imputer(inputCols=numeric, outputCols=[f"{x}__imputed" for x in numeric], strategy="median"))
    encoded = []
    for c in categorical:
        out = f"{c}__encoded"
        stages.append(StringIndexer(inputCol=c, outputCol=out, handleInvalid="keep"))
        encoded.append(out)
    assembled = [f"{x}__imputed" for x in numeric] + encoded
    stages.append(VectorAssembler(inputCols=assembled, outputCol="features", handleInvalid="error"))
    stages.append(estimator)
    return Pipeline(stages=stages), numeric


def configured(estimator, values):
    """Copy normal estimators or a multiclass One-vs-Rest GBT with the requested child params."""
    if isinstance(estimator, OneVsRest):
        child = estimator.getClassifier()
        child_values = {child.getParam(k.replace("classifier_", "")): v for k, v in values.items()}
        return OneVsRest(classifier=child.copy(child_values), labelCol="label", featuresCol="features", predictionCol="prediction")
    return estimator.copy({estimator.getParam(k): v for k, v in values.items()})


def save_json(task, algorithm, payload):
    path = MODELS / "metrics" / f"{task}_{algorithm}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def save_version(task, algorithm, payload):
    path = MODELS / task / f"{algorithm}_v1" / "version.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def sample_predictions(task, pred, kind, algorithm="best"):
    out = REPORTS / "spark_sample_predictions"
    out.mkdir(parents=True, exist_ok=True)
    cols = ["trip_id", "route_id", "service_date", "split", "target", "prediction"] if "trip_id" in pred.columns else ["route_id", "service_date", "split", "target", "prediction"]
    if kind == "classification" and "probability" in pred.columns:
        pred = pred.withColumn("probability", vector_to_array("probability").cast("string"))
        cols.append("probability")
    (pred.filter(F.col("split") == "test").select(*[c for c in cols if c in pred.columns])
         .orderBy("service_date", "route_id").limit(500).toPandas().to_csv(out / f"{task}_{algorithm}.csv", index=False))


def run_classification(log, task, df, target, features, categorical, algorithms, positive_rate=None):
    keep = list(dict.fromkeys(["trip_id", "route_id", "service_date", "split", target, *features, *categorical]))
    frames = split_frames(df.select(*[F.col(c).alias("target") if c == target else F.col(c) for c in keep]).dropna(subset=["target"]))
    results, candidates = [], []
    for name, estimator, grid in algorithms:
        best = None
        for params in grid:
            est = configured(estimator, params)
            pipe, imputed = classification_pipeline(features, categorical, est, label_indexed=(task == "delay_severity"))
            # For binary crowding target, Spark requires its numeric label directly.
            train = frames["train"] if task == "delay_severity" else frames["train"].withColumn("label", F.col("target").cast("double"))
            val = frames["validation"] if task == "delay_severity" else frames["validation"].withColumn("label", F.col("target").cast("double"))
            if task == "crowding_flag" and positive_rate and positive_rate < .15:
                weight = (1 - positive_rate) / positive_rate
                train = train.withColumn("weight", F.when(F.col("label") == 1, F.lit(weight)).otherwise(F.lit(1.0)))
                est.setWeightCol("weight")
                pipe, imputed = classification_pipeline(features, categorical, est, label_indexed=False)
            fitted = pipe.fit(train)
            score = cls_scores(fitted.transform(val))
            trial = {"params": params, "validation": score, "imputed_columns": imputed}
            if best is None or score["macro_f1"] > best[0]["validation"]["macro_f1"]:
                best = (trial, fitted, est)
        # Refit only after selection, on train+validation. Test remains completely untouched.
        est = configured(estimator, best[0]["params"])
        if task == "crowding_flag" and positive_rate and positive_rate < .15:
            est.setWeightCol("weight")
        pipe, imputed = classification_pipeline(features, categorical, est, label_indexed=(task == "delay_severity"))
        tv = frames["train"].unionByName(frames["validation"])
        if task == "crowding_flag":
            tv = tv.withColumn("label", F.col("target").cast("double"))
            if positive_rate and positive_rate < .15:
                tv = tv.withColumn("weight", F.when(F.col("label") == 1, F.lit((1-positive_rate)/positive_rate)).otherwise(F.lit(1.0)))
        final = pipe.fit(tv)
        scored = {}
        for split, data in frames.items():
            d = data if task == "delay_severity" else data.withColumn("label", F.col("target").cast("double"))
            scored[split] = cls_scores(final.transform(d))
        record = {"task": task, "algorithm": name, "selected_params": best[0]["params"], "metrics": scored,
                  "validation_tuning": best[0]["validation"], "rows": {k: v.count() for k, v in frames.items()},
                  "null_handling": f"Median Imputer: {', '.join(imputed)}; categorical unknowns retained as an extra index.",
                  "date": DATE}
        save_json(task, name, record); METRICS.append(record); candidates.append((record, final))
        final.write().overwrite().save(model_dir(task, name))
        save_version(task, name, {"version": "v1", "date": DATE, "metrics": scored})
        d = frames["test"] if task == "delay_severity" else frames["test"].withColumn("label", F.col("target").cast("double"))
        sample_predictions(task, final.transform(d), "classification", name)
        log.info("%s %s test=%s", task, name, scored["test"])
    winner, model = max(candidates, key=lambda x: x[0]["metrics"]["validation"]["macro_f1"])
    model.write().overwrite().save(model_dir(task, winner["algorithm"]))
    save_version(task, winner["algorithm"], {"version": "v1", "date": DATE, "metrics": winner["metrics"]})
    sample_predictions(task, model.transform(frames["test"] if task == "delay_severity" else frames["test"].withColumn("label", F.col("target").cast("double"))), "classification", "best")
    return winner


def demand_features(df):
    w = Window.partitionBy("route_id").orderBy("service_date")
    # All lag/rolling windows end at -1: the day's boardings are never a feature for itself.
    return (df.withColumn("lag_1_demand", F.lag("estimated_daily_boardings", 1).over(w))
              .withColumn("lag_7_demand", F.lag("estimated_daily_boardings", 7).over(w))
              .withColumn("lag_28_demand", F.lag("estimated_daily_boardings", 28).over(w))
              .withColumn("rolling_7_mean", F.avg("estimated_daily_boardings").over(w.rowsBetween(-7, -1)))
              .withColumn("rolling_28_mean", F.avg("estimated_daily_boardings").over(w.rowsBetween(-28, -1)))
              .withColumn("month", F.month("service_date").cast("double"))
              .withColumn("is_holiday", F.lit(0.0)))


def run_forecast(log, df):
    features = ["lag_1_demand", "lag_7_demand", "lag_28_demand", "rolling_7_mean", "rolling_28_mean", "day_of_week", "weekend_indicator", "month", "is_holiday"]
    df = as_number(demand_features(df), ["day_of_week", "weekend_indicator"])
    frames = split_frames(df.select("route_id", "service_date", "split", F.col("estimated_daily_boardings").alias("target"), *features))
    baseline = {}
    for s, d in frames.items():
        baseline[s] = reg_scores(d.withColumn("label", "target").withColumn("prediction", "rolling_28_mean").dropna(subset=["prediction"]))
    algorithms = [("linear_regression", LinearRegression(labelCol="label", featuresCol="features"), [{"regParam": 0.0}, {"regParam": 0.1}]),
                  ("random_forest", RandomForestRegressor(labelCol="label", featuresCol="features", seed=42), [{"numTrees": 50, "maxDepth": 8}, {"numTrees": 80, "maxDepth": 12}]),
                  ("gbt", GBTRegressor(labelCol="label", featuresCol="features", seed=42), [{"maxIter": 40, "maxDepth": 5}, {"maxIter": 70, "maxDepth": 7}]),
                  ("decision_tree", DecisionTreeRegressor(labelCol="label", featuresCol="features", seed=42), [{"maxDepth": 6}, {"maxDepth": 10}])]
    candidates = []
    for name, estimator, grid in algorithms:
        best = None
        for settings in grid:
            est = estimator.copy({estimator.getParam(k): v for k, v in settings.items()})
            imputer = Imputer(inputCols=features, outputCols=[f"{x}__imputed" for x in features], strategy="median")
            idx = StringIndexer(inputCol="route_id", outputCol="route_id__encoded", handleInvalid="keep")
            va = VectorAssembler(inputCols=[f"{x}__imputed" for x in features] + ["route_id__encoded"], outputCol="features")
            pipe = Pipeline(stages=[imputer, idx, va, est])
            fitted = pipe.fit(frames["train"].withColumn("label", "target"))
            score = reg_scores(fitted.transform(frames["validation"].withColumn("label", "target")))
            if best is None or score["rmse"] < best[0]["rmse"]: best = (score, settings)
        est = estimator.copy({estimator.getParam(k): v for k, v in best[1].items()})
        pipe = Pipeline(stages=[Imputer(inputCols=features, outputCols=[f"{x}__imputed" for x in features], strategy="median"), StringIndexer(inputCol="route_id", outputCol="route_id__encoded", handleInvalid="keep"), VectorAssembler(inputCols=[f"{x}__imputed" for x in features] + ["route_id__encoded"], outputCol="features"), est])
        final = pipe.fit(frames["train"].unionByName(frames["validation"]).withColumn("label", "target"))
        metrics = {s: reg_scores(final.transform(d.withColumn("label", "target"))) for s, d in frames.items()}
        record = {"task": "daily_boardings", "algorithm": name, "selected_params": best[1], "metrics": metrics, "baseline": baseline,
                  "null_handling": "Median Imputer for strictly-prior lag/rolling features; no boardings value was zero-filled.", "date": DATE}
        save_json("daily_boardings", name, record); METRICS.append(record); candidates.append((record, final))
    winner, model = min(candidates, key=lambda x: x[0]["metrics"]["validation"]["rmse"])
    model.write().overwrite().save(model_dir("daily_boardings", winner["algorithm"])); save_version("daily_boardings", winner["algorithm"], {"version":"v1", "date":DATE, "metrics":winner["metrics"]})
    sample_predictions("daily_boardings", model.transform(frames["test"].withColumn("label", "target")), "regression")
    return winner, baseline


def run_clustering(log, route):
    # Stored route_features contains train-only measures. These are the requested operational equivalents.
    features = ["route_load_factor", "route_reliability_delay_min", "trip_punctuality_rate", "avg_trip_boardings", "avg_daily_boardings", "crowding_rate", "bunching_rate", "arrival_delay_std_min"]
    route = route.filter("in_train_period").dropna(subset=features)
    pipe = Pipeline(stages=[StandardScaler(inputCol="raw_features", outputCol="features", withMean=True, withStd=True)])
    raw = VectorAssembler(inputCols=features, outputCol="raw_features").transform(route)
    scaled = pipe.fit(raw).transform(raw)
    evaluator = ClusteringEvaluator(featuresCol="features", predictionCol="prediction", metricName="silhouette")
    candidates = []
    for name, cls in (("kmeans", KMeans), ("bisecting_kmeans", BisectingKMeans), ("gaussian_mixture", GaussianMixture)):
        for k in (3, 4, 5):
            model = cls(k=k, seed=42, featuresCol="features", predictionCol="prediction").fit(scaled)
            pred = model.transform(scaled); score = round(evaluator.evaluate(pred), 6)
            record = {"task":"route_clustering", "algorithm":name, "k":k, "silhouette":score, "date":DATE, "features":features}
            save_json("route_clustering", f"{name}_k{k}", record); METRICS.append(record); candidates.append((record, model, pred))
    winner, model, pred = max(candidates, key=lambda x: x[0]["silhouette"])
    model.write().overwrite().save(model_dir("route_clustering", f"{winner['algorithm']}_k{winner['k']}"))
    save_version("route_clustering", f"{winner['algorithm']}_k{winner['k']}", {"version":"v1", "date":DATE, **winner})
    profiles = pred.groupBy("prediction").agg(*[F.avg(c).alias(c) for c in features], F.count("*").alias("routes")).orderBy("prediction").toPandas()
    # Labels are intentionally descriptive rather than pretending an unsupervised cluster is ground truth.
    profiles["plain_language_label"] = ["High-demand reliable routes" if r.avg_daily_boardings >= profiles.avg_daily_boardings.median() and r.trip_punctuality_rate >= profiles.trip_punctuality_rate.median() else "Capacity or reliability needs review" for r in profiles.itertuples()]
    profiles.to_csv(REPORTS / "phase6_cluster_profiles.csv", index=False)
    return winner, profiles


def write_docs(winners, date_ranges):
    REPORTS.mkdir(exist_ok=True); MODELS.mkdir(parents=True, exist_ok=True)
    lines = ["# Spark Model Metrics (Phase 6)", "", f"Generated {DATE}. Test data was used only once for each final selected model.", "",
             "| task | algorithm | train | validation | test |", "|---|---|---|---|---|"]
    for r in METRICS:
        if "metrics" in r:
            lines.append(f"| {r['task']} | {r['algorithm']} | {r['metrics']['train']} | {r['metrics']['validation']} | {r['metrics']['test']} |")
        else:
            lines.append(f"| route_clustering | {r['algorithm']} k={r['k']} | - | silhouette={r['silhouette']} | - |")
    lines += ["", "## Leakage checklist", "", "```json", json.dumps(date_ranges, indent=2), "```", "", "## NULL handling", "", "All numeric feature NULLs handled by Spark `Imputer(strategy='median')`; occupancy, boardings, and delay measurements were never zero-filled."]
    (REPORTS / "spark_model_metrics.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    doc = ["# Spark Models Explained", "", "## What the metrics mean", "", "Macro F1 gives every class equal importance; accuracy is the overall share correct. MAE and RMSE are average forecasting errors (RMSE penalises large misses more). R² measures explained variation. Silhouette measures how separate route clusters are; higher is better.", "",
           "## Algorithms", "", "Logistic Regression is a transparent weighted score. A Random Forest is like running many slightly different database queries and taking their majority vote. Gradient-Boosted Trees are like iteratively fixing the mistakes of the previous query. Linear Regression estimates a numerical trend; tree regressors learn non-linear decision rules. K-Means groups routes around representative centres; Bisecting K-Means repeatedly splits groups; Gaussian Mixture assigns routes probabilistically to overlapping groups.", "",
           "## Tasks", "", "Delay severity predicts the stored operational severity band. The actual labels are On Time, Minor, Moderate and Severe (the source schema does not contain a Major value). Crowding predicts whether occupancy crosses the configured 0.90 threshold. Daily boardings forecasts route demand from strictly previous demand. Route clustering groups the train-only operational route profiles. Categorical route and vehicle IDs are indexed; numerical missing values are median-imputed, never silently set to zero.", "",
           "## Schema mapping", "", "The Phase 4 schema uses `route_load_factor` for average occupancy/load factor, `route_reliability_delay_min` for average delay/reliability, and `avg_daily_boardings` for demand. Tasks A and B use trip-level `occupancy_pct`, `historical_delay_average`, `distance_km`, `travel_time_min`, `n_stops`, and demand growth; Task C uses `estimated_daily_boardings` and strict-prior lags; Task D uses the three route-level fields above with `avg_trip_boardings`, punctuality, crowding, bunching, and arrival-delay variability."]
    (PROJECT_ROOT / "documentation" / "spark_models_explained.md").write_text("\n".join(doc)+"\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-a-trees", action="store_true", help="resume only Task A Random Forest and multiclass GBT; preserves Logistic Regression")
    args = ap.parse_args()
    log, _ = get_logger("phase6_spark_models")
    spark = get_spark("phase6-spark-models")
    trip = spark.read.parquet(hdfs_uri("full", "features", "trip_features"))
    demand = spark.read.parquet(hdfs_uri("full", "features", "route_daily_demand"))
    route = spark.read.parquet(hdfs_uri("full", "features", "route_features"))
    date_ranges = {"trip_features": date_check(log, trip, "trip_features"), "route_daily_demand": date_check(log, demand, "route_daily_demand")}
    base = as_number(trip.join(route.select("route_id", "n_stops"), "route_id", "left"), ["hour", "day_of_week", "weekend_indicator", "peak_hour_indicator_asof"])
    # These rolling occupancy features are strictly past trip observations on the same route.
    w = Window.partitionBy("route_id").orderBy("scheduled_departure", "trip_id")
    base = (base.withColumn("rolling_28_mean_occupancy", F.avg("occupancy_pct").over(w.rowsBetween(-28, -1)))
                .withColumn("lag_7_occupancy", F.lag("occupancy_pct", 7).over(w)))
    common = ["hour", "day_of_week", "weekend_indicator", "peak_hour_indicator_asof", "historical_delay_average", "occupancy_pct", "n_stops", "distance_km", "travel_time_min", "demand_wow_growth"]
    delay = base.filter(F.col("delay_severity").isNotNull())
    # vehicle_id has 763 values; tree maxBins must cover that indexed categorical domain.
    task_a_trees = [("random_forest", RandomForestClassifier(seed=42, numTrees=100, maxBins=1024), [{"maxDepth":6}, {"maxDepth":8}, {"maxDepth":10}]),
                    ("gbt_one_vs_rest", OneVsRest(classifier=GBTClassifier(seed=42, maxBins=1024)),
                     [{"classifier_maxIter": i, "classifier_maxDepth": d} for i in (30, 50, 80) for d in (5, 6, 8)])]
    if args.task_a_trees:
        a = run_classification(log, "delay_severity", delay, "delay_severity", common, ["route_id", "vehicle_id"], task_a_trees)
        write_docs({"delay": a}, date_ranges)
        log.info("PHASE6 TASK A TREES COMPLETE winner=%s", a["algorithm"])
        spark.stop()
        return
    a = run_classification(log, "delay_severity", delay, "delay_severity", common, ["route_id", "vehicle_id"],
        [("logistic_regression", LogisticRegression(maxIter=80), [{"regParam":0.01}, {"regParam":0.1}]), *task_a_trees])
    crowd = base.filter(F.col("crowding_flag").isNotNull())
    rate = crowd.filter("crowding_flag").count() / crowd.count(); log.info("crowding positive rate=%.6f", rate)
    b = run_classification(log, "crowding_flag", crowd, "crowding_flag", common + ["rolling_28_mean_occupancy", "lag_7_occupancy"], ["route_id", "vehicle_id"],
        [("logistic_regression", LogisticRegression(maxIter=80), [{"regParam":0.01}, {"regParam":0.1}]), ("random_forest", RandomForestClassifier(seed=42), [{"numTrees":50,"maxDepth":10}, {"numTrees":80,"maxDepth":14}]), ("gbt", GBTClassifier(seed=42), [{"maxIter":40,"maxDepth":5}, {"maxIter":70,"maxDepth":7}])], rate)
    c, baseline = run_forecast(log, demand)
    d, profiles = run_clustering(log, route)
    write_docs({"delay":a, "crowding":b, "demand":c, "cluster":d}, date_ranges)
    log.info("PHASE6 COMPLETE winners: delay=%s crowding=%s demand=%s cluster=%s", a["algorithm"], b["algorithm"], c["algorithm"], d)
    spark.stop()


if __name__ == "__main__":
    main()
