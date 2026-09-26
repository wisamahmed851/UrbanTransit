"""Phase 5 analytics summary tables, mirrored from HDFS `/urbantransit/analytics/<name>`.

`ANALYTICS_SCHEMAS` is copied from the Parquet schemas (Spark `DataType.simpleString()`),
column for column and in the same order. Names and types are kept exactly, including the
mixed decimal precisions, and every column is nullable, as in Parquet. The loader
(`database/load_analytics_to_mysql.py`) refuses to load a table whose live Parquet schema
differs from this spec, so the two cannot drift silently.

Each table gets a surrogate `id` primary key (Parquet rows have no key, and several
natural keys contain NULLs) plus single-column indexes on the API filter columns.

Spark -> MySQL type map:

| Spark         | MySQL          | note                                              |
|---------------|----------------|---------------------------------------------------|
| string        | VARCHAR(64)    | longest measured value is 31 chars; wider exceptions in `STRING_OVERRIDES` |
| int / bigint  | INT / BIGINT   |                                                   |
| double        | DOUBLE         | 8-byte IEEE, same as Spark                        |
| decimal(p,s)  | DECIMAL(p,s)   | precision and scale preserved                     |
| date          | DATE           |                                                   |
| boolean       | TINYINT(1)     | SQLAlchemy Boolean                                |

Laravel analogy: a schema file listing `$table->decimal('late_share', 6, 4)->nullable()`
for each column, except that it is data, so the loader and the API read the same list.
"""

import re

from sqlalchemy import BigInteger, Boolean, Column, Date, Double, Index, Integer, Numeric, String, Table, Text

from src.extensions import db

STRING_DEFAULT_LENGTH = 64
# Measured max lengths (2026-09-26): class_reason 322, tricky_case_notes 111,
# spiking_routes 79, detail 71. Everything else is <= 31 characters.
STRING_OVERRIDES = {
    ("route_performance", "class_reason"): None,          # None = TEXT
    ("route_performance", "tricky_case_notes"): 255,
    ("special_event_dates", "spiking_routes"): 255,
    ("anomalies", "detail"): 255,
}

# Columns that get an index because the API filters or sorts on them.
INDEXED_COLUMNS = {"route_id", "stop_id", "origin_stop_id", "destination_stop_id",
                   "direction", "day_class", "time_period", "service_date"}

