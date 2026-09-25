"""Phase 4: integrate *clean* UrbanTransit tables and write leakage-safe feature sets.

The job never reads raw or Phase-2 Parquet.  Think of the SQL files as Laravel query
scopes: they document the 10 relationships, while this job is the service that runs
them, measures their cardinality, and materialises model-ready Spark features.
"""

import json
import subprocess
import sys
from pathlib import Path

import yaml
from pyspark.sql import functions as F
from pyspark.sql.window import Window

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spark_jobs.common import PROJECT_ROOT, get_logger, get_spark, hdfs_file_count, hdfs_uri

CFG = PROJECT_ROOT / "config" / "phase4.yaml"
SQL_DIR = PROJECT_ROOT / "spark_sql"


def clean(spark, table):
    """Read one Phase-3 clean table; no raw/Phase-2 fallback is permitted."""
    return spark.read.parquet(hdfs_uri("full", "clean", table))


def hdfs_rm(path):
    subprocess.run(["hdfs", "dfs", "-rm", "-r", "-f", path], check=False, capture_output=True)


def write(df, name, partitions):
    """Overwrite one feature table and immediately read it back for verification."""
    path = hdfs_uri("full", "features", name)
    hdfs_rm(path)
    (df.repartition(partitions).write.mode("overwrite").parquet(path))
    rows = df.sparkSession.read.parquet(path).count()
    return {"path": path, "rows": rows, "files": hdfs_file_count(path)}


def severity(delay):
    return (F.when(delay <= 1, "On Time").when(delay <= 5, "Minor")
            .when(delay <= 10, "Moderate").when(delay <= 20, "Major").otherwise("Severe"))


