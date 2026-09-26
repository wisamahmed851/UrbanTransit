"""Load the Phase 5 analytics tables (and optionally the reference tables) from HDFS into MySQL.

Run inside WSL from the repo root, with HDFS started and the venv active:

    python database/load_analytics_to_mysql.py                     # all 30 analytics tables
    python database/load_analytics_to_mysql.py --tables od_matrix  # just some
    python database/load_analytics_to_mysql.py --reference         # also routes/stops/vehicles (only if empty)
    python database/load_analytics_to_mysql.py --network --tables none   # only route_stops + gps_events (map)

For each table:
1. Read `hdfs:///urbantransit/analytics/<table>` and compare its schema with
   `src.models.analytics.ANALYTICS_SCHEMAS` (names, order and Spark types). Any difference
   stops that table: the MySQL definition would no longer match the data.
2. In one transaction: delete the old MySQL rows, then insert the Parquet rows in batches.
   A failure rolls back, so the previous load stays intact (all-or-nothing per table).
3. Reconcile three counts: the Phase 5 run (`reports/phase5_metrics.json`), the Parquet
   read now, and `SELECT COUNT(*)` in MySQL after the load.

Results go to `reports/mysql_load_report.json` and `reports/processing_logs/`.
Laravel analogy: an Artisan command that runs a seeder from an external source.

Network tables (`--network`): `route_stops` and the 7-day `gps_events` sample from the Phase 3
clean Parquet, for the map. Besides row counts, GPS is reconciled on its first/last ping time
and number of vehicles, which would expose any timezone shift of the timestamps.

Reference tables are a working copy that admins can edit, so they are loaded only when
`--reference` is given, and only into empty tables unless `--force-reference` is also given.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, select  # noqa: E402

from spark_jobs.common import PROJECT_ROOT, get_logger, get_spark, hdfs_uri  # noqa: E402
from src.app import create_app  # noqa: E402
from src.extensions import db  # noqa: E402
from src.models.analytics import ANALYTICS_SCHEMAS, ANALYTICS_TABLES  # noqa: E402
from src.models.network import GpsEvent, RouteStop  # noqa: E402
from src.models.reference import Route, Stop, Vehicle  # noqa: E402

REPORT_PATH = PROJECT_ROOT / "reports" / "mysql_load_report.json"
PHASE5_METRICS = PROJECT_ROOT / "reports" / "phase5_metrics.json"
# Parent tables first when inserting (routes reference stops); reversed when deleting.
REFERENCE_ORDER = [("stops", Stop), ("routes", Route), ("vehicles", Vehicle)]
REFERENCE_SKIPPED_COLUMNS = {"_source_file"}   # raw-file lineage; not an attribute of the entity


def expected_phase5_rows() -> dict[str, int]:
    """Row counts recorded by the Phase 5 run, i.e. the numbers from the audit."""
    data = json.loads(PHASE5_METRICS.read_text(encoding="utf-8"))
    return {name: v["rows"] for name, v in data.items() if isinstance(v, dict) and "rows" in v}


def schema_of(df) -> list[tuple[str, str]]:
    return [(f.name, f.dataType.simpleString()) for f in df.schema.fields]


def replace_rows(table, rows_iter, batch_size: int, transform=None) -> int:
    """Delete everything in `table`, insert `rows_iter` in batches, commit once. Returns rows inserted."""
    inserted = 0
    with db.engine.begin() as conn:            # one transaction: rollback on any error
        conn.execute(delete(table))
        batch = []
        for row in rows_iter:
            record = row.asDict()
            batch.append(transform(record) if transform else record)
            if len(batch) >= batch_size:
                conn.execute(table.insert(), batch)
                inserted += len(batch)
                batch = []
        if batch:
            conn.execute(table.insert(), batch)
            inserted += len(batch)
    return inserted


def mysql_count(table) -> int:
    with db.engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar_one()


def load_analytics(spark, log, names: list[str], expected: dict[str, int], batch_size: int) -> list[dict]:
    results = []
    for name in names:
        t0 = time.perf_counter()
        entry = {"table": name, "group": "analytics", "expected_rows": expected.get(name)}
        df = spark.read.parquet(hdfs_uri("full", "analytics", name))
        live = schema_of(df)
        if live != ANALYTICS_SCHEMAS[name]:
            entry.update(status="schema_mismatch",
                         detail={"parquet": live, "spec": ANALYTICS_SCHEMAS[name]})
            log.error("%s: Parquet schema differs from the MySQL spec; not loaded", name)
            results.append(entry)
            continue
        entry["hdfs_rows"] = df.count()
        entry["inserted"] = replace_rows(ANALYTICS_TABLES[name], df.toLocalIterator(), batch_size)
        entry["mysql_rows"] = mysql_count(ANALYTICS_TABLES[name])
        entry["seconds"] = round(time.perf_counter() - t0, 1)
        counts = {entry["expected_rows"], entry["hdfs_rows"], entry["mysql_rows"]}
        entry["status"] = "ok" if len(counts) == 1 else "count_mismatch"
        log.info("%-26s expected=%-9s hdfs=%-9s mysql=%-9s %s (%.1f s)", name, entry["expected_rows"],
                 entry["hdfs_rows"], entry["mysql_rows"], entry["status"], entry["seconds"])
        results.append(entry)
    return results


def load_reference(spark, log, force: bool, batch_size: int) -> list[dict]:
    """Copy routes/stops/vehicles from the Phase 3 clean Parquet into MySQL."""
    tables = {name: model.__table__ for name, model in REFERENCE_ORDER}
    non_empty = [n for n, t in tables.items() if mysql_count(t) > 0]
    if non_empty and not force:
        log.warning("Reference tables already hold data (%s); skipped. Use --force-reference to overwrite admin edits.",
                    ", ".join(non_empty))
        return [{"table": n, "group": "reference", "status": "skipped_not_empty"} for n in tables]

    frames = {}
    for name, model in REFERENCE_ORDER:
        df = spark.read.parquet(hdfs_uri("full", "clean", name))
        parquet_cols = [c for c in df.columns if c not in REFERENCE_SKIPPED_COLUMNS]
        mysql_cols = [c.name for c in tables[name].columns]
        if parquet_cols != mysql_cols:
            raise SystemExit(f"{name}: clean Parquet columns {parquet_cols} != MySQL columns {mysql_cols}")
        frames[name] = df.select(*parquet_cols)

    with db.engine.begin() as conn:            # children first, so the FK never dangles
        for name, _ in reversed(REFERENCE_ORDER):
            conn.execute(delete(tables[name]))

    results = []
    for name, _ in REFERENCE_ORDER:
        t0 = time.perf_counter()
        df = frames[name]
        entry = {"table": name, "group": "reference", "expected_rows": None, "hdfs_rows": df.count()}
        entry["inserted"] = replace_rows(tables[name], df.toLocalIterator(), batch_size,
                                         transform=lambda r: {**r, "dq_flags": list(r["dq_flags"] or [])})
        entry["mysql_rows"] = mysql_count(tables[name])
        entry["seconds"] = round(time.perf_counter() - t0, 1)
        entry["status"] = "ok" if entry["hdfs_rows"] == entry["mysql_rows"] else "count_mismatch"
        log.info("%-26s hdfs=%-9s mysql=%-9s %s", name, entry["hdfs_rows"], entry["mysql_rows"], entry["status"])
        results.append(entry)
    return results


def load_network(spark, log, batch_size: int) -> list[dict]:
    """Replace route_stops and gps_events with the clean Parquet (routes/stops must be loaded)."""
    from pyspark.sql import functions as F

    results = []
    for name, model in (("route_stops", RouteStop), ("gps_events", GpsEvent)):
        t0 = time.perf_counter()
        table = model.__table__
        df = spark.read.parquet(hdfs_uri("full", "clean", name))
        cols = [c for c in df.columns if c not in REFERENCE_SKIPPED_COLUMNS]
        if cols != [c.name for c in table.columns]:
            raise SystemExit(f"{name}: clean Parquet columns {cols} != MySQL columns {[c.name for c in table.columns]}")
        df = df.select(*cols)
        entry = {"table": name, "group": "network", "expected_rows": None, "hdfs_rows": df.count()}
        entry["inserted"] = replace_rows(table, df.toLocalIterator(), batch_size,
                                         transform=lambda r: {**r, "dq_flags": list(r["dq_flags"] or [])})
        entry["mysql_rows"] = mysql_count(table)
        ok = entry["hdfs_rows"] == entry["mysql_rows"]
        if name == "gps_events":
            s_ = df.agg(F.min("event_time").alias("a"), F.max("event_time").alias("b"),
                        F.countDistinct("vehicle_id").alias("v")).first()
            with db.engine.connect() as conn:
                m_ = conn.execute(select(func.min(table.c.event_time), func.max(table.c.event_time),
                                         func.count(table.c.vehicle_id.distinct()))).one()
            entry["time_window"] = {"hdfs": [str(s_["a"]), str(s_["b"])], "mysql": [str(m_[0]), str(m_[1])]}
            entry["vehicles"] = {"hdfs": s_["v"], "mysql": m_[2]}
            ok = ok and s_["a"] == m_[0] and s_["b"] == m_[1] and s_["v"] == m_[2]
        entry["seconds"] = round(time.perf_counter() - t0, 1)
        entry["status"] = "ok" if ok else "count_mismatch"
        log.info("%-26s hdfs=%-9s mysql=%-9s %s (%.1f s) %s", name, entry["hdfs_rows"], entry["mysql_rows"],
                 entry["status"], entry["seconds"], entry.get("time_window", ""))
        results.append(entry)
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tables", help="comma-separated analytics tables (default: all 30)")
    ap.add_argument("--reference", action="store_true", help="also load routes/stops/vehicles (only into empty tables)")
    ap.add_argument("--force-reference", action="store_true", help="overwrite non-empty reference tables")
    ap.add_argument("--network", action="store_true", help="also load route_stops + gps_events (map)")
    ap.add_argument("--batch-size", type=int, default=5000)
    args = ap.parse_args()

    names = [] if args.tables == "none" else args.tables.split(",") if args.tables else list(ANALYTICS_SCHEMAS)
    unknown = [n for n in names if n not in ANALYTICS_SCHEMAS]
    if unknown:
        raise SystemExit(f"Unknown analytics tables: {unknown}")

    log, log_path = get_logger("load_analytics_to_mysql")
    spark = get_spark("load-analytics-to-mysql")
    app = create_app()
    started = datetime.now(timezone.utc)
    with app.app_context():
        results = load_analytics(spark, log, names, expected_phase5_rows(), args.batch_size)
        if args.reference or args.force_reference:
            results += load_reference(spark, log, args.force_reference, args.batch_size)
        if args.network:
            results += load_network(spark, log, max(args.batch_size, 10000))
    spark.stop()

    failed = [r["table"] for r in results if r["status"] not in ("ok", "skipped_not_empty")]
    report = {
        "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "log": str(log_path.relative_to(PROJECT_ROOT)),
        "tables": results,
        "failed": failed,
        "result": "PASS" if not failed else "FAIL",
    }
    if args.tables and REPORT_PATH.exists():   # partial run: keep the other tables' last results
        previous = {r["table"]: r for r in json.loads(REPORT_PATH.read_text(encoding="utf-8"))["tables"]}
        previous.update({r["table"]: r for r in results})
        report["tables"] = list(previous.values())
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log.info("LOAD %s: %d tables, failed=%s, report=%s", report["result"], len(results), failed, REPORT_PATH.name)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