ANALYTICS_SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "route_performance": [  # 118 rows
        ("route_id", "string"),
        ("route_code", "string"),
        ("route_type", "string"),
        ("launch_date", "date"),
        ("eligible", "boolean"),
        ("normal_service_days", "bigint"),
        ("excluded_abnormal_days", "bigint"),
        ("demand_coverage", "double"),
        ("med_daily_boardings", "double"),
        ("med_occupancy", "double"),
        ("med_p90_occupancy", "double"),
        ("med_punctuality", "double"),
        ("med_late_share", "decimal(6,4)"),
        ("med_travel_time_ratio", "double"),
        ("med_arrival_delay_std", "double"),
        ("med_underload_share", "decimal(6,4)"),
        ("med_overload_share", "decimal(6,4)"),
        ("persistent_cells", "bigint"),
        ("recurring_cells", "bigint"),
        ("one_off_cells", "bigint"),
        ("event_day_overloads", "bigint"),
        ("demand_score", "double"),
        ("occupancy_score", "double"),
        ("punctuality_score", "double"),
        ("delay_frequency_score", "double"),
        ("travel_time_score", "double"),
        ("reliability_score", "double"),
        ("load_score", "double"),
        ("underutilization_score", "decimal(16,1)"),
        ("overcrowding_score", "double"),
        ("med_overload_severity", "decimal(6,4)"),
        ("persistent_cell_share", "double"),
        ("overcrowding_penalty", "double"),
        ("composite_score", "double"),
        ("composite_rank", "double"),
        ("reliability_rank", "double"),
        ("route_class", "string"),
        ("class_reason", "string"),
        ("overcrowded_flag", "boolean"),
        ("overcrowded_scope", "string"),
        ("overcrowding_location", "string"),
        ("hotspot_stop_id", "string"),
        ("hotspot_share", "double"),
        ("tricky_case_notes", "string"),
    ],
    "route_reliability": [  # 118 rows
        ("route_id", "string"),
        ("scheduled_trips", "bigint"),
        ("missed_trips", "bigint"),
        ("missed_share", "double"),
        ("evaluated_trips", "bigint"),
        ("on_time_rate", "double"),
        ("early_arrival_share", "decimal(6,4)"),
        ("late_arrival_share", "decimal(6,4)"),
        ("arrival_delay_std", "double"),
        ("travel_time_cv", "double"),
        ("on_time_rank", "int"),
    ],
    "eda_route_demand": [  # 118 rows
        ("route_id", "string"),
        ("route_code", "string"),
        ("route_type", "string"),
        ("launch_date", "date"),
        ("service_days", "bigint"),
        ("est_total_boardings", "double"),
        ("avg_daily_boardings", "double"),
        ("avg_demand_coverage", "double"),
        ("demand_rank", "int"),
    ],
    "eda_route_delay": [  # 118 rows
        ("route_id", "string"),
        ("route_code", "string"),
        ("trips", "bigint"),
        ("evaluated_trips", "bigint"),
        ("avg_delay_min", "double"),
        ("late_share", "decimal(6,4)"),
        ("punctuality_rate", "double"),
        ("avg_arrival_delay_min", "double"),
        ("most_delayed_rank", "int"),
        ("punctuality_rank", "int"),
    ],
    "delay_congestion_patterns": [  # 118 rows
        ("route_id", "string"),
        ("early_morning_delay", "double"),
        ("morning_peak_delay", "double"),
        ("midday_delay", "double"),
        ("evening_peak_delay", "double"),
        ("evening_delay", "double"),
        ("morning_excess_min", "double"),
        ("evening_excess_min", "double"),
        ("congestion_pattern", "string"),
    ],
    "overcrowding_summary": [  # 236 rows
        ("route_id", "string"),
        ("direction", "int"),
        ("trips", "bigint"),
        ("measured_trips", "bigint"),
        ("not_measured_trips", "bigint"),
        ("low_trips", "bigint"),
        ("moderate_trips", "bigint"),
        ("high_trips", "bigint"),
        ("overcrowded_trips", "bigint"),
        ("critical_trips", "bigint"),
        ("overload_share", "double"),
        ("avg_occupancy", "double"),
        ("max_occupancy", "double"),
    ],
    "persistent_overcrowding": [  # 8,240 rows
        ("route_id", "string"),
        ("direction", "int"),
        ("day_of_week", "int"),
        ("time_period", "string"),
        ("days_observed", "bigint"),
        ("days_overloaded", "bigint"),
        ("event_day_overloads", "bigint"),
        ("max_occupancy", "double"),
        ("overload_day_share", "double"),
        ("overload_pattern", "string"),
    ],
    "underutilized_services": [  # 3,540 rows
        ("route_id", "string"),
        ("direction", "int"),
        ("day_class", "string"),
        ("time_period", "string"),
        ("distance_km", "double"),
        ("days", "bigint"),
        ("operated_trips", "bigint"),
        ("measured_trips", "bigint"),
        ("trips_per_hour", "double"),
        ("avg_occupancy", "double"),
        ("p90_occupancy", "double"),
        ("avg_boardings_per_trip", "double"),
        ("boardings_per_km", "double"),
        ("period_median_boardings_per_km", "double"),
        ("utilization_status", "string"),
    ],
    "demand_supply_gap": [  # 3,540 rows
        ("route_id", "string"),
        ("direction", "int"),
        ("day_class", "string"),
        ("time_period", "string"),
        ("days", "bigint"),
        ("operated_trips", "bigint"),
        ("measured_trips", "bigint"),
        ("trips_per_hour", "double"),
        ("avg_capacity", "double"),
        ("utilization", "double"),
        ("p90_load", "int"),
        ("denied_per_trip", "double"),
        ("required_capacity", "decimal(14,1)"),
        ("suggested_vehicle_type", "string"),
        ("suggested_capacity", "int"),
        ("gap_status", "string"),
        ("suggestion", "string"),
        ("extra_trips_per_hour", "double"),
    ],
    "service_frequency": [  # 3,540 rows
        ("route_id", "string"),
        ("direction", "int"),
        ("day_class", "string"),
        ("time_period", "string"),
        ("days", "bigint"),
        ("scheduled_trips", "bigint"),
        ("operated_trips", "bigint"),
        ("measured_trips", "bigint"),
        ("scheduled_trips_per_hour", "double"),
        ("avg_boardings_per_trip", "double"),
        ("avg_occupancy", "double"),
        ("p90_occupancy", "double"),
        ("overload_share", "decimal(6,4)"),
        ("peak_rate_asof", "double"),
        ("avg_arrival_delay_min", "double"),
        ("frequency_match", "string"),
    ],
    "delay_by_dimension": [  # 939 rows
        ("dimension", "string"),
        ("dim_value", "string"),
        ("trips", "bigint"),
        ("evaluated_trips", "bigint"),
        ("avg_delay_min", "double"),
        ("late_share", "decimal(6,4)"),
        ("avg_arrival_delay_min", "double"),
        ("p90_arrival_delay_min", "double"),
    ],
    "delay_by_stop": [  # 756 rows
        ("stop_id", "string"),
        ("stop_name", "string"),
        ("zone", "string"),
        ("stop_type", "string"),
        ("routes_serving", "bigint"),
        ("trips_serving", "bigint"),
        ("late_records", "bigint"),
        ("congestion_records", "bigint"),
        ("avg_record_delay_min", "double"),
        ("top_reason", "string"),
        ("late_record_rate", "double"),
        ("congestion_record_rate", "double"),
        ("congestion_rate_pctile", "double"),
        ("is_bottleneck", "boolean"),
    ],
    "delay_top_trips": [  # 500 rows
        ("trip_id", "string"),
        ("route_id", "string"),
        ("direction", "int"),
        ("service_date", "date"),
        ("time_period", "string"),
        ("day_class", "string"),
        ("vehicle_id", "string"),
        ("delay_minutes", "double"),
        ("delay_severity", "string"),
        ("arrival_delay_min", "double"),
    ],
    "stop_performance": [  # 756 rows
        ("stop_id", "string"),
        ("stop_name", "string"),
        ("zone", "string"),
        ("stop_type", "string"),
        ("est_boardings_per_day", "double"),
        ("est_alightings_per_day", "double"),
        ("est_turnover_per_day", "double"),
        ("routes_serving", "bigint"),
        ("trips_serving_per_day", "double"),
        ("turnover_per_trip", "double"),
        ("late_records", "bigint"),
        ("avg_record_delay_min", "double"),
        ("late_record_rate", "double"),
        ("congestion_record_rate", "double"),
        ("top_reason", "string"),
        ("is_bottleneck", "boolean"),
        ("weekday_morning_peak_boardings", "double"),
        ("weekday_midday_boardings", "double"),
        ("weekday_evening_peak_boardings", "double"),
        ("weekday_offpeak_boardings", "double"),
    ],
    "eda_stop_usage": [  # 756 rows
        ("stop_id", "string"),
        ("stop_name", "string"),
        ("zone", "string"),
        ("stop_type", "string"),
        ("days_open", "int"),
        ("card_boardings", "bigint"),
        ("card_alightings", "bigint"),
        ("est_boardings_per_day", "double"),
        ("est_alightings_per_day", "double"),
        ("est_turnover_per_day", "double"),
        ("usage_rank", "int"),
    ],
    "eda_peak_hours": [  # 60 rows
        ("day_class", "string"),
        ("hour", "int"),
        ("days", "bigint"),
        ("trips", "bigint"),
        ("measured_trips", "bigint"),
        ("avg_boardings_per_trip", "double"),
        ("est_boardings_per_day", "double"),
        ("avg_occupancy", "double"),
        ("peak_rate_asof", "double"),
    ],
    "eda_peak_days": [  # 365 rows
        ("service_date", "date"),
        ("day_of_week", "int"),
        ("day_class", "string"),
        ("holiday_name", "string"),
        ("est_system_boardings", "double"),
        ("routes_with_demand", "bigint"),
        ("routes_in_service", "bigint"),
        ("busiest_rank", "int"),
    ],
    "peak_period_summary": [  # 15 rows
        ("day_class", "string"),
        ("time_period", "string"),
        ("days", "bigint"),
        ("trips", "bigint"),
        ("measured_trips", "bigint"),
        ("asof_trips", "bigint"),
        ("avg_boardings_per_trip", "double"),
        ("est_boardings_per_day", "double"),
        ("share_of_day", "double"),
        ("avg_occupancy", "double"),
        ("peak_rate_asof", "double"),
        ("is_peak_period", "boolean"),
    ],
    "flow_od_pairs": [  # 19,296 rows
        ("origin_stop_id", "string"),
        ("destination_stop_id", "string"),
        ("card_journeys", "bigint"),
        ("est_journeys", "double"),
        ("est_journeys_per_day", "double"),
        ("avg_journey_km", "double"),
        ("avg_ride_min", "double"),
        ("routes_used", "bigint"),
        ("flow_rank", "int"),
    ],
    "flow_direction_demand": [  # 3,540 rows
        ("route_id", "string"),
        ("direction", "int"),
        ("day_class", "string"),
        ("time_period", "string"),
        ("days", "bigint"),
        ("operated_trips", "bigint"),
        ("measured_trips", "bigint"),
        ("avg_boardings_per_trip", "double"),
        ("est_boardings_per_day", "double"),
        ("direction_share", "double"),
        ("direction_balance", "string"),
    ],
    "od_matrix": [  # 316,810 rows
        ("origin_stop_id", "string"),
        ("origin_stop_name", "string"),
        ("destination_stop_id", "string"),
        ("destination_stop_name", "string"),
        ("route_id", "string"),
        ("service_type", "string"),
        ("direction", "int"),
        ("time_period", "string"),
        ("day_class", "string"),
        ("day_type", "string"),
        ("card_journeys", "bigint"),
        ("est_passengers", "double"),
        ("days_observed", "bigint"),
    ],
    "travel_time_analysis": [  # 3,540 rows
        ("route_id", "string"),
        ("direction", "int"),
        ("day_class", "string"),
        ("time_period", "string"),
        ("completed_trips", "bigint"),
        ("scheduled_min", "double"),
        ("actual_min", "double"),
        ("excess_min", "double"),
        ("actual_to_scheduled", "double"),
        ("std_min", "double"),
        ("historical_avg_min", "double"),
        ("vs_historical_min", "double"),
    ],
    "travel_time_peak_offpeak": [  # 236 rows
        ("route_id", "string"),
        ("direction", "int"),
        ("peak_trips", "bigint"),
        ("offpeak_trips", "bigint"),
        ("peak_actual_min", "double"),
        ("offpeak_actual_min", "double"),
        ("peak_scheduled_min", "double"),
        ("offpeak_scheduled_min", "double"),
        ("peak_minus_offpeak_min", "double"),
        ("peak_penalty_pct", "double"),
    ],
    "schedule_adherence": [  # 354 rows
        ("route_id", "string"),
        ("day_class", "string"),
        ("scheduled_trips", "bigint"),
        ("missed_trips", "bigint"),
        ("completed_trips", "bigint"),
        ("early_arrivals", "bigint"),
        ("on_time_arrivals", "bigint"),
        ("late_arrivals", "bigint"),
        ("early_share", "double"),
        ("on_time_share", "double"),
        ("late_share", "double"),
        ("missed_share", "double"),
        ("intervals_assessed", "bigint"),
        ("irregular_intervals", "bigint"),
        ("irregular_interval_share", "double"),
    ],
    "headway_bunching": [  # 1,180 rows
        ("route_id", "string"),
        ("direction", "int"),
        ("time_period", "string"),
        ("headways", "bigint"),
        ("headways_assessed", "bigint"),
        ("avg_headway_min", "double"),
        ("avg_scheduled_gap_min", "double"),
        ("headway_cv", "double"),
        ("bunched", "bigint"),
        ("gaps", "bigint"),
        ("overtakings", "bigint"),
        ("bunched_share", "double"),
        ("gap_share", "double"),
    ],
    "special_event_dates": [  # 365 rows
        ("service_date", "date"),
        ("routes_observed", "bigint"),
        ("routes_spiking", "bigint"),
        ("routes_dropping", "bigint"),
        ("max_demand_ratio", "double"),
        ("holiday_name", "string"),
        ("event_extra_trips", "bigint"),
        ("date_status", "string"),
        ("spiking_routes", "string"),
    ],
    "anomalies": [  # 38,382 rows
        ("anomaly_type", "string"),
        ("entity_type", "string"),
        ("entity_id", "string"),
        ("service_date", "date"),
        ("observed_value", "double"),
        ("expected_value", "double"),
        ("detail", "string"),
    ],
    "anomaly_summary": [  # 5 rows
        ("anomaly_type", "string"),
        ("entity_type", "string"),
        ("signals", "bigint"),
        ("entities", "bigint"),
        ("dates", "bigint"),
    ],
    "passenger_segments": [  # 56,779 rows
        ("passenger_id", "string"),
        ("passenger_type", "string"),
        ("age_group", "string"),
        ("journeys", "bigint"),
        ("active_days", "bigint"),
        ("active_span_weeks", "decimal(14,2)"),
        ("active_days_per_week", "decimal(30,3)"),
        ("weekday_share", "decimal(6,4)"),
        ("weekend_share", "decimal(6,4)"),
        ("peak_share", "decimal(6,4)"),
        ("avg_journey_km", "double"),
        ("long_distance_threshold_km", "double"),
        ("est_journeys_represented", "double"),
        ("segment", "string"),
    ],
    "segment_summary": [  # 5 rows
        ("segment", "string"),
        ("card_holders", "bigint"),
        ("share_of_card_holders", "double"),
        ("avg_journeys", "double"),
        ("avg_active_days_per_week", "decimal(30,2)"),
        ("avg_peak_share", "decimal(7,4)"),
        ("avg_journey_km", "double"),
        ("share_of_est_journeys", "double"),
        ("most_common_passenger_type", "string"),
    ],
}

