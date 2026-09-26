"""Small, reproducible WSL/HDFS evidence run for Phase 6 Task D.

Run from the project root inside Ubuntu after Hadoop and Spark are configured:
  spark-submit spark_jobs/phase6_taskD_wsl_demo.py 2>&1 | tee reports/processing_logs/phase6_taskD_wsl.log
"""
from pathlib import Path

from pyspark.ml import Pipeline
from pyspark.ml.clustering import KMeans
from pyspark.ml.evaluation import ClusteringEvaluator
from pyspark.ml.feature import StandardScaler, VectorAssembler
from pyspark.sql import functions as F

from spark_jobs.common import PROJECT_ROOT, get_logger, get_spark, hdfs_uri


FEATURES = [
    "route_load_factor", "route_reliability_delay_min", "trip_punctuality_rate",
    "avg_trip_boardings", "avg_daily_boardings", "crowding_rate", "bunching_rate",
    "arrival_delay_std_min",
]
EXPECTED_SILHOUETTE = 0.514014


def main():
    log, _ = get_logger("phase6_taskD_wsl")
    spark = get_spark("phase6-taskD-wsl-demo")
    source = hdfs_uri("full", "features", "route_features")
    output = hdfs_uri("full", "models", "phase6", "route_clustering", "kmeans_k4_wsl_v1")
    # K-Means++ initialization can depend on input partitions even when a seed is set.
    # Canonical order and one partition make this small (116-route) demo reproducible.
    route = (spark.read.parquet(source).filter(F.col("in_train_period"))
             .dropna(subset=FEATURES).orderBy("route_id").coalesce(1))
    route_count = route.count()
    fingerprint = route.agg(*[F.round(F.avg(c), 6).alias(c) for c in FEATURES]).first().asDict()
    log.info("TASK_D_WSL_DEMO_INPUT routes=%s feature_means=%s", route_count, fingerprint)
    raw = VectorAssembler(inputCols=FEATURES, outputCol="raw_features").transform(route)
    scaled = Pipeline(stages=[StandardScaler(inputCol="raw_features", outputCol="features", withMean=True, withStd=True)]).fit(raw).transform(raw)
    model = KMeans(k=4, seed=42, featuresCol="features", predictionCol="prediction").fit(scaled)
    pred = model.transform(scaled)
    silhouette = ClusteringEvaluator(featuresCol="features", predictionCol="prediction", metricName="silhouette").evaluate(pred)
    assignments = pred.select("route_id", "prediction").orderBy("route_id")
    actual_k = assignments.select("prediction").distinct().count()
    model.write().overwrite().save(output)
    log.info("TASK_D_WSL_DEMO source=%s routes=%s k=%s silhouette=%.6f expected=%.6f delta=%.6f model=%s", source, route_count, actual_k, silhouette, EXPECTED_SILHOUETTE, abs(silhouette - EXPECTED_SILHOUETTE), output)
    assignments.show(20, truncate=False)
    if actual_k < 2 or abs(silhouette - EXPECTED_SILHOUETTE) > 0.05:
        raise RuntimeError("Task D demo result is outside the permitted comparison range")
    Path(PROJECT_ROOT / "reports" / "processing_logs").mkdir(parents=True, exist_ok=True)
    spark.stop()


if __name__ == "__main__":
    main()
