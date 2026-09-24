"""Phase 3 cleaning: apply the configured action of every data-quality rule.

Inputs : Phase 2 Parquet + ingestion quarantine (HDFS), DQ violations (HDFS /<base>/dq/violations),
         config/data_quality.yaml (actions, corrections, fallbacks, minimum volumes).
Outputs: HDFS /<base>/clean/<table>/            clean Parquet (+ `dq_flags` array column)
         HDFS /<base>/clean_quarantine/<table>/ rows that cannot be trusted, with the original record
         HDFS /<base>/cleaning_log/             one row per (record, rule): issue, original value,
                                                corrected value, action, final status
         reports/cleaning_metrics_<mode>.json   reconciliation, per-rule counts, fingerprints

Per table, in this order:
1. rows in = Phase 2 Parquet rows + rows quarantined at ingestion
2. duplicate rules (action remove): identical copies of a key are removed (one kept); if the
   copies differ, all of them are quarantined (the true version is unknown)
3. every other rule marks the rows it found (joined by record key; group rules by group key;
   the missing-trip rule marks child rows by trip_id)
4. effective action per row and rule: correct (deterministic derivation; if impossible -> the
   rule's fallback), flag (row kept, rule ID in dq_flags), quarantine. A row with any quarantine
   goes to the quarantine; otherwise it is kept with its corrections and flags.
5. rows quarantined at ingestion are re-parsed; if `correct` rules repair every column that
   failed to parse (e.g. delay_minutes recomputed from the timestamps) the row is recovered,
   otherwise it stays quarantined
6. reconcile: rows in = clean + removed + quarantined

Deterministic: no clocks or random numbers, stable window ordering -> rerunning produces identical
outputs (checked with per-table fingerprints in the metrics file).

Laravel analogy: like a queued job that walks every record, applies fix-up rules (mutators), moves
records that cannot be trusted to a `failed` table and writes an audit-log row for every change.

Usage: python spark_jobs/clean_data.py --mode full
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyspark import StorageLevel  # noqa: E402
from pyspark.sql import Window  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

from spark_jobs.common import PROJECT_ROOT, get_logger, get_spark, hdfs_uri  # noqa: E402
from spark_jobs.dq_rules import DQData, key_expr, load_dq_config, primary_key  # noqa: E402
from spark_jobs.ingest_raw import PARTITIONS  # noqa: E402
from spark_jobs.schemas import FORMATS, SCHEMAS  # noqa: E402

TS_FMT = "yyyy-MM-dd HH:mm:ss"
LOG_COLUMNS = ["table", "record_key", "rule_id", "defect_type", "column", "original_value",
               "corrected_value", "action", "final_status", "note"]


def empty_flags():
    """An empty array<string> column (built lazily: Spark needs a running session)."""
    return F.array().cast("array<string>")


# ---------------------------------------------------------------------------------------------
# Corrections
# ---------------------------------------------------------------------------------------------

def target_columns(rule: dict) -> list[str]:
    """Column(s) a correction writes to."""
    p = rule.get("params", {})
    if rule.get("correction", {}).get("method") == "swap_coordinates":
        return [p["lat"], p["lon"]]
    if "sequence_column" in p:
        return [p["sequence_column"]]
    return [p["column"]] if "column" in p else []


def log_columns(rule: dict, table: str) -> list[str]:
    """Column(s) whose values are written to the cleaning log for this rule."""
    p = rule.get("params", {})
    if rule["action"] == "correct":
        return target_columns(rule)
    if rule["check"] == "missing_parent":
        return [p["child_column"]]
    if p.get("columns"):
        return p["columns"]
    for key in ("column", "load_column", "later", "sequence_column", "lat"):
        if p.get(key):
            return [p[key]]
    return [primary_key(table)[0]]


def lookup_values(d: DQData, corr: dict):
    """key -> value pairs for a lookup correction; keys with more than one distinct value are dropped (ambiguous)."""
    lk = (d.table(corr["lookup_table"]).select(F.col(corr["lookup_key"]).alias("_lk"), F.col(corr["lookup_value"]).alias("_lv"))
          .filter(F.col("_lk").isNotNull() & F.col("_lv").isNotNull()).distinct())
    unique = lk.groupBy("_lk").agg(F.count("*").alias("_n")).filter("_n = 1").select("_lk")
    return lk.join(unique, "_lk")


def apply_correction(df, d: DQData, rule: dict, P: dict):
    """Add `_new_<col>` (corrected value) and `_fix_<rule>` (true where the correction succeeded)."""
    corr, rid, hit = rule["correction"], rule["id"], F.col(f"_hit_{rule['id']}")
    method = corr["method"]
    if method == "lookup":                     # e.g. route_id from the trip, vehicle_id from the APC record
        col = rule["params"]["column"]
        df = df.join(lookup_values(d, corr), F.col(corr["via_column"]) == F.col("_lk"), "left").drop("_lk")
        df = df.withColumn(f"_new_{col}", F.when(hit, F.col("_lv"))).drop("_lv")
        return df.withColumn(f"_fix_{rid}", hit & F.col(f"_new_{col}").isNotNull())
    if method == "minutes_between":            # delay_minutes = actual_arrival - scheduled_arrival
        col, p = rule["params"]["column"], rule["params"]
        mins = F.round((F.unix_timestamp(corr["end"]) - F.unix_timestamp(corr["start"])) / 60.0, 2)
        ok = (mins.isNotNull() & (mins >= P[p["min_param"]]) & (mins <= P[p["max_param"]])
              & (F.abs(mins) <= P["impossible_time_gap_hours"] * 60))
        df = df.withColumn(f"_new_{col}", F.when(hit & ok, mins))
        return df.withColumn(f"_fix_{rid}", hit & ok)
    if method == "resequence":                 # stop order = distance order
        p = rule["params"]
        w = Window.partitionBy(*p["group_by"]).orderBy(corr["order_by"], p["sequence_column"], "stop_id")
        df = df.withColumn(f"_new_{p['sequence_column']}", F.when(hit, F.row_number().over(w)))
        return df.withColumn(f"_fix_{rid}", hit)
    if method == "max_child_value":            # route length = distance of its last stop
        col = rule["params"]["column"]
        child = (d.table(corr["child_table"]).filter(corr.get("child_filter", "1=1"))
                 .groupBy(F.col(corr["child_key"]).alias("_ck")).agg(F.round(F.max(corr["child_value"]), 2).alias("_cv")))
        df = df.join(F.broadcast(child), F.col(primary_key(rule["table"])[0]) == F.col("_ck"), "left").drop("_ck")
        df = df.withColumn(f"_new_{col}", F.when(hit & (F.col("_cv") > 0), F.col("_cv"))).drop("_cv")
        return df.withColumn(f"_fix_{rid}", hit & F.col(f"_new_{col}").isNotNull())
    if method == "swap_coordinates":           # only if the swapped point lies inside the operating area
        p, b = rule["params"], P["geo_bounds"]
        lat, lon = F.col(p["lat"]), F.col(p["lon"])
        ok = lon.between(b["lat_min"], b["lat_max"]) & lat.between(b["lon_min"], b["lon_max"])
        df = df.withColumn(f"_new_{p['lat']}", F.when(hit & ok, lon)).withColumn(f"_new_{p['lon']}", F.when(hit & ok, lat))
        return df.withColumn(f"_fix_{rid}", hit & ok)
    raise ValueError(f"{rid}: unknown correction method {method!r}")


def typed_from_strings(df, table: str):
    """Cast the string columns of re-parsed quarantined lines to the explicit types (bad values -> null)."""
    out = []
    for f in SCHEMAS[table].fields:
        t, c = f.dataType.simpleString(), F.col(f.name)
        if t == "timestamp":
            e = F.call_function("try_to_timestamp", c, F.lit(TS_FMT))
        elif t == "date":
            e = F.call_function("try_to_timestamp", c, F.lit("yyyy-MM-dd")).cast("date")
        elif t in ("int", "double", "boolean"):
            e = c.try_cast(t)
        else:
            e = c
        out.append(e.alias(f.name))
    return df.select(*out, "record_key", "failed_columns", "raw_record", F.col("source_file").alias("_source_file"))


def log_rows(df, table, rule_id, defect, column, original, corrected, action, status, note):
    """Shape rows into the cleaning-log format."""
    lit = lambda v: v if not isinstance(v, (str, type(None))) else F.lit(v).cast("string")  # noqa: E731
    return df.select(F.lit(table).alias("table"), F.col("record_key"), lit(rule_id).alias("rule_id"),
                     lit(defect).alias("defect_type"), lit(column).alias("column"), lit(original).alias("original_value"),
                     lit(corrected).alias("corrected_value"), lit(action).alias("action"),
                     lit(status).alias("final_status"), lit(note).alias("note"))


# ---------------------------------------------------------------------------------------------
# One table
# ---------------------------------------------------------------------------------------------

def write_log_parts(parts, out_log: str) -> None:
    """Append cleaning-log rows to HDFS, one small job per part."""
    for part in parts:
        part.select(*LOG_COLUMNS).coalesce(1).write.mode("append").partitionBy("table").parquet(out_log)


def clean_table(spark, d: DQData, cfg: dict, viol, table: str, mode: str, log):
    P = cfg["params"]
    rules = [r for r in cfg["rules"] if r["table"] == table and r["check"] not in ("duplicate_key", "missing_parent")]
    dup_rules = [r for r in cfg["rules"] if r["table"] == table and r["check"] == "duplicate_key"]
    child_rules = [r for r in cfg["rules"] if r["check"] == "missing_parent" and table in r["params"]["child_tables"]]
    all_rules = rules + child_rules
    schema_cols = [f.name for f in SCHEMAS[table].fields]
    original = F.to_json(F.struct(*schema_cols))        # full original record (evaluated only where used)
    m, log_parts = {"table": table, "rules": {}}, []

    # ---- 1. rows in ----------------------------------------------------------------------
    base = d.table(table).withColumn("record_key", key_expr(table))
    m["rows_parquet"] = base.count()
    q_in = d.quarantine(table) if FORMATS[table] in ("csv", "jsonl", "json") else None
    m["rows_ingestion_quarantine"] = q_in.count() if q_in is not None else 0
    m["rows_in"] = m["rows_parquet"] + m["rows_ingestion_quarantine"]

    # ---- 2. duplicates ------------------------------------------------------------------------
    removed_n, conflict_part = 0, None
    for r in dup_rules:
        h = base.withColumn("_h", F.xxhash64(*schema_cols))
        g = h.groupBy("record_key").agg(F.count("*").alias("_n"), F.countDistinct("_h").alias("_v"))
        h = h.join(g, "record_key").withColumn(
            "_rn", F.row_number().over(Window.partitionBy("record_key").orderBy("_h", "_source_file")))
        removed = h.filter((F.col("_v") == 1) & (F.col("_rn") > 1))
        conflict = h.filter(F.col("_v") > 1)
        removed_n, conflict_n = removed.count(), conflict.count()
        log_parts.append(log_rows(removed, table, r["id"], r["defect_type"], ",".join(primary_key(table)), original,
                                  None, "remove", "removed", "identical copy of a kept row"))
        log_parts.append(log_rows(conflict, table, r["id"], r["defect_type"], ",".join(primary_key(table)), original,
                                  None, "quarantine", "quarantined", "conflicting copies of one key"))
        conflict_part = conflict.select("record_key", F.array(F.lit(r["id"])).alias("rules"), original.alias("original_record"))
        m["rules"][r["id"]] = {"hits": int(removed_n + conflict_n), "remove": int(removed_n), "quarantine": int(conflict_n)}
        base = h.filter((F.col("_v") == 1) & (F.col("_rn") == 1)).drop("_h", "_n", "_v", "_rn")

    # ---- 3. mark rows hit by each rule ------------------------------------------------------------
    for r in all_rules:
        v = (viol.filter(F.col("rule_id") == r["id"]).select(F.col("record_key").alias("_vk")).distinct()
             .withColumn(f"_hit_{r['id']}", F.lit(True)))
        if r in child_rules:
            on = F.col(r["params"]["child_column"]) == F.col("_vk")
        elif r["check"] == "sequence_integrity":
            base = base.withColumn("_gk", F.concat_ws("|", *[F.col(c).cast("string") for c in r["params"]["group_by"]]))
            on = F.col("_gk") == F.col("_vk")
        else:
            on = F.col("record_key") == F.col("_vk")
        base = (base.join(F.broadcast(v), on, "left").drop("_vk", "_gk")
                .withColumn(f"_hit_{r['id']}", F.coalesce(f"_hit_{r['id']}", F.lit(False))))

    # ---- 4. corrections and effective actions --------------------------------------------------------
    for r in all_rules:
        if r["action"] == "correct":
            base = apply_correction(base, d, r, P)
    for r in all_rules:
        hit = F.col(f"_hit_{r['id']}")
        eff = (F.when(hit & F.col(f"_fix_{r['id']}"), "correct").when(hit, r.get("fallback", "flag"))
               if r["action"] == "correct" else F.when(hit, r["action"]))
        base = base.withColumn(f"_act_{r['id']}", eff)

    def rule_list(action):
        """array<string> of the rule IDs whose effective action for the row is `action`."""
        if not all_rules:
            return empty_flags()
        return F.array_compact(F.array(*[F.when(F.col(f"_act_{r['id']}") == action, F.lit(r["id"])) for r in all_rules]))

    base = (base.withColumn("_q", rule_list("quarantine")).withColumn("dq_flags", rule_list("flag"))
            .withColumn("_c", rule_list("correct"))
            .withColumn("_status", F.when(F.size("_q") > 0, "quarantined").when(F.size("dq_flags") > 0, "flagged")
                        .when(F.size("_c") > 0, "corrected").otherwise("clean"))
            .persist(StorageLevel.MEMORY_AND_DISK))

    # clean projection: corrected values replace originals (originals stay in `base` for the log)
    clean_cols = {c: F.col(c) for c in schema_cols}
    for r in all_rules:
        if r["action"] == "correct":
            for c in target_columns(r):
                clean_cols[c] = F.when(F.col(f"_act_{r['id']}") == "correct",
                                       F.col(f"_new_{c}").cast(SCHEMAS[table][c].dataType)).otherwise(clean_cols[c])

    for r in all_rules:
        a = F.col(f"_act_{r['id']}")
        cols = log_columns(r, table)
        orig = F.concat_ws(",", *[F.col(c).cast("string") for c in cols])
        new = (F.when(a == "correct", F.concat_ws(",", *[F.col(f"_new_{c}").cast("string") for c in cols]))
               if r["action"] == "correct" else F.lit(None).cast("string"))
        if r["action"] == "correct":
            note = F.when(a != "correct", F.lit(f"correction not possible -> {r.get('fallback', 'flag')}"))
            if r["correction"]["method"] == "resequence":
                note = F.coalesce(note, F.lit("renumbered in distance order; a missing stop cannot be restored"))
        else:
            note = F.lit(None).cast("string")
        hits = base.filter(a.isNotNull())
        log_parts.append(log_rows(hits, table, r["id"], r["defect_type"], ",".join(cols), orig, new, a,
                                  F.col("_status"), note))
        counts = {row["a"]: row["n"] for row in hits.groupBy(a.alias("a")).agg(F.count("*").alias("n")).collect()}
        m["rules"][r["id"]] = {"hits": int(sum(counts.values())), **{k: int(v) for k, v in counts.items()}}

    clean_part = base.filter(F.col("_status") != "quarantined").select(
        *[e.alias(c) for c, e in clean_cols.items()], "_source_file", "dq_flags")
    quar_part = base.filter(F.col("_status") == "quarantined").select(
        "record_key", F.col("_q").alias("rules"), original.alias("original_record"))
    if conflict_part is not None:
        quar_part = quar_part.unionByName(conflict_part)

    # ---- 5. rows quarantined at ingestion: recover them with `correct` rules where possible -----------
    m["recovered_from_ingestion_quarantine"] = 0
    if m["rows_ingestion_quarantine"] > 0:
        typed = typed_from_strings(q_in, table).withColumn("_fixed", empty_flags())
        failed = F.split("failed_columns", ",")
        fixable = [r for r in rules if r["action"] == "correct"
                   and r["correction"]["method"] in ("minutes_between", "lookup", "swap_coordinates")]
        for r in fixable:
            cols = target_columns(r)
            typed = typed.withColumn(f"_hit_{r['id']}", F.arrays_overlap(failed, F.array(*[F.lit(c) for c in cols])))
            typed = apply_correction(typed, d, r, P)
            for c in cols:
                typed = typed.withColumn(c, F.when(F.col(f"_fix_{r['id']}"), F.col(f"_new_{c}").cast(SCHEMAS[table][c].dataType))
                                         .otherwise(F.col(c)))
            typed = typed.withColumn("_fixed", F.when(F.col(f"_fix_{r['id']}"),
                                                      F.array_union("_fixed", F.array(*[F.lit(c) for c in cols]))).otherwise(F.col("_fixed")))
        typed = typed.withColumn("_ok", F.size(F.array_except(failed, "_fixed")) == 0).persist(StorageLevel.MEMORY_AND_DISK)
        rec, still = typed.filter("_ok"), typed.filter(~F.col("_ok"))
        m["recovered_from_ingestion_quarantine"] = rec.count()
        clean_part = clean_part.unionByName(rec.withColumn("dq_flags", empty_flags()).select(*schema_cols, "_source_file", "dq_flags"))
        for r in fixable:
            c0 = target_columns(r)[0]
            fixed = rec.filter(F.col(f"_fix_{r['id']}"))
            log_parts.append(log_rows(fixed, table, r["id"], r["defect_type"], c0, F.col("raw_record"), F.col(c0).cast("string"),
                                      "correct", "corrected", "recovered from ingestion quarantine"))
            m["rules"].setdefault(r["id"], {"hits": 0})["recovered_from_ingestion_quarantine"] = int(fixed.count())
        rule_map = viol.filter(F.col("table") == table).select(F.col("record_key").alias("_k"), "rule_id")
        still_rules = (still.select("record_key", "raw_record", "failed_columns")
                       .join(rule_map, F.col("record_key") == F.col("_k"), "left")
                       .groupBy("record_key", "raw_record", "failed_columns")
                       .agg(F.array_compact(F.collect_set("rule_id")).alias("rules")))
        still_rules = still_rules.withColumn(
            "rules", F.when(F.size("rules") > 0, F.col("rules")).otherwise(F.array(F.lit("INGESTION_TYPE_FAILURE"))))
        quar_part = quar_part.unionByName(still_rules.select("record_key", "rules", F.col("raw_record").alias("original_record")))
        log_parts.append(log_rows(still_rules.withColumn("rule_id", F.explode("rules")), table, F.col("rule_id"), None,
                                  F.col("failed_columns"), F.col("raw_record"), None, "quarantine", "quarantined",
                                  "type failure at ingestion, not repairable"))

    # ---- 6. write outputs and reconcile --------------------------------------------------------------
    write_log_parts(log_parts, hdfs_uri(mode, "cleaning_log"))
    out_clean, out_q = hdfs_uri(mode, "clean", table), hdfs_uri(mode, "clean_quarantine", table)
    if table in PARTITIONS:
        name, make_expr = PARTITIONS[table]
        clean_part.withColumn(name, make_expr()).repartition(name).write.mode("overwrite").partitionBy(name).parquet(out_clean)
    else:
        clean_part.coalesce(1).write.mode("overwrite").parquet(out_clean)
    quar_part.withColumn("table", F.lit(table)).coalesce(1).write.mode("overwrite").parquet(out_q)

    clean_back, q_back = spark.read.parquet(out_clean), spark.read.parquet(out_q)
    m["rows_clean"] = clean_back.count()
    m["rows_removed"] = int(removed_n)
    m["rows_quarantined"] = q_back.count()
    m["rows_flagged"] = clean_back.filter(F.size("dq_flags") > 0).count()
    m["rows_corrected"] = base.filter(F.col("_status") == "corrected").count() + m["recovered_from_ingestion_quarantine"]
    m["reconciled"] = m["rows_in"] == m["rows_clean"] + m["rows_removed"] + m["rows_quarantined"]
    fp = lambda df, cols: str(df.select(F.sum(F.xxhash64(*cols).cast("decimal(38,0)"))).first()[0] or 0)  # noqa: E731
    m["fingerprint_clean"] = fp(clean_back, schema_cols + ["dq_flags"])
    m["fingerprint_quarantine"] = fp(q_back, ["record_key", "original_record", "rules"])
    base.unpersist()
    log.info(f"{table}: in={m['rows_in']:,} clean={m['rows_clean']:,} removed={m['rows_removed']:,} "
             f"quarantined={m['rows_quarantined']:,} (flagged {m['rows_flagged']:,}, corrected {m['rows_corrected']:,}) "
             f"reconciled={m['reconciled']}")
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="full")
    ap.add_argument("--tables", nargs="*", help="subset of tables (default: all 12)")
    args = ap.parse_args()
    log, log_path = get_logger(f"clean_data_{args.mode}")
    cfg = load_dq_config()
    spark = get_spark("clean-data")
    d = DQData(spark, args.mode)
    viol = spark.read.parquet(hdfs_uri(args.mode, "dq", "violations")).persist(StorageLevel.MEMORY_AND_DISK)
    t0 = time.perf_counter()
    out_log = hdfs_uri(args.mode, "cleaning_log")
    # the log is appended table by table, so start each run from an empty folder (idempotent)
    subprocess.run(["hdfs", "dfs", "-rm", "-r", "-f", "-skipTrash", out_log], check=True, capture_output=True)
    metrics = []
    for table in (args.tables or list(SCHEMAS)):
        metrics.append(clean_table(spark, d, cfg, viol, table, args.mode, log))
    clog_back = spark.read.parquet(out_log)
    log_counts = [{"table": r["table"], "rule_id": r["rule_id"], "action": r["action"], "rows": r["n"]}
                  for r in clog_back.groupBy("table", "rule_id", "action").agg(F.count("*").alias("n"))
                  .orderBy("table", "rule_id", "action").collect()]
    log_fp = str(clog_back.select(F.sum(F.xxhash64(*LOG_COLUMNS).cast("decimal(38,0)"))).first()[0] or 0)

    mv = cfg["params"]["minimum_volumes"]
    minimums = {}
    if args.mode in mv["apply_to_modes"] and not args.tables:
        clean_rows = {m["table"]: m["rows_clean"] for m in metrics}
        minimums = {t: {"minimum": v, "clean_rows": clean_rows[t], "ok": clean_rows[t] >= v} for t, v in mv["tables"].items()}
    ok = all(m["reconciled"] for m in metrics) and all(v["ok"] for v in minimums.values())
    secs = round(time.perf_counter() - t0, 1)
    out = PROJECT_ROOT / "reports" / f"cleaning_metrics_{args.mode}.json"
    out.write_text(json.dumps({"mode": args.mode, "seconds": secs, "log_file": str(log_path.relative_to(PROJECT_ROOT)),
                               "all_reconciled": all(m["reconciled"] for m in metrics), "minimums": minimums,
                               "cleaning_log_rows": clog_back.count(), "cleaning_log_fingerprint": log_fp,
                               "cleaning_log_counts": log_counts, "tables": metrics}, indent=2), encoding="utf-8")
    log.info(f"CLEANING {'PASS' if ok else 'FAIL'} in {secs}s -> {out.relative_to(PROJECT_ROOT)}")
    spark.stop()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