_DECIMAL = re.compile(r"decimal\((\d+),(\d+)\)")


def sql_type(table: str, column: str, spark_type: str):
    """Map one Spark simpleString type to the SQLAlchemy/MySQL column type."""
    if spark_type == "string":
        length = STRING_OVERRIDES.get((table, column), STRING_DEFAULT_LENGTH)
        return Text() if length is None else String(length)
    if spark_type == "int":
        return Integer()
    if spark_type == "bigint":
        return BigInteger()
    if spark_type == "double":
        return Double()
    if spark_type == "date":
        return Date()
    if spark_type == "boolean":
        return Boolean(create_constraint=False)
    match = _DECIMAL.fullmatch(spark_type)
    if match:
        return Numeric(int(match.group(1)), int(match.group(2)), asdecimal=True)
    raise ValueError(f"{table}.{column}: unmapped Spark type {spark_type!r}")


def _build_table(name: str, columns: list[tuple[str, str]]) -> Table:
    table = Table(
        name,
        db.metadata,
        Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
        *[Column(col, sql_type(name, col, spark_type), nullable=True) for col, spark_type in columns],
        comment=f"Phase 5 analytics, loaded from hdfs:///urbantransit/analytics/{name}",
    )
    for col, _ in columns:
        if col in INDEXED_COLUMNS:
            Index(f"ix_{name}_{col}", table.c[col])
    return table


ANALYTICS_TABLES: dict[str, Table] = {name: _build_table(name, cols) for name, cols in ANALYTICS_SCHEMAS.items()}
