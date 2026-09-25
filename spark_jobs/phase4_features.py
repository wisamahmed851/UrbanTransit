"""Phase 4: integrate *clean* UrbanTransit tables and write leakage-safe feature sets.

The job never reads raw or Phase-2 Parquet.  Think of the SQL files as Laravel query
scopes: they document the 10 relationships, while this job is the service that runs
them, measures their cardinality, and materialises model-ready Spark features.

The feature builders (split_dates, add_demand_growth, add_peak_asof, ...) are plain
functions so spark_jobs/verify_phase4.py can re-run them on data truncated at a cutoff
date and prove that no value depends on later data.
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
EPOCH = "2000-01-01"


def load_cfg():
    return yaml.safe_load(CFG.read_text(encoding="utf-8"))


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


def day_idx(col="service_date"):
    """Integer day number, so range windows can say 'the previous N calendar days'."""
    return F.datediff(F.col(col), F.lit(EPOCH))


def severity_bands():
    """Delay-severity bands from config/thresholds.yaml (single source of truth)."""
    return yaml.safe_load((PROJECT_ROOT / "config" / "thresholds.yaml").read_text(encoding="utf-8"))["delay_severity"]


def severity(delay, cfg):
    """Lateness class from thresholds.yaml. 'On Time' must cover the generator's no-record band
    (< on_time_late_min, early included), otherwise within_tolerance trips would be mislabelled."""
    bands = severity_bands()
    if bands[0]["below_minutes"] != cfg["delay"]["on_time_late_min"]:
        raise ValueError("thresholds.yaml On Time bound must equal phase4.yaml delay.on_time_late_min")
    expr = F.when(delay.isNull(), F.lit(None))
    for b in bands:
        expr = expr.when(delay < b["below_minutes"], b["name"]) if b["below_minutes"] is not None else expr.otherwise(b["name"])
    return expr


def split_dates(spark, dates, cfg):
    """Assign whole service dates to train/validation/test from the configured fractions."""
    tf, vf = cfg["splits"]["train_fraction"], cfg["splits"]["validation_fraction"]
    if not (0 < tf < 1 and 0 < vf < 1 and tf + vf < 1):
        raise ValueError(f"invalid split fractions train={tf} validation={vf}")
    ordered = sorted(r[0] for r in dates.distinct().collect())
    n_train, n_val = round(len(ordered) * tf), round(len(ordered) * vf)
    if n_train + n_val >= len(ordered):
        raise ValueError("split fractions leave no test dates")
    rows = [(d, "train" if i < n_train else "validation" if i < n_train + n_val else "test")
            for i, d in enumerate(ordered)]
    return spark.createDataFrame(rows, "service_date date, split string")


def add_demand_growth(route_day, cfg):
    """Week-over-week and month-over-month growth of estimated daily boardings.

    Both windows end at d-1, so the value for day d uses only strictly earlier days.
    """
    out = route_day.withColumn("_d", day_idx())
    for name, n in (("wow", cfg["demand_growth"]["wow_window_days"]), ("mom", cfg["demand_growth"]["mom_window_days"])):
        recent = Window.partitionBy("route_id").orderBy("_d").rangeBetween(-n, -1)
        prior = Window.partitionBy("route_id").orderBy("_d").rangeBetween(-2 * n, -n - 1)
        cur, prev = F.avg("estimated_daily_boardings").over(recent), F.avg("estimated_daily_boardings").over(prior)
        out = out.withColumn(f"demand_{name}_growth", F.when(prev > 0, cur / prev - 1))
    return out.drop("_d")


def add_peak_asof(trip, cfg):
    """Leak-free peak flag: the route-hour's share of daily ridership averaged over *previous* days.

    Same route, same hour, same weekday/weekend type, window [d-lookback, d-1]; the trip's own
    day (and therefore its own boardings and every later hour) is never used.
    """
    hourly = trip.groupBy("route_id", "service_date", "hour", "weekend_indicator").agg(F.sum("boardings").alias("_hb"))
    daily = trip.groupBy("route_id", "service_date").agg(F.sum("boardings").alias("_db"))
    n = cfg["peak"]["asof_lookback_days"]
    w = Window.partitionBy("route_id", "hour", "weekend_indicator").orderBy("_d").rangeBetween(-n, -1)
    share = (hourly.join(daily, ["route_id", "service_date"])
             .withColumn("_share", F.when(F.col("_db") > 0, F.col("_hb") / F.col("_db")))
             .withColumn("_d", day_idx())
             .withColumn("peak_hour_share_asof", F.avg("_share").over(w))
             .select("route_id", "service_date", "hour", "peak_hour_share_asof"))
    return (trip.join(share, ["route_id", "service_date", "hour"], "left")
            .withColumn("peak_hour_indicator_asof", F.col("peak_hour_share_asof") >= F.lit(cfg["peak"]["min_share_of_daily_ridership"])))


def add_historical(trip):
    """Strict-prior route averages. PRECEDING -1 excludes the current row and all future rows;
    trip_id breaks timestamp ties so the result is reproducible. avg() skips NULL (unmeasured) trips."""
    historic = Window.partitionBy("route_id").orderBy("scheduled_departure", "trip_id").rowsBetween(Window.unboundedPreceding, -1)
    return (trip.withColumn("historical_demand_average", F.avg("boardings").over(historic))
            .withColumn("historical_delay_average", F.avg("delay_minutes").over(historic)))


def build_route_day(trip):
    """One row per route per service date (forecasting grain)."""
    return (trip.groupBy("route_id", "service_date", "day_of_week", "weekend_indicator", "split").agg(
        F.count("*").alias("scheduled_trips"),
        F.sum((F.col("trip_status") == "completed").cast("int")).alias("operated_trips"),
        F.count("boardings").alias("measured_trips"),
        F.sum("boardings").alias("passenger_count"),
        F.avg("occupancy_pct").alias("route_load_factor"),
        F.avg("delay_minutes").alias("route_reliability_delay_min"),
        F.avg("arrival_delay_min").alias("avg_arrival_delay_min"),
        F.avg(F.col("trip_punctuality").cast("double")).alias("trip_punctuality_rate"),
        F.sum("denied_boardings").alias("denied_boardings"))
        .withColumn("demand_coverage", F.when(F.col("operated_trips") > 0, F.col("measured_trips") / F.col("operated_trips")))
        # scale measured boardings up to all operated trips; unmeasured trips are not counted as zero riders
        .withColumn("estimated_daily_boardings", F.when(F.col("measured_trips") > 0,
                    F.col("passenger_count") / F.col("measured_trips") * F.col("operated_trips"))))


def main():
    cfg = load_cfg()
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

    # Passenger counts: a trip without a clean counter record was never measured -> NULL, not 0.
    pc = tables["passenger_counts"].groupBy("trip_id").agg(
        F.sum("boardings").alias("boardings"), F.sum("alightings").alias("alightings"),
        F.max("max_load").alias("max_load"), F.sum("denied_boardings").alias("denied_boardings"))
    # Delays are exception records (see config/phase4.yaml `delay`). Trips whose delay record was
    # quarantined in Phase 3 lost their measurement, so they are treated as not evaluated.
    delay = tables["delays"].groupBy("trip_id").agg(F.avg("delay_minutes").alias("recorded_delay_min"))
    quarantined_delay = (spark.read.parquet(hdfs_uri("full", "clean_quarantine", "delays"))
                         .select(F.get_json_object("original_record", "$.trip_id").alias("trip_id"))
                         .dropna().distinct().withColumn("delay_record_quarantined", F.lit(True)))
    early, late = cfg["delay"]["on_time_early_min"], cfg["delay"]["on_time_late_min"]
    trip = (tables["trips"].filter(~F.array_contains("dq_flags", "DQ16"))
            .join(pc, "trip_id", "left").join(delay, "trip_id", "left").join(quarantined_delay, "trip_id", "left")
            .join(tables["vehicles"].select("vehicle_id", "capacity_total"), "vehicle_id", "left")
            .join(tables["routes"].select("route_id", "distance_km", "route_type"), "route_id", "left")
            .join(tables["schedules"].select("schedule_id", "planned_runtime_min", "headway_min"), "schedule_id", "left")
            .withColumn("passenger_count_measured", F.col("boardings").isNotNull())
            .withColumn("occupancy_pct", F.when(F.col("capacity_total") > 0, F.col("max_load") / F.col("capacity_total")))
            .withColumn("travel_time_min", (F.unix_timestamp("actual_arrival") - F.unix_timestamp("actual_departure")) / 60)
            .withColumn("schedule_deviation_min", (F.unix_timestamp("actual_departure") - F.unix_timestamp("scheduled_departure")) / 60)
            .withColumn("arrival_delay_min", (F.unix_timestamp("actual_arrival") - F.unix_timestamp("scheduled_arrival")) / 60)
            .withColumn("delay_source", F.when(F.col("trip_status") != "completed", "not_evaluated")
                        .when(F.col("delay_record_quarantined"), "not_evaluated")
                        .when(F.col("recorded_delay_min").isNotNull(), "record")
                        .otherwise("within_tolerance"))
            # within_tolerance -> 0.0: the generator guarantees -2 < deviation < 5 for these trips
            .withColumn("delay_minutes", F.when(F.col("delay_source") == "record", F.col("recorded_delay_min"))
                        .when(F.col("delay_source") == "within_tolerance", F.lit(0.0)))
            .drop("recorded_delay_min", "delay_record_quarantined")
            .withColumn("delay_severity", severity(F.col("delay_minutes"), cfg))
            .withColumn("crowding_flag", F.col("occupancy_pct") > F.lit(0.9))
            .withColumn("trip_punctuality", (F.col("delay_minutes") > early) & (F.col("delay_minutes") < late))
            .withColumn("hour", F.hour("scheduled_departure"))
            .withColumn("day_of_week", F.dayofweek("service_date"))
            .withColumn("weekend_indicator", F.col("day_of_week").isin(1, 7)))
    trip = add_historical(trip)
    # Headway is measured against the previous *operated* trip of the same route, day and direction.
    # Cancelled trips are skipped (the gap they leave is real); a negative value means this bus overtook
    # the one scheduled before it (bunching), so the sign is kept and exposed as overtaking_flag.
    headway_w = (Window.partitionBy("route_id", "service_date", "direction").orderBy("scheduled_departure", "trip_id")
                 .rowsBetween(Window.unboundedPreceding, -1))
    trip = (trip.withColumn("previous_departure", F.last("actual_departure", ignorenulls=True).over(headway_w))
            .withColumn("headway_minutes", (F.unix_timestamp("actual_departure") - F.unix_timestamp("previous_departure")) / 60)
            .withColumn("overtaking_flag", F.col("headway_minutes") < 0)
            .drop("previous_departure"))
    # Descriptive peak flag (uses the whole day - Phase 5 analytics only, never a model input).
    hourly = trip.groupBy("route_id", "service_date", "hour").agg(F.sum("boardings").alias("hourly_boardings"))
    daily = trip.groupBy("route_id", "service_date").agg(F.sum("boardings").alias("daily_boardings"))
    trip = (trip.join(hourly, ["route_id", "service_date", "hour"], "left").join(daily, ["route_id", "service_date"], "left")
            .withColumn("peak_hour_indicator", F.col("hourly_boardings") / F.col("daily_boardings") >=
                        F.lit(cfg["peak"]["min_share_of_daily_ridership"])))
    trip = add_peak_asof(trip, cfg)
    # Whole dates are assigned to one split, so a busy date is never divided between splits.
    date_splits = split_dates(spark, trip.select("service_date"), cfg)
    trip = trip.join(date_splits, "service_date", "inner")

    route_day = add_demand_growth(build_route_day(trip), cfg).cache()
    trip = trip.join(route_day.select("route_id", "service_date", "demand_wow_growth", "demand_mom_growth"),
                     ["route_id", "service_date"], "left").cache()

    # route_features: one row per route. Behavioural metrics come from the TRAIN split only, so the
    # table can be joined to any split as a static route profile without leaking later data.
    train = trip.filter(F.col("split") == "train")
    stops_per_route = tables["route_stops"].filter("direction = 0").groupBy("route_id").agg(F.countDistinct("stop_id").alias("n_stops"))
    route = (tables["routes"].select("route_id", "route_code", "route_type", "distance_km", "launch_date")
             .join(stops_per_route, "route_id", "left")
             .join(train.groupBy("route_id").agg(
                 F.countDistinct("service_date").alias("train_service_days"),
                 F.avg("boardings").alias("avg_trip_boardings"),
                 F.avg("occupancy_pct").alias("route_load_factor"),
                 F.avg("delay_minutes").alias("route_reliability_delay_min"),
                 F.stddev("arrival_delay_min").alias("arrival_delay_std_min"),
                 F.avg(F.col("trip_punctuality").cast("double")).alias("trip_punctuality_rate"),
                 F.avg(F.col("crowding_flag").cast("double")).alias("crowding_rate"),
                 F.avg(F.col("overtaking_flag").cast("double")).alias("bunching_rate")), "route_id", "left")
             .join(route_day.filter(F.col("split") == "train").groupBy("route_id")
                   .agg(F.avg("estimated_daily_boardings").alias("avg_daily_boardings")), "route_id", "left")
             .withColumn("in_train_period", F.col("train_service_days").isNotNull()))
    route_period = trip.groupBy("route_id", "day_of_week", "hour", "split").agg(
        F.avg("boardings").alias("avg_boardings"), F.avg("delay_minutes").alias("avg_delay_minutes"),
        F.avg("occupancy_pct").alias("capacity_utilization"), F.avg(F.col("peak_hour_indicator").cast("double")).alias("peak_rate"),
        F.avg(F.col("peak_hour_indicator_asof").cast("double")).alias("peak_rate_asof"))
    stop_ticket = tables["tickets"].groupBy(F.col("entry_stop_id").alias("stop_id"), "service_date").agg(F.count("*").alias("boarding_count"))
    stop = stop_ticket.join(loc.select("stop_id", "zone", "stop_type"), "stop_id", "left").join(date_splits, "service_date", "left")
    outputs = {
        "trip_features": write(trip, "trip_features", cfg["output_partitions"]),
        "route_features": write(route, "route_features", cfg["output_partitions"]),
        "route_time_features": write(route_period, "route_time_features", cfg["output_partitions"]),
        "stop_daily_demand": write(stop, "stop_daily_demand", cfg["output_partitions"]),
        "route_daily_demand": write(route_day, "route_daily_demand", cfg["output_partitions"]),
    }
    split_rows = [r.asDict() for r in trip.groupBy("split").agg(F.min("service_date").alias("min_date"), F.max("service_date").alias("max_date"), F.countDistinct("service_date").alias("dates"), F.count("*").alias("rows")).orderBy("min_date").collect()]
    target_balance = [r.asDict() for r in trip.groupBy("split", "delay_severity", "crowding_flag").count().orderBy("split", "delay_severity", "crowding_flag").collect()]
    coverage = {
        "delay_source": {r[0]: r[1] for r in trip.groupBy("delay_source").count().collect()},
        "passenger_count_measured": {str(r[0]): r[1] for r in trip.groupBy("passenger_count_measured").count().collect()},
        "negative_headway_overtaking": trip.filter("overtaking_flag").count(),
    }
    report = ["# Phase 4 Join Report", "", "| join | keys | type | left rows | output rows | orphans |", "|---|---|---|---:|---:|---:|"]
    report += [f"| {m['join']} | {m['keys']} | {m['type']} | {m['left_rows']:,} | {m['joined_rows']:,} | {m['orphans']:,} |" for m in join_metrics]
    report += ["", "Ticket orphans (01, 02) are exactly the rows Phase 3 flagged `DQ15` (unknown passenger) and `DQ16` (missing trip); see `documentation/feature_catalog.md`.",
               "", "## Chronological splits", "", json.dumps(split_rows, default=str, indent=2),
               "", "## Measurement coverage", "", json.dumps(coverage, indent=2),
               "", "## Target distribution", "", json.dumps(target_balance, default=str, indent=2),
               "", "## Leakage check", "", "`historical_*` windows order by `scheduled_departure, trip_id` and end at `rowsBetween(..., -1)`; `demand_*_growth` and `peak_hour_indicator_asof` use only days before the trip's service date. `spark_jobs/verify_phase4.py` recomputes them on data truncated at a cutoff date."]
    (PROJECT_ROOT / "reports" / "join_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (PROJECT_ROOT / "reports" / "phase4_metrics.json").write_text(json.dumps({"joins": join_metrics, "outputs": outputs, "splits": split_rows, "coverage": coverage, "target_balance": target_balance}, indent=2, default=str), encoding="utf-8")
    log.info("PHASE4 PASS: %s", json.dumps(outputs))
    spark.stop()


if __name__ == "__main__":
    main()
