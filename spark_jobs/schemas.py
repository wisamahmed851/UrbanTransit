"""Explicit Spark schemas for the 12 UrbanTransit IQ tables.

Why explicit schemas? Spark can guess column types ("schema inference"), but guessing
reads the data twice and gets types wrong when the data is dirty (one "unknown" in a
numeric column turns the whole column into a string). An explicit StructType is the
contract for the raw files - Laravel analogy: a migration / Eloquent `$casts`; NestJS
analogy: a TypeORM entity or a DTO with class-validator types.

Each schema here must match documentation/schemas/<table>.json (the single source of
truth). `verify_against_docs()` checks that, and the ingestion job refuses to run if
they drift apart.

Every CSV/JSON table also gets the extra column `_corrupt_record` when read in
PERMISSIVE mode: Spark puts the raw text of any row it could not parse there instead of
silently dropping it (see ingest_raw.py).
"""

import json
from pathlib import Path

from pyspark.sql.types import (ArrayType, BooleanType, DateType, DoubleType, IntegerType, StringType,
                               StructField, StructType, TimestampType)

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "documentation" / "schemas"
CORRUPT_COL = "_corrupt_record"


def _f(name, dtype, nullable=True):
    # All raw columns are nullable in Spark: missing values are kept as null so that the
    # quality checks in Phase 3 can find them (nothing is rejected at ingestion time).
    return StructField(name, dtype, nullable)


SCHEMAS: dict[str, StructType] = {
    "stops": StructType([
        _f("stop_id", StringType()), _f("stop_name", StringType()), _f("latitude", DoubleType()),
        _f("longitude", DoubleType()), _f("zone", StringType()), _f("stop_type", StringType()),
        _f("has_shelter", BooleanType()), _f("opened_date", DateType()),
    ]),
    "routes": StructType([
        _f("route_id", StringType()), _f("route_code", StringType()), _f("route_name", StringType()),
        _f("route_type", StringType()), _f("origin_stop_id", StringType()), _f("destination_stop_id", StringType()),
        _f("distance_km", DoubleType()), _f("base_fare", DoubleType()), _f("fare_per_km", DoubleType()),
        _f("launch_date", DateType()), _f("status", StringType()),
    ]),
    "route_stops": StructType([
        _f("route_id", StringType()), _f("direction", IntegerType()), _f("stop_sequence", IntegerType()),
        _f("stop_id", StringType()), _f("distance_from_start_km", DoubleType()),
        _f("scheduled_offset_min", DoubleType()), _f("is_timing_point", BooleanType()),
    ]),
    "service_calendar": StructType([
        _f("service_id", StringType()), _f("service_name", StringType()), _f("day_type", StringType()),
        _f("timetable_period", StringType()), _f("days_of_week", ArrayType(StringType())),
        _f("start_date", DateType()), _f("end_date", DateType()),
        _f("exceptions", ArrayType(StructType([
            _f("date", DateType()), _f("exception_type", StringType()), _f("reason", StringType())]))),
    ]),
    "schedules": StructType([
        _f("schedule_id", StringType()), _f("route_id", StringType()), _f("service_id", StringType()),
        _f("direction", IntegerType()), _f("period", StringType()), _f("start_time", StringType()),
        _f("end_time", StringType()), _f("headway_min", IntegerType()), _f("planned_runtime_min", DoubleType()),
        _f("valid_from", DateType()), _f("valid_to", DateType()),
    ]),
    "vehicles": StructType([
        _f("vehicle_id", StringType()), _f("registration_no", StringType()), _f("vehicle_type", StringType()),
        _f("capacity_seated", IntegerType()), _f("capacity_total", IntegerType()), _f("depot", StringType()),
        _f("fuel_type", StringType()), _f("commission_date", DateType()), _f("has_apc", BooleanType()),
        _f("status", StringType()),
    ]),
    "passengers": StructType([
        _f("passenger_id", StringType()), _f("card_number", StringType()), _f("passenger_type", StringType()),
        _f("age_group", StringType()), _f("gender", StringType()), _f("home_stop_id", StringType()),
        _f("registration_date", DateType()), _f("card_status", StringType()),
    ]),
    "trips": StructType([
        _f("trip_id", StringType()), _f("route_id", StringType()), _f("direction", IntegerType()),
        _f("service_date", DateType()), _f("service_id", StringType()), _f("schedule_id", StringType()),
        _f("vehicle_id", StringType()), _f("original_vehicle_id", StringType()),
        _f("scheduled_departure", TimestampType()), _f("scheduled_arrival", TimestampType()),
        _f("actual_departure", TimestampType()), _f("actual_arrival", TimestampType()),
        _f("trip_status", StringType()), _f("trip_type", StringType()), _f("cancellation_reason", StringType()),
    ]),
    "passenger_counts": StructType([
        _f("count_id", StringType()), _f("trip_id", StringType()), _f("route_id", StringType()),
        _f("service_date", DateType()), _f("vehicle_id", StringType()), _f("boardings", IntegerType()),
        _f("alightings", IntegerType()), _f("max_load", IntegerType()), _f("max_load_stop_id", StringType()),
        _f("denied_boardings", IntegerType()), _f("card_taps", IntegerType()),
    ]),
    "tickets": StructType([
        _f("ticket_id", StringType()), _f("passenger_id", StringType()), _f("trip_id", StringType()),
        _f("route_id", StringType()), _f("service_date", DateType()), _f("entry_stop_id", StringType()),
        _f("exit_stop_id", StringType()), _f("entry_time", TimestampType()), _f("exit_time", TimestampType()),
        _f("ticket_type", StringType()), _f("fare_category", StringType()), _f("fare_amount", DoubleType()),
        _f("payment_method", StringType()),
    ]),
    "delays": StructType([
        _f("delay_id", StringType()), _f("trip_id", StringType()), _f("route_id", StringType()),
        _f("stop_id", StringType()), _f("service_date", DateType()),
        _f("scheduled_arrival", TimestampType()), _f("actual_arrival", TimestampType()),
        _f("scheduled_departure", TimestampType()), _f("actual_departure", TimestampType()),
        _f("delay_minutes", DoubleType()), _f("delay_reason", StringType()), _f("record_source", StringType()),
    ]),
    "gps_events": StructType([
        _f("event_id", StringType()), _f("vehicle_id", StringType()), _f("trip_id", StringType()),
        _f("route_id", StringType()), _f("stop_id", StringType()), _f("event_time", TimestampType()),
        _f("event_type", StringType()), _f("latitude", DoubleType()), _f("longitude", DoubleType()),
        _f("speed_kmh", DoubleType()),
    ]),
}

