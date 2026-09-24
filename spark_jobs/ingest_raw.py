"""Phase 2 ingestion: raw files in HDFS -> typed DataFrames -> quarantine + partitioned Parquet in HDFS.

What happens per table
----------------------
1. **Rows in** - count the raw records independently of the parser (text lines minus one
   header per CSV file; JSON Lines = lines; the JSON calendar = array elements).
2. **Typed read** - read *all files of the table at once* (multi-file ingestion, e.g. the 12
   monthly ticket files) with the explicit schema from schemas.py in PERMISSIVE mode.
   A row whose value cannot be converted to its type is NOT dropped: Spark keeps the raw
   line in `_corrupt_record`.
3. **Split** - rows with `_corrupt_record` go to /quarantine/<table>/ (raw line, source file,
   which columns failed); the others are the "OK" rows.
4. **Reconcile** - rows in == OK + quarantined, and the typed read count == rows in.
5. **Parquet** - OK rows are written as Snappy Parquet to /parquet/<table>/, partitioned as
   described in documentation/partition_strategy.md, then read back and counted again.
6. **Measure** - timings per step and CSV/JSON vs Parquet sizes.

No cleaning happens here (that is Phase 3): values are kept exactly as parsed, including the
injected defects that are type-valid (duplicates, negative counts, unknown IDs, ...).
Only `_source_file` (lineage) and the partition column are added.

NestJS analogy: the explicit schema is the DTO + ValidationPipe; instead of throwing a 400 for
a bad row, we put it in a "dead-letter" folder (the quarantine) and keep processing.

Usage (WSL, venv, HDFS running):  python spark_jobs/ingest_raw.py --mode full
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyspark import StorageLevel  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import StringType, StructField, StructType  # noqa: E402

from spark_jobs.common import (PROJECT_ROOT, get_logger, get_spark, hdfs_du_bytes, hdfs_file_count,  # noqa: E402
                               hdfs_uri, timed)
from spark_jobs.schemas import CORRUPT_COL, FORMATS, SCHEMAS, verify_against_docs, with_corrupt_column  # noqa: E402

TS_FMT = "yyyy-MM-dd HH:mm:ss"
DATE_FMT = "yyyy-MM-dd"

# Partitioning strategy (justified in documentation/partition_strategy.md):
#   big event tables -> one folder per month of service_date (queries are almost always by period),
#   GPS -> one folder per day (7-day window, per-day files arrive daily),
#   small reference tables -> not partitioned, a single file each.
# (Column expressions are built lazily - Spark needs a running session to create them.)
def _year_month():
    return F.date_format("service_date", "yyyy-MM")


PARTITIONS = {
    "trips": ("year_month", _year_month),
    "passenger_counts": ("year_month", _year_month),
    "tickets": ("year_month", _year_month),
    "delays": ("year_month", _year_month),
    "gps_events": ("event_date", lambda: F.to_date("event_time")),
}


def count_raw_records(spark, table: str, path: str) -> tuple[int, int]:
    """(records, files) counted without the typed parser, so it is an independent reference."""
    files = hdfs_file_count(path)
    fmt = FORMATS[table]
    if fmt == "json":                                   # one JSON array per file
        return spark.read.option("multiLine", True).json(path).count(), files
    lines = spark.read.text(path).filter(F.length(F.trim("value")) > 0).count()
    return (lines - files if fmt == "csv" else lines), files


def typed_read(spark, table: str, path: str):
    """All files of the table with the explicit schema; bad rows kept in _corrupt_record."""
    reader = (spark.read.schema(with_corrupt_column(table))
              .option("mode", "PERMISSIVE")
              .option("columnNameOfCorruptRecord", CORRUPT_COL)
              .option("timestampFormat", TS_FMT)
              .option("dateFormat", DATE_FMT))
    fmt = FORMATS[table]
    if fmt == "csv":
        df = reader.option("header", True).option("enforceSchema", True).csv(path)
    else:
        df = reader.option("multiLine", fmt == "json").json(path)
    return df.withColumn("_source_file", F.input_file_name())


def failed_columns_expr(table: str):
    """For a quarantined CSV line: comma-separated names of the columns whose text fails their type."""
    fields = SCHEMAS[table].fields
    as_strings = StructType([StructField(f.name, StringType(), True) for f in fields])
    parsed = F.from_csv(F.col(CORRUPT_COL), as_strings.simpleString(), {"header": "false"}) \
        if FORMATS[table] == "csv" else F.from_json(F.col(CORRUPT_COL), as_strings)
    checks = []
    for f in fields:
        t = f.dataType.simpleString()
        v = parsed[f.name]
        if t == "timestamp":
            ok = F.call_function("try_to_timestamp", v, F.lit(TS_FMT)).isNotNull()
        elif t == "date":
            ok = F.call_function("try_to_timestamp", v, F.lit(DATE_FMT)).isNotNull()
        elif t in ("int", "double", "boolean"):
            ok = v.try_cast(t).isNotNull()
        else:
            continue
        bad = v.isNotNull() & (F.trim(v) != "") & ~ok
        checks.append(F.when(bad, F.lit(f.name)))
    return F.concat_ws(",", *checks) if checks else F.lit("")


def ingest_table(spark, log, mode: str, table: str) -> dict:
    raw = hdfs_uri(mode, "raw", table)
    parquet = hdfs_uri(mode, "parquet", table)
    quarantine = hdfs_uri(mode, "quarantine", table)
    m = {"table": table, "format": FORMATS[table], "timings_s": {}}
    tm = m["timings_s"]

    with timed(log, f"{table}: count raw records (text)", tm, "count_raw"):
        m["rows_in"], m["raw_files"] = count_raw_records(spark, table, raw)

    with timed(log, f"{table}: typed read + parse (all files, explicit schema)", tm, "read_parse"):
        df = typed_read(spark, table, raw).persist(StorageLevel.MEMORY_AND_DISK)
        m["rows_read"] = df.count()                    # materialises the fully parsed rows
    m["input_files_read"] = len(df.inputFiles())
    m["rows_per_file"] = {Path(r["_source_file"]).name: r["count"]
                          for r in df.groupBy("_source_file").count().orderBy("_source_file").collect()}

    bad = df.filter(F.col(CORRUPT_COL).isNotNull())
    ok = df.filter(F.col(CORRUPT_COL).isNull()).drop(CORRUPT_COL)

    with timed(log, f"{table}: write quarantine", tm, "quarantine_write"):
        q = (bad.select(F.lit(table).alias("table"), F.col("_source_file").alias("source_file"),
                        F.col(CORRUPT_COL).alias("raw_record"), failed_columns_expr(table).alias("failed_columns"),
                        F.lit("type_parse_failure").alias("reason"), F.current_timestamp().alias("quarantined_at"))
             .persist(StorageLevel.MEMORY_AND_DISK))
        m["rows_quarantined"] = q.count()
        q.coalesce(1).write.mode("overwrite").json(quarantine)
        m["quarantine_by_column"] = {r["failed_columns"]: r["count"]
                                     for r in q.groupBy("failed_columns").count().collect()}
        m["quarantine_examples"] = [r["raw_record"][:160] for r in q.select("raw_record").limit(3).collect()]
    m["rows_ok"] = m["rows_read"] - m["rows_quarantined"]

    with timed(log, f"{table}: write parquet", tm, "parquet_write"):
        if table in PARTITIONS:
            name, make_expr = PARTITIONS[table]
            out = ok.withColumn(name, make_expr())
            # one task per partition value -> one file per month/day (no tiny files)
            out.repartition(name).write.mode("overwrite").partitionBy(name).parquet(parquet)
            m["partition_column"] = name
        else:
            ok.coalesce(1).write.mode("overwrite").parquet(parquet)
            m["partition_column"] = None

    with timed(log, f"{table}: read back parquet", tm, "parquet_readback"):
        back = spark.read.parquet(parquet)
        m["rows_parquet"] = back.count()
        if m["partition_column"]:
            m["partitions"] = back.select(m["partition_column"]).distinct().count()

    m["raw_bytes"] = hdfs_du_bytes(raw)
    m["parquet_bytes"] = hdfs_du_bytes(parquet)
    m["parquet_files"] = hdfs_file_count(parquet)
    m["quarantine_bytes"] = hdfs_du_bytes(quarantine)
    m["reconciled"] = (m["rows_in"] == m["rows_ok"] + m["rows_quarantined"] == m["rows_read"])
    m["parquet_matches_ok"] = m["rows_parquet"] == m["rows_ok"]
    total_s = sum(tm.values())
    m["rows_per_second"] = round(m["rows_in"] / max(total_s, 1e-9))
    log.info(f"{table}: in={m['rows_in']:,} read={m['rows_read']:,} ok={m['rows_ok']:,} "
             f"quarantined={m['rows_quarantined']:,} parquet={m['rows_parquet']:,} "
             f"reconciled={m['reconciled']} parquet_ok={m['parquet_matches_ok']} "
             f"raw={m['raw_bytes'] / 1e6:.1f}MB parquet={m['parquet_bytes'] / 1e6:.1f}MB files={m['parquet_files']}")
    df.unpersist(); q.unpersist()
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="full")
    ap.add_argument("--tables", nargs="*", help="subset of tables (default: all 12)")
    args = ap.parse_args()
    log, log_path = get_logger(f"ingest_raw_{args.mode}")
    drift = verify_against_docs()
    if drift:
        raise SystemExit(f"Spark schemas differ from documentation/schemas: {drift}")
    spark = get_spark("ingest-raw")
    # parse every column even when a query only needs some, so type failures are always detected
    spark.conf.set("spark.sql.csv.parser.columnPruning.enabled", "false")
    log.info(f"mode={args.mode} spark={spark.version} master={spark.sparkContext.master} "
             f"shuffle_partitions={spark.conf.get('spark.sql.shuffle.partitions')} "
             f"driver_memory={spark.conf.get('spark.driver.memory')} codec={spark.conf.get('spark.sql.parquet.compression.codec')}")
    tables = args.tables or list(SCHEMAS)
    t0 = time.perf_counter()
    results = [ingest_table(spark, log, args.mode, t) for t in tables]
    total = round(time.perf_counter() - t0, 1)
    ok = all(r["reconciled"] and r["parquet_matches_ok"] for r in results)
    out = PROJECT_ROOT / "reports" / f"ingestion_metrics_{args.mode}.json"
    out.write_text(json.dumps({"mode": args.mode, "spark_version": spark.version, "total_seconds": total,
                               "log_file": str(log_path.relative_to(PROJECT_ROOT)), "all_reconciled": ok,
                               "tables": results}, indent=2), encoding="utf-8")
    log.info(f"INGESTION {'PASS' if ok else 'FAIL'}: {len(results)} tables in {total}s; metrics -> {out.relative_to(PROJECT_ROOT)}")
    spark.stop()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
