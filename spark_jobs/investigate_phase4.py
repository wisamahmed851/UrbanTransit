"""One-off Phase 4 investigation: ticket orphans, negative headways, delay coverage.

Results go to reports/phase4_investigation.json and back the decisions in
documentation/feature_catalog.md (items 3, 7 and 8 of CMD-015).
"""
import json
import sys
from pathlib import Path

from pyspark.sql import functions as F
from pyspark.sql.window import Window

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spark_jobs.common import PROJECT_ROOT, get_spark, hdfs_uri


def main():
    spark = get_spark("investigate-phase4")
    t = lambda n: spark.read.parquet(hdfs_uri("full", "clean", n))
    q = lambda n: spark.read.parquet(hdfs_uri("full", "clean_quarantine", n))
    tickets, passengers, trips, delays = t("tickets"), t("passengers"), t("trips"), t("delays")
    out = {"schemas": {n: t(n).columns for n in ("trips", "delays", "tickets", "passenger_counts")}}

    # --- 7. ticket orphans vs the Phase 3 flags that should explain them
    no_pax = tickets.filter(F.col("passenger_id").isNotNull()).join(passengers.select("passenger_id"), "passenger_id", "left_anti")
    no_trip = tickets.filter(F.col("trip_id").isNotNull()).join(trips.select("trip_id"), "trip_id", "left_anti")
    out["ticket_orphans"] = {
        "no_passenger": no_pax.count(),
        "no_passenger_flagged_DQ15": no_pax.filter(F.array_contains("dq_flags", "DQ15")).count(),
        "no_trip": no_trip.count(),
        "no_trip_flagged_DQ16": no_trip.filter(F.array_contains("dq_flags", "DQ16")).count(),
        "tickets_flag_counts": {r["f"]: r["count"] for r in tickets.select(F.explode("dq_flags").alias("f")).groupBy("f").count().collect()},
        "no_trip_sample_ids": [r[0] for r in no_trip.select("trip_id").limit(5).collect()],
    }

    # --- 8. negative headway anatomy
    w = Window.partitionBy("route_id", "service_date").orderBy("scheduled_departure", "trip_id")
    cols = [c for c in ("direction", "schedule_id") if c in trips.columns]
    h = (trips.withColumn("prev_dep", F.lag("actual_departure").over(w))
         .withColumn("prev_sched", F.lag("scheduled_departure").over(w))
         .withColumn("prev_trip", F.lag("trip_id").over(w))
         .withColumn("hw", (F.unix_timestamp("actual_departure") - F.unix_timestamp("prev_dep")) / 60)
         .withColumn("sched_hw", (F.unix_timestamp("scheduled_departure") - F.unix_timestamp("prev_sched")) / 60)
         .withColumn("dep_dev", (F.unix_timestamp("actual_departure") - F.unix_timestamp("scheduled_departure")) / 60)
         .withColumn("prev_dev", (F.unix_timestamp("prev_dep") - F.unix_timestamp("prev_sched")) / 60)
         .withColumn("crosses_midnight", F.to_date("scheduled_departure") != F.col("service_date")))
    neg = h.filter("hw < 0")
    out["headway"] = {
        "rows_with_headway": h.filter("hw is not null").count(),
        "negative": neg.count(),
        "negative_crossing_midnight": neg.filter("crosses_midnight").count(),
        "negative_summary": [r.asDict() for r in neg.select("hw", "sched_hw", "dep_dev", "prev_dev").summary("min", "25%", "50%", "75%", "max").collect()],
        "negative_where_prev_departed_late": neg.filter("prev_dev > sched_hw").count(),
        "zero_sched_headway": h.filter("sched_hw = 0").count(),
        "direction_column_present": "direction" in trips.columns,
    }
    if "direction" in trips.columns:
        wd = Window.partitionBy("route_id", "service_date", "direction").orderBy("scheduled_departure", "trip_id")
        hd = trips.withColumn("hw", (F.unix_timestamp("actual_departure") - F.unix_timestamp(F.lag("actual_departure").over(wd))) / 60)
        out["headway"]["negative_if_partitioned_by_direction"] = hd.filter("hw < 0").count()
        out["headway"]["rows_with_headway_by_direction"] = hd.filter("hw is not null").count()
        wo = Window.partitionBy("route_id", "service_date", "direction").orderBy("actual_departure", "trip_id")
        ho = trips.filter("actual_departure is not null").withColumn("hw", (F.unix_timestamp("actual_departure") - F.unix_timestamp(F.lag("actual_departure").over(wo))) / 60)
        out["headway"]["actual_order_by_direction_min_max"] = [ho.agg(F.min("hw")).first()[0], ho.agg(F.max("hw")).first()[0]]

    # --- 3. delay coverage
    dtrips = delays.select("trip_id").distinct()
    status_col = next((c for c in ("trip_status", "status") if c in trips.columns), None)
    out["delay"] = {
        "trips": trips.count(),
        "trips_actual_departure_null": trips.filter("actual_departure is null").count(),
        "trips_with_delay_record": trips.join(dtrips, "trip_id", "left_semi").count(),
        "delay_reason_counts": {r[0]: r[1] for r in delays.groupBy("delay_reason").count().collect()},
        "status_col": status_col,
        "status_counts": {str(r[0]): r[1] for r in trips.groupBy(status_col).count().collect()} if status_col else None,
    }
    try:
        qd = q("delays")
        out["delay"]["quarantined_delay_rows"] = qd.count()
        out["delay"]["quarantined_delay_trips_without_clean_record"] = (
            qd.select("trip_id").distinct().join(dtrips, "trip_id", "left_anti").join(trips.select("trip_id"), "trip_id", "left_semi").count())
    except Exception as e:  # noqa: BLE001
        out["delay"]["quarantine_error"] = str(e)[:200]
    try:
        qp = q("passenger_counts")
        pct = t("passenger_counts").select("trip_id").distinct()
        out["pc_quarantine_trips_without_clean_record"] = (
            qp.select("trip_id").distinct().join(pct, "trip_id", "left_anti").join(trips.select("trip_id"), "trip_id", "left_semi").count())
    except Exception as e:  # noqa: BLE001
        out["pc_quarantine_error"] = str(e)[:200]

    (PROJECT_ROOT / "reports" / "phase4_investigation.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps(out, indent=2, default=str))
    spark.stop()


if __name__ == "__main__":
    main()