# How each table is stored in raw_data / HDFS raw
FORMATS = {t: "csv" for t in SCHEMAS}
FORMATS["service_calendar"] = "json"      # one JSON array (multi-line)
FORMATS["gps_events"] = "jsonl"           # JSON Lines

# JSON-schema type names used in documentation/schemas -> Spark simpleString()
_DOC_TO_SPARK = {"string": "string", "integer": "int", "double": "double", "boolean": "boolean",
                 "date": "date", "timestamp": "timestamp", "array<string>": "array<string>",
                 "array<struct<date:date,exception_type:string,reason:string>>":
                     "array<struct<date:date,exception_type:string,reason:string>>"}


def with_corrupt_column(table: str) -> StructType:
    """Explicit schema plus the `_corrupt_record` column used by PERMISSIVE parsing."""
    return StructType(SCHEMAS[table].fields + [StructField(CORRUPT_COL, StringType(), True)])


def verify_against_docs() -> list[str]:
    """Return a list of differences between these StructTypes and documentation/schemas/*.json."""
    problems = []
    for table, schema in SCHEMAS.items():
        doc = json.loads((SCHEMA_DIR / f"{table}.json").read_text(encoding="utf-8"))
        doc_cols = [(c["name"], _DOC_TO_SPARK[c["type"]]) for c in doc["columns"]]
        spark_cols = [(f.name, f.dataType.simpleString()) for f in schema.fields]
        if doc_cols != spark_cols:
            problems.append(f"{table}: docs={doc_cols} spark={spark_cols}")
    missing = {p.stem for p in SCHEMA_DIR.glob("*.json")} - set(SCHEMAS)
    problems += [f"{t}: documented but no Spark schema" for t in sorted(missing)]
    return problems


if __name__ == "__main__":
    issues = verify_against_docs()
    print(f"{len(SCHEMAS)} explicit schemas; differences vs documentation/schemas: {len(issues)}")
    for i in issues:
        print("  ", i)
