"""Null/sanity counts on the trip_features Parquet: python spark_jobs/phase4_null_check.py <label>.

Writes reports/phase4_null_check_<label>.json so before/after runs can be compared.
"""
import json
import sys
from pathlib import Path

from pyspark.sql import functions as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spark_jobs.common import PROJECT_ROOT, get_spark, hdfs_uri


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "latest"
    spark = get_spark("phase4-null-check")
    f = spark.read.parquet(hdfs_uri("full", "features", "trip_features"))
    row = f.select(F.count("*").alias("rows"), *[F.sum(F.col(c).isNull().cast("int")).alias(c) for c in f.columns]).first().asDict()
    out = {"label": label, "rows": row.pop("rows"), "null_counts": row,
           "negative_headway": f.filter("headway_minutes < 0").count(),
           "zero_boardings": f.filter("boardings = 0").count(),
           "zero_delay_minutes": f.filter("delay_minutes = 0").count()}
    (PROJECT_ROOT / "reports" / f"phase4_null_check_{label}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    spark.stop()


if __name__ == "__main__":
    main()
