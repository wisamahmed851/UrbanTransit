"""Check that the MySQL copies hold the same values as the HDFS Parquet, not just the same row count.

Run inside WSL (HDFS started, venv active) after `load_analytics_to_mysql.py`:

    python database/verify_mysql_load.py

For every column of every analytics table it compares, Parquet vs MySQL:

* all columns: non-NULL count
* decimal / int / bigint / boolean: exact SUM (decimals are exact in both systems)
* double: SUM within a relative 1e-9 (floating-point addition order differs)
* string / date: COUNT(DISTINCT)

Writes `reports/mysql_load_verification.json`; exit code 1 on any mismatch.
"""

import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyspark.sql import functions as F  # noqa: E402
from sqlalchemy import Integer, cast, func, select  # noqa: E402

from spark_jobs.common import PROJECT_ROOT, get_logger, get_spark, hdfs_uri  # noqa: E402
from src.app import create_app  # noqa: E402
from src.extensions import db  # noqa: E402
from src.models.analytics import ANALYTICS_SCHEMAS, ANALYTICS_TABLES  # noqa: E402

REPORT_PATH = PROJECT_ROOT / "reports" / "mysql_load_verification.json"
EXACT_SUM = ("int", "bigint", "boolean")


def kind(spark_type: str) -> str:
    if spark_type.startswith("decimal") or spark_type in EXACT_SUM:
        return "exact_sum"
    if spark_type == "double":
        return "float_sum"
    return "distinct"


def spark_stats(df, columns):
    aggs = []
    for col, t in columns:
        aggs.append(F.count(col).alias(f"{col}__n"))
        k = kind(t)
        if k == "distinct":
            aggs.append(F.countDistinct(col).alias(f"{col}__v"))
        else:
            aggs.append(F.sum(F.col(col).cast("int") if t == "boolean" else F.col(col)).alias(f"{col}__v"))
    return df.agg(*aggs).first().asDict()


def mysql_stats(table, columns):
    exprs = []
    for col, t in columns:
        c = table.c[col]
        exprs.append(func.count(c).label(f"{col}__n"))
        k = kind(t)
        if k == "distinct":
            exprs.append(func.count(c.distinct()).label(f"{col}__v"))
        else:
            exprs.append(func.sum(cast(c, Integer) if t == "boolean" else c).label(f"{col}__v"))
    with db.engine.connect() as conn:
        return dict(conn.execute(select(*exprs)).mappings().one())


def same(a, b, k: str) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if k == "float_sum":
        return abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a)))
    if k == "exact_sum":
        return Decimal(str(a)) == Decimal(str(b))
    return int(a) == int(b)


def main() -> int:
    log, _ = get_logger("verify_mysql_load")
    spark = get_spark("verify-mysql-load")
    app = create_app()
    results, failed = {}, []
    with app.app_context():
        for name, columns in ANALYTICS_SCHEMAS.items():
            s = spark_stats(spark.read.parquet(hdfs_uri("full", "analytics", name)), columns)
            m = mysql_stats(ANALYTICS_TABLES[name], columns)
            bad = []
            for col, t in columns:
                k = kind(t)
                if s[f"{col}__n"] != m[f"{col}__n"]:
                    bad.append({"column": col, "check": "non_null_count", "parquet": s[f"{col}__n"], "mysql": m[f"{col}__n"]})
                if not same(s[f"{col}__v"], m[f"{col}__v"], k):
                    bad.append({"column": col, "check": k, "parquet": str(s[f"{col}__v"]), "mysql": str(m[f"{col}__v"])})
            results[name] = {"columns_checked": len(columns), "mismatches": bad}
            if bad:
                failed.append(name)
            log.info("%-26s %2d columns  %s", name, len(columns), "PASS" if not bad else f"FAIL {bad}")
    spark.stop()
    report = {"result": "PASS" if not failed else "FAIL", "failed": failed, "tables": results}
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log.info("VERIFY %s (%d tables, %d columns)", report["result"], len(results),
             sum(r["columns_checked"] for r in results.values()))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
