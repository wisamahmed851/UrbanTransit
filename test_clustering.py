import os, sys
from pathlib import Path
import logging
import pandas as pd
ROOT = Path("E:/Projects/Techwizz7/UrbanTransit")
def extend_spark_clustering():
    from pyspark.sql import SparkSession
    from pyspark.ml.clustering import KMeansModel
    from pyspark.ml.feature import StandardScaler, VectorAssembler
    from pyspark.ml import Pipeline
    spark = SparkSession.builder.appName("extend").getOrCreate()
    route = spark.read.parquet("hdfs://localhost:9000/urbantransit/features/route_features")
    features = ["route_load_factor", "route_reliability_delay_min", "trip_punctuality_rate", "avg_trip_boardings", "avg_daily_boardings", "crowding_rate", "bunching_rate", "arrival_delay_std_min"]
    route = route.filter("in_train_period").dropna(subset=features)
    pipe = Pipeline(stages=[StandardScaler(inputCol="raw_features", outputCol="features", withMean=True, withStd=True)])
    raw = VectorAssembler(inputCols=features, outputCol="raw_features").transform(route)
    scaled = pipe.fit(raw).transform(raw)
    
    print("Loading model...")
    model_path = "file:///" + str(ROOT / "models" / "spark" / "route_clustering" / "kmeans_k4_v1").replace("\\", "/")
    print(f"Path: {model_path}")
    model = KMeansModel.load(model_path)
    print("Transforming...")
    pred = model.transform(scaled).select("route_id", "prediction").toPandas()
    print("Saving...")
    print(pred.head())
    
extend_spark_clustering()