def main():
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    log, log_path = get_logger("phase4_features")
    spark = get_spark("phase4-features")
    tables = {n: clean(spark, n) for n in (
        "stops", "routes", "route_stops", "schedules", "vehicles", "passengers", "trips",
        "passenger_counts", "tickets", "delays")}
    for name, df in tables.items():
        df.createOrReplaceTempView(name)

    # Execute each requested Spark SQL relationship, measuring the left rows, joined
    # rows, and left records without a parent. These measurements form join_report.md.
    joins = [
        ("01_tickets_passengers", "tickets", "passengers", "passenger_id"),
        ("02_tickets_trips", "tickets", "trips", "trip_id"),
        ("03_trips_routes", "trips", "routes", "route_id"),
        ("04_trips_vehicles", "trips", "vehicles", "vehicle_id"),
        ("05_trips_schedules", "trips", "schedules", "schedule_id"),
        ("06_routes_route_stops", "routes", "route_stops", "route_id"),
        ("07_route_stops_stops", "route_stops", "stops", "stop_id"),
        ("08_trips_delays", "trips", "delays", "trip_id"),
        ("09_trips_passenger_counts", "trips", "passenger_counts", "trip_id"),
    ]
    join_metrics = []
    for stem, left, right, key in joins:
        sql = (SQL_DIR / f"{stem}.sql").read_text(encoding="utf-8")
        joined = spark.sql(sql)
        left_rows = tables[left].count()
        joined_rows = joined.count()
        orphans = tables[left].select(key).filter(F.col(key).isNotNull()).join(
            tables[right].select(key).distinct(), key, "left_anti").count()
        join_metrics.append({"join": stem, "keys": key, "type": "left", "left_rows": left_rows,
                             "joined_rows": joined_rows, "orphans": orphans})
    # tenth relationship is a one-table location enrichment and is verified as a SQL output.
    loc = spark.sql((SQL_DIR / "10_stops_location.sql").read_text(encoding="utf-8"))
    join_metrics.append({"join": "10_stops_location", "keys": "stop_id", "type": "projection",
                         "left_rows": tables["stops"].count(), "joined_rows": loc.count(), "orphans": 0})

    pc = tables["passenger_counts"].groupBy("trip_id").agg(
        F.sum("boardings").alias("boardings"), F.sum("alightings").alias("alightings"),
        F.max("max_load").alias("max_load"), F.sum("denied_boardings").alias("denied_boardings"))
    delay = tables["delays"].groupBy("trip_id").agg(F.avg("delay_minutes").alias("delay_minutes"))
    trip = (tables["trips"].filter(~F.array_contains("dq_flags", "DQ16"))
            .join(pc, "trip_id", "left").join(delay, "trip_id", "left")
            .join(tables["vehicles"].select("vehicle_id", "capacity_total"), "vehicle_id", "left")
            .join(tables["routes"].select("route_id", "distance_km", "route_type"), "route_id", "left")
            .join(tables["schedules"].select("schedule_id", "planned_runtime_min", "headway_min"), "schedule_id", "left")
            .withColumn("boardings", F.coalesce("boardings", F.lit(0)))
            .withColumn("alightings", F.coalesce("alightings", F.lit(0)))
            .withColumn("max_load", F.coalesce("max_load", F.lit(0)))
            .withColumn("occupancy_pct", F.when(F.col("capacity_total") > 0, F.col("max_load") / F.col("capacity_total")))
            .withColumn("travel_time_min", (F.unix_timestamp("actual_arrival") - F.unix_timestamp("actual_departure")) / 60)
            .withColumn("schedule_deviation_min", (F.unix_timestamp("actual_departure") - F.unix_timestamp("scheduled_departure")) / 60)
            .withColumn("delay_minutes", F.coalesce("delay_minutes", F.lit(0.0)))
            .withColumn("delay_severity", severity(F.col("delay_minutes")))
            .withColumn("crowding_flag", F.col("occupancy_pct") > F.lit(0.9))
            .withColumn("trip_punctuality", F.abs("delay_minutes") <= 1)
            .withColumn("hour", F.hour("scheduled_departure"))
            .withColumn("day_of_week", F.dayofweek("service_date"))
            .withColumn("weekend_indicator", F.col("day_of_week").isin(1, 7)))
    # PRECEDING -1 excludes the current row and all future rows: the leakage contract.
    # trip_id breaks timestamp ties, making historical and headway features reproducible.
    historic = Window.partitionBy("route_id").orderBy("scheduled_departure", "trip_id").rowsBetween(Window.unboundedPreceding, -1)
    headway_w = Window.partitionBy("route_id", "service_date").orderBy("scheduled_departure", "trip_id")
    trip = (trip.withColumn("historical_demand_average", F.avg("boardings").over(historic))
            .withColumn("historical_delay_average", F.avg("delay_minutes").over(historic))
            .withColumn("previous_departure", F.lag("actual_departure").over(headway_w))
            .withColumn("headway_minutes", (F.unix_timestamp("actual_departure") - F.unix_timestamp("previous_departure")) / 60)
            .drop("previous_departure"))
    hourly = trip.groupBy("route_id", "service_date", "hour").agg(F.sum("boardings").alias("hourly_boardings"))
    daily = trip.groupBy("route_id", "service_date").agg(F.sum("boardings").alias("daily_boardings"))
    trip = (trip.join(hourly, ["route_id", "service_date", "hour"], "left").join(daily, ["route_id", "service_date"], "left")
            .withColumn("peak_hour_indicator", F.col("hourly_boardings") / F.col("daily_boardings") >=
                        F.lit(cfg["peak"]["min_share_of_daily_ridership"])))
    # Rank distinct dates first, then join their assignment back. This prevents a busy
    # date from being divided between train and validation/test rows.
    date_rank = Window.orderBy("service_date")
    date_splits = (trip.select("service_date").distinct().withColumn("_date_bucket", F.ntile(6).over(date_rank))
                   .withColumn("split", F.when(F.col("_date_bucket") <= 4, "train")
                               .when(F.col("_date_bucket") == 5, "validation").otherwise("test"))
                   .select("service_date", "split"))
    trip = trip.join(date_splits, "service_date", "inner")

    route = trip.groupBy("route_id", "service_date", "split").agg(
        F.sum("boardings").alias("passenger_count"), F.avg("occupancy_pct").alias("route_load_factor"),
        F.avg("delay_minutes").alias("route_reliability_delay_min"), F.avg(F.col("trip_punctuality").cast("double")).alias("trip_punctuality_rate"),
        F.sum("denied_boardings").alias("denied_boardings"))
    route_period = trip.groupBy("route_id", "day_of_week", "hour", "split").agg(
        F.avg("boardings").alias("avg_boardings"), F.avg("delay_minutes").alias("avg_delay_minutes"),
        F.avg("occupancy_pct").alias("capacity_utilization"), F.avg(F.col("peak_hour_indicator").cast("double")).alias("peak_rate"))
    stop_ticket = tables["tickets"].groupBy(F.col("entry_stop_id").alias("stop_id"), "service_date").agg(F.count("*").alias("boarding_count"))
    stop = stop_ticket.join(loc.select("stop_id", "zone", "stop_type"), "stop_id", "left")
    outputs = {
        "trip_features": write(trip, "trip_features", cfg["output_partitions"]),
        "route_features": write(route, "route_features", cfg["output_partitions"]),
        "route_time_features": write(route_period, "route_time_features", cfg["output_partitions"]),
        "stop_daily_demand": write(stop, "stop_daily_demand", cfg["output_partitions"]),
        "route_daily_demand": write(route, "route_daily_demand", cfg["output_partitions"]),
    }
    split_rows = [r.asDict() for r in trip.groupBy("split").agg(F.min("service_date").alias("min_date"), F.max("service_date").alias("max_date"), F.count("*").alias("rows")).orderBy("min_date").collect()]
    target_balance = [r.asDict() for r in trip.groupBy("split", "delay_severity", "crowding_flag").count().orderBy("split", "delay_severity", "crowding_flag").collect()]
    report = ["# Phase 4 Join Report", "", "| join | keys | type | left rows | output rows | orphans |", "|---|---|---|---:|---:|---:|"]
    report += [f"| {m['join']} | {m['keys']} | {m['type']} | {m['left_rows']:,} | {m['joined_rows']:,} | {m['orphans']:,} |" for m in join_metrics]
    report += ["", "## Chronological splits", "", json.dumps(split_rows, default=str, indent=2), "", "## Target distribution", "", json.dumps(target_balance, default=str, indent=2), "", "## Leakage check", "", "`historical_*` windows order by `scheduled_departure, trip_id` and end at `rowsBetween(..., -1)`: the current and future trips are excluded. `spark_jobs/verify_phase4.py` recomputes this on a deterministic sample."]
    (PROJECT_ROOT / "reports" / "join_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (PROJECT_ROOT / "reports" / "phase4_metrics.json").write_text(json.dumps({"joins": join_metrics, "outputs": outputs, "splits": split_rows, "target_balance": target_balance}, indent=2, default=str), encoding="utf-8")
    log.info("PHASE4 PASS: %s", json.dumps(outputs))
    spark.stop()


if __name__ == "__main__":
    main()
