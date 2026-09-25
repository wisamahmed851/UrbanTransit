"""Verify Phase 4 split integrity and strict-prior historical feature values."""
import json
import sys
from pathlib import Path

from pyspark.sql import functions as F
from pyspark.sql.window import Window

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spark_jobs.common import PROJECT_ROOT, get_spark, hdfs_uri


def main():
    spark = get_spark("verify-phase4")
    feat = spark.read.parquet(hdfs_uri("full", "features", "trip_features"))
    dates = feat.groupBy("service_date").agg(F.countDistinct("split").alias("n"))
    overlap_dates = dates.filter("n != 1").count()
    routes = [r[0] for r in feat.select("route_id").distinct().orderBy("route_id").limit(5).collect()]
    sample = feat.filter(F.col("route_id").isin(routes))
    w = Window.partitionBy("route_id").orderBy("scheduled_departure", "trip_id").rowsBetween(Window.unboundedPreceding, -1)
    checked = sample.withColumn("expected", F.avg("boardings").over(w))
    mismatch = checked.filter(~(F.col("historical_demand_average").eqNullSafe(F.col("expected")))).count()
    out = {"split_dates_with_multiple_assignments": overlap_dates, "sample_routes": routes,
           "historical_demand_mismatches": mismatch, "result": "PASS" if overlap_dates == 0 and mismatch == 0 else "FAIL"}
    (PROJECT_ROOT / "reports" / "phase4_verification.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out))
    spark.stop()
    if out["result"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
