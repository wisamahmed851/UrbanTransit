"""Phase 0 check: SparkSession, DataFrame, Spark SQL, Parquet write/read, HDFS read.

Run inside WSL with HDFS started and hdfs_scripts/verify_hdfs.sh run once
(it leaves /urbantransit/verify/spark_input.txt in HDFS).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyspark.sql import SparkSession  # noqa: E402

from config import settings  # noqa: E402


def main() -> int:
    os.makedirs(settings.SPARK_LOCAL_DIR, exist_ok=True)
    builder = SparkSession.builder.appName(f"{settings.SPARK_APP_NAME}-verify").master(settings.SPARK_MASTER)
    for key, value in settings.SPARK_CONF.items():
        builder = builder.config(key, value)
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    print(f"Spark version: {spark.version}")

    df = spark.createDataFrame(
        [("R1", "S1", 12), ("R1", "S2", 30), ("R2", "S3", 7)],
        ["route_id", "stop_id", "passengers"],
    )
    df.createOrReplaceTempView("boardings")
    sql_result = spark.sql(
        "SELECT route_id, SUM(passengers) AS total FROM boardings GROUP BY route_id ORDER BY route_id"
    )
    sql_result.show()
    totals = {r["route_id"]: r["total"] for r in sql_result.collect()}
    assert totals == {"R1": 42, "R2": 7}, totals
    print("Spark SQL: PASS")

    # Parquet round trip on local disk (inside WSL, not /mnt/d)
    parquet_path = f"file://{settings.SPARK_LOCAL_DIR}/urbantransit_verify.parquet"
    df.write.mode("overwrite").parquet(parquet_path)
    back = spark.read.parquet(parquet_path)
    assert back.count() == 3
    print(f"Parquet write/read ({parquet_path}): PASS")

    # Read the file placed in HDFS by verify_hdfs.sh
    hdfs_file = settings.hdfs_path("verify", "spark_input.txt")
    hdfs_df = spark.read.option("header", True).csv(hdfs_file)
    hdfs_df.show()
    assert hdfs_df.count() == 3
    print(f"HDFS read ({hdfs_file}): PASS")

    spark.stop()
    print("VERIFY_SPARK: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
