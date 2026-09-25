# Phase 4 Feature Catalog

All Spark features are built only from Phase 3 clean Parquet. `Passenger_Counts` is the demand/occupancy source; smart-card `Tickets` is used for O-D and stop demand only.

| feature | definition / formula | grain | sources | leakage note |
|---|---|---|---|---|
| boardings, alightings, max_load | cleaned passenger-counter totals per trip | trip | trips, passenger_counts | same-trip observation; not a historical predictor |
| occupancy_pct / capacity_utilization | `max_load / capacity_total` | trip / route-period | passenger_counts, vehicles | same-trip target-time state |
| delay_minutes / delay_severity | mean delay record; configurable threshold class | trip | delays | same-trip target |
| travel_time_min | actual arrival minus actual departure | trip | trips | same-trip outcome |
| schedule_deviation_min | actual minus scheduled departure | trip | trips | same-trip outcome |
| trip_punctuality | `abs(delay_minutes) <= 1` | trip / route | delays | same-trip target |
| headway_minutes | current actual departure minus prior route/date departure | trip | trips | previous ordered event only |
| historical_demand_average | mean prior route boardings | trip | passenger_counts, trips | window ends at preceding row |
| historical_delay_average | mean prior route delays | trip | delays, trips | window ends at preceding row |
| peak_hour_indicator | route-hour boardings / route-day boardings >= configured threshold | trip / route-period | passenger_counts, trips | descriptive aggregate; exclude for prospective forecasting if needed |
| route_load_factor | mean trip occupancy | route-day | trip features | aggregation at stated grain |
| route_reliability_delay_min | mean trip delay | route-day | trip features | aggregation at stated grain |
| stop boarding_count | smart-card entry taps per stop/day | stop-day | tickets, stops | stated smart-card limitation |
| daily demand | passenger boardings summed by route/day; ticket entries by stop/day | route-day / stop-day | passenger_counts / tickets | daily target, not future feature |
| day_of_week / weekend_indicator | calendar derivatives of service_date | trip | trips | no future data |
| split | chronological train/validation/test date assignment | all model grains | trips | an entire date belongs to exactly one split |

The executable check in `spark_jobs/verify_phase4.py` recomputes historical demand for a deterministic route sample using `scheduled_departure, trip_id` and compares it with stored values.
