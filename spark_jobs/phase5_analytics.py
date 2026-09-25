"""Phase 5: run the Spark SQL analytics in spark_sql/analytics/ and write them to HDFS.

Every .sql file starts with a small header that tells this job what to do with it:

    -- name: <view or output name>
    -- kind: view | output | both   (view = temp view only; output = HDFS Parquet; both = both)
    -- item: <Phase 5 item number, 0 = shared helper>
    -- cache: true                  (optional; cache a heavily reused view)
    -- partitions: 4                (optional; output file count)

Files run in filename order, so later analyses can query earlier results by name.
`${placeholders}` are filled from config/phase5.yaml, config/thresholds.yaml and
config/phase4.yaml, so no threshold is hard-coded in SQL.

Laravel analogy: the SQL files are the queries (think Eloquent scopes kept in one folder)
and this job is the Artisan command that runs them in order, persists each result to
/urbantransit/analytics/<name> and records row counts in reports/phase5_metrics.json.

Usage: python spark_jobs/phase5_analytics.py [--only name1,name2]
  --only re-runs just those outputs; other outputs are read back from HDFS.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from string import Template

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spark_jobs.common import PROJECT_ROOT, get_logger, get_spark, hdfs_file_count, hdfs_uri

SQL_DIR = PROJECT_ROOT / "spark_sql" / "analytics"
FEATURE_TABLES = ("trip_features", "route_features", "route_time_features", "stop_daily_demand", "route_daily_demand")
# Clean (Phase 3) tables needed only for facts the feature tables do not carry at the right
# grain: ticket O-D stops, stop-level delay records, route geometry, calendar and vehicle types.
CLEAN_TABLES = ("tickets", "delays", "route_stops", "stops", "routes", "vehicles", "service_calendar", "passengers",
                "passenger_counts")


def load_yaml(name):
    return yaml.safe_load((PROJECT_ROOT / "config" / name).read_text(encoding="utf-8"))


def flatten(prefix, value, out):
    """Flatten nested config into ${section_key} placeholders (scalars only)."""
    if isinstance(value, dict):
        for k, v in value.items():
            flatten(f"{prefix}_{k}" if prefix else k, v, out)
    elif not isinstance(value, list):
        out[prefix] = value


def sql_list(values):
    return ", ".join(f"'{v}'" for v in values)


def period_case(cfg, col):
    """CASE expression mapping an hour column to the configured time period."""
    whens = " ".join(f"WHEN {col} BETWEEN {p['from_hour']} AND {p['to_hour']} THEN '{p['name']}'" for p in cfg["time_periods"])
    return f"CASE {whens} END"


def build_params():
    """All ${placeholders} available to the SQL files."""
    p5, thr, p4 = load_yaml("phase5.yaml"), load_yaml("thresholds.yaml"), load_yaml("phase4.yaml")
    params = {}
    flatten("", {k: v for k, v in p5.items() if k != "time_periods"}, params)
    flatten("bunching", thr["bunching"], params)
    flatten("peak_detection", thr["peak_detection"], params)
    params["on_time_early_min"] = p4["delay"]["on_time_early_min"]
    params["on_time_late_min"] = p4["delay"]["on_time_late_min"]
    # thresholds.yaml: a vehicle falls into the first category whose max_ratio >= its load.
    cats = thr["occupancy_categories"]
    whens = " ".join(f"WHEN t.occupancy_pct <= {c['max_ratio']} THEN '{c['name']}'" for c in cats if c["max_ratio"] is not None)
    last = next(c["name"] for c in cats if c["max_ratio"] is None)
    params["occupancy_case"] = f"CASE WHEN t.occupancy_pct IS NULL THEN NULL {whens} ELSE '{last}' END"
    params["category_count_columns"] = ",\n       ".join(
        f"sum(CASE WHEN occupancy_category = '{c['name']}' THEN 1 ELSE 0 END) AS {c['name'].lower()}_trips" for c in cats)
    params["overload_list"] = sql_list(p5["overcrowding"]["overload_categories"])
    params["underload_list"] = sql_list(p5["overcrowding"]["underload_categories"])
    params["time_period_case_trip"] = period_case(p5, "t.hour")
    params["time_period_case_entry"] = period_case(p5, "hour(k.entry_time)")
    params["time_period_case_exit"] = period_case(p5, "hour(k.exit_time)")
    params["period_hours_case"] = "CASE time_period " + " ".join(
        f"WHEN '{p['name']}' THEN {p['to_hour'] - p['from_hour'] + 1}" for p in p5["time_periods"]) + " END"
    bands = p5["delay"]["distance_bands_km"]
    edges = [0] + bands
    params["distance_band_case"] = "CASE " + " ".join(
        f"WHEN distance_km < {hi} THEN '{lo:02d}-{hi:02d} km'" for lo, hi in zip(edges, bands)) + f" ELSE '{bands[-1]:02d}+ km' END"
    params["on_time_band"] = f"{params['on_time_early_min']} < x < {params['on_time_late_min']}"
    return p5, params


def parse(path, params):
    """Split a SQL file into (header dict, rendered SQL)."""
    text = path.read_text(encoding="utf-8")
    header = dict(re.findall(r"^--\s*(name|kind|item|cache|partitions):\s*(\S+)", text, flags=re.M))
    sql = Template(text).substitute(params)  # KeyError on an unknown placeholder: fail fast
    return header, sql


def hdfs_rm(path):
    subprocess.run(["hdfs", "dfs", "-rm", "-r", "-f", path], check=False, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated output names to recompute")
    only = {n for n in ap.parse_args().only.split(",") if n}
    p5, params = build_params()
    log, _ = get_logger("phase5_analytics")
    spark = get_spark("phase5-analytics")
    for t in FEATURE_TABLES:
        spark.read.parquet(hdfs_uri("full", "features", t)).createOrReplaceTempView(t)
    for t in CLEAN_TABLES:
        spark.read.parquet(hdfs_uri("full", "clean", t)).createOrReplaceTempView(t)

    metrics_path = PROJECT_ROOT / "reports" / "phase5_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() and only else {}
    for path in sorted(SQL_DIR.glob("*.sql")):
        header, sql = parse(path, params)
        name, kind = header["name"], header.get("kind", "output")
        if kind == "view":
            df = spark.sql(sql)
            df.createOrReplaceTempView(name)
            if header.get("cache") == "true":
                spark.sql(f"CACHE TABLE {name}")
            log.info("view %-32s ready", name)
            continue
        out = hdfs_uri("full", "analytics", name)
        if only and name not in only:
            spark.read.parquet(out).createOrReplaceTempView(name)  # reuse the stored result
            continue
        t0 = time.perf_counter()
        parts = int(header.get("partitions", p5["output_partitions"]))
        hdfs_rm(out)
        spark.sql(sql).coalesce(parts).write.mode("overwrite").parquet(out)
        back = spark.read.parquet(out)
        back.createOrReplaceTempView(name)  # later files read the persisted result
        metrics[name] = {"item": int(header.get("item", 0)), "file": path.name, "path": out, "rows": back.count(),
                         "files": hdfs_file_count(out), "seconds": round(time.perf_counter() - t0, 1)}
        log.info("output %-32s rows=%-9d %.1fs", name, metrics[name]["rows"], metrics[name]["seconds"])
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    log.info("PHASE5 ANALYTICS DONE: %d outputs", len(metrics))
    spark.stop()


if __name__ == "__main__":
    main()
