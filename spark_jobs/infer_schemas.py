"""Compare Spark's inferred schemas with our explicit schemas and document the differences.

For each table we:
1. read the raw files from HDFS with schema inference (CSV `inferSchema=true`, JSON default inference)
   and time it,
2. compare every column's inferred type with the explicit type in spark_jobs/schemas.py,
3. for every mismatch, count how many raw values actually fail the explicit type (so the
   explanation is evidence-based, e.g. "3 text values in delay_minutes"),
4. write reports/schema_inference_<mode>.json and documentation/schema_inference_comparison.md.

Laravel analogy: inference is like letting the database guess column types from the first
CSV import instead of writing a migration - convenient, but one bad row changes the type
for the whole column.

Usage (WSL, venv, HDFS running): python spark_jobs/infer_schemas.py --mode full
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import StringType, StructField, StructType  # noqa: E402

from spark_jobs.common import PROJECT_ROOT, get_logger, get_spark, hdfs_uri  # noqa: E402
from spark_jobs.schemas import FORMATS, SCHEMAS  # noqa: E402

TS_FMT = "yyyy-MM-dd HH:mm:ss"


def read_inferred(spark, table, path):
    fmt = FORMATS[table]
    if fmt == "csv":
        return spark.read.option("header", True).option("inferSchema", True).csv(path)
    if fmt == "json":
        return spark.read.option("multiLine", True).json(path)
    return spark.read.json(path)                        # JSON Lines


def read_as_strings(spark, table, path):
    """Read with every column as string (for counting values that fail the explicit type)."""
    schema = StructType([StructField(f.name, StringType(), True) for f in SCHEMAS[table].fields])
    fmt = FORMATS[table]
    if fmt == "csv":
        return spark.read.option("header", True).schema(schema).csv(path)
    return spark.read.option("multiLine", fmt == "json").schema(schema).json(path)


def failing_values(col, spark_type: str):
    """Spark SQL condition: value present but not valid for the explicit type."""
    present = F.col(col).isNotNull() & (F.trim(F.col(col)) != "")
    if spark_type == "timestamp":
        ok = F.expr(f"try_to_timestamp(`{col}`, '{TS_FMT}')").isNotNull()
    elif spark_type == "date":
        ok = F.expr(f"try_to_timestamp(`{col}`, 'yyyy-MM-dd')").isNotNull()
    elif spark_type in ("int", "double", "boolean"):
        ok = F.expr(f"try_cast(`{col}` AS {spark_type})").isNotNull()
    else:
        return F.lit(False)
    return present & ~ok


def explain(explicit: str, inferred: str, n_bad: int, samples: list) -> str:
    """Human-readable reason for a type difference."""
    if explicit == "timestamp" and inferred == "string":
        if n_bad:
            return f"{n_bad:,} values are not valid timestamps (e.g. {samples}), so Spark fell back to string"
        return "JSON has no timestamp type: JSON inference never produces timestamps, only strings"
    if explicit == "date" and inferred == "string":
        return "JSON has no date type (dates stay strings)" if not n_bad else f"{n_bad:,} invalid dates (e.g. {samples})"
    if explicit == "date" and inferred == "timestamp":
        return "Spark inferred a timestamp for date-only values (midnight time added)"
    if explicit == "double" and inferred == "string":
        return f"{n_bad:,} non-numeric values (e.g. {samples}) turned the whole column into string"
    if explicit == "int" and inferred == "bigint":
        return "JSON inference always uses 64-bit integers (bigint); values fit in int"
    if explicit == "double" and inferred in ("int", "bigint"):
        return "every value happened to be a whole number, so Spark chose an integer type"
    if explicit == "string" and inferred in ("int", "bigint", "double"):
        return "values look numeric, but they are identifiers/codes and must stay strings"
    if explicit == "string" and inferred in ("date", "timestamp"):
        return "values look like dates but are stored as text by design"
    if explicit == "string" and inferred == "boolean":
        return "values look boolean but are text codes"
    if explicit.startswith("array<struct") and inferred.startswith("array<struct"):
        return "nested dates inferred as strings and struct fields ordered alphabetically"
    return "different type"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="full")
    args = ap.parse_args()
    log, log_path = get_logger(f"infer_schemas_{args.mode}")
    spark = get_spark("infer-schemas")
    results = []
    for table, explicit in SCHEMAS.items():
        path = hdfs_uri(args.mode, "raw", table)
        t0 = time.perf_counter()
        inferred_df = read_inferred(spark, table, path)
        infer_s = time.perf_counter() - t0                 # inference scans the data before any query
        inferred = {f.name: f.dataType.simpleString() for f in inferred_df.schema.fields}
        strings = read_as_strings(spark, table, path)
        cols = []
        for f in explicit.fields:
            exp_t, inf_t = f.dataType.simpleString(), inferred.get(f.name, "MISSING")
            row = {"column": f.name, "explicit": exp_t, "inferred": inf_t, "match": exp_t == inf_t}
            if not row["match"]:
                bad_df = strings.filter(failing_values(f.name, exp_t))
                row["values_failing_explicit_type"] = bad_df.count()
                row["examples"] = [r[0] for r in bad_df.select(f.name).distinct().limit(3).collect()]
                row["reason"] = explain(exp_t, inf_t, row["values_failing_explicit_type"], row["examples"])
            cols.append(row)
        extra = sorted(set(inferred) - {f.name for f in explicit.fields})
        n_mis = sum(not c["match"] for c in cols)
        log.info(f"{table}: inference {infer_s:.1f}s, {n_mis} of {len(cols)} columns differ"
                 + "".join(f"\n    {c['column']}: explicit {c['explicit']} vs inferred {c['inferred']} - {c['reason']}"
                           for c in cols if not c["match"]))
        results.append({"table": table, "format": FORMATS[table], "inference_seconds": round(infer_s, 2),
                        "columns": cols, "extra_inferred_columns": extra, "mismatches": n_mis})

    out_json = PROJECT_ROOT / "reports" / f"schema_inference_{args.mode}.json"
    out_json.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    lines = ["# Schema Inference vs Explicit Schemas", "",
             f"_Generated by `spark_jobs/infer_schemas.py --mode {args.mode}` from the raw files in HDFS "
             f"(log: `{log_path.relative_to(PROJECT_ROOT)}`)._", "",
             "Spark can infer types (`inferSchema=true` for CSV, automatic for JSON). The table below shows where "
             "that guess differs from the explicit schemas in `spark_jobs/schemas.py`, and why. For each difference "
             "the raw values were re-checked against the explicit type; *failing values* is how many values really "
             "are invalid for the documented type.", "",
             "| table | format | inference time (s) | columns | differences |", "|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['table']} | {r['format']} | {r['inference_seconds']} | {len(r['columns'])} | {r['mismatches']} |")
    lines += ["", "## Differences", "", "| table | column | explicit | inferred | failing values | reason |", "|---|---|---|---|---|---|"]
    for r in results:
        for c in r["columns"]:
            if not c["match"]:
                lines.append(f"| {r['table']} | {c['column']} | `{c['explicit']}` | `{c['inferred']}` | "
                             f"{c['values_failing_explicit_type']:,} | {c['reason']} |")
    lines += ["", "## Why the pipeline uses explicit schemas", "",
              "- **Correct types even with dirty data:** a handful of bad values should become quarantined rows, not "
              "turn a whole column into strings.",
              "- **No extra pass over the data:** inference reads the files once just to guess types (time above).",
              "- **Stable contract:** the same types every run and in every mode, matching `documentation/schemas/`.",
              "- **Identifiers stay text:** IDs and codes are never parsed as numbers.", ""]
    doc = PROJECT_ROOT / "documentation" / "schema_inference_comparison.md"
    doc.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"wrote {out_json.relative_to(PROJECT_ROOT)} and {doc.relative_to(PROJECT_ROOT)}")
    spark.stop()


if __name__ == "__main__":
    main()
