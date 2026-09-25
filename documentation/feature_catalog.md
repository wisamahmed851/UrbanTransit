# Phase 4 Feature Catalog

All Spark features are built only from Phase 3 clean Parquet (`/urbantransit/clean`, plus the delay quarantine table to know which trips lost their delay record). `Passenger_Counts` is the demand/occupancy source; smart-card `Tickets` is used for O-D and stop demand only. Parameters live in `config/phase4.yaml`.

## Output tables (`/urbantransit/features/`)

| table | grain | purpose |
|---|---|---|
| `trip_features` | one row per trip | the analysis-ready dataset; carries `split` |
| `route_daily_demand` | one row per route per service date | demand forecasting target and growth features; carries `split` |
| `route_features` | one row per route | static route profile; behavioural metrics computed from the **train split only** |
| `route_time_features` | route × day-of-week × hour × split | time-of-day profiles, each aggregated within its own split |
| `stop_daily_demand` | stop × service date | smart-card boardings per stop; carries `split` |

## Model-input rule

A column is safe as a **model input** only if its leakage note says *as-of* or *static*. Columns marked *same-trip outcome* or *descriptive* describe the trip or day being predicted and may only be used as **targets** or in Phase 5 descriptive analytics.

| feature | definition / formula | grain | sources | leakage note |
|---|---|---|---|---|
| boardings, alightings, max_load, denied_boardings | cleaned passenger-counter totals per trip; **NULL when the trip has no clean passenger_counts record** (never 0) | trip | trips, passenger_counts | same-trip outcome |
| passenger_count_measured | `boardings IS NOT NULL` | trip | passenger_counts | static (measurement indicator) |
| occupancy_pct / capacity_utilization | `max_load / capacity_total`; NULL when unmeasured or vehicle capacity unknown (DQ17) | trip / route-period | passenger_counts, vehicles | same-trip outcome |
| crowding_flag | `occupancy_pct > 0.9`; NULL when occupancy is NULL | trip | derived | same-trip outcome (target) |
| delay_minutes | see *Delay coverage* below: mean of the trip's delay records; 0.0 for completed trips with no record; NULL when not evaluated | trip | delays, trips | same-trip outcome (target) |
| delay_source | `record` / `within_tolerance` / `not_evaluated` | trip | delays, trips, delay quarantine | static (measurement indicator) |
| delay_severity | `On Time` < 5 min late (early running included), `Minor` [5,10), `Moderate` [10,20), `Severe` ≥ 20, with bands read from `config/thresholds.yaml` (`delay_severity`); NULL when delay_minutes is NULL | trip | delays | same-trip outcome (target) |
| trip_punctuality | `-2 < delay_minutes < 5`; NULL when delay_minutes is NULL | trip / route | delays | same-trip outcome (target) |
| arrival_delay_min | `actual_arrival - scheduled_arrival` at the last stop, from the trips table; available for every completed trip | trip | trips | same-trip outcome (full-coverage alternative delay target) |
| travel_time_min | actual arrival minus actual departure | trip | trips | same-trip outcome |
| schedule_deviation_min | actual minus scheduled departure | trip | trips | same-trip outcome |
| headway_minutes | actual departure minus the actual departure of the previous **operated** trip of the same route, service date and **direction** (ordered by `scheduled_departure, trip_id`; cancelled trips skipped) | trip | trips | same-trip outcome; the previous trip is strictly earlier |
| overtaking_flag | `headway_minutes < 0` (this bus left before the bus scheduled ahead of it: bunching) | trip | derived | same-trip outcome |
| historical_demand_average | mean boardings of earlier trips on the route (NULL trips are skipped, not averaged as 0) | trip | passenger_counts, trips | **as-of**: window ends at the preceding row |
| historical_delay_average | mean delay_minutes of earlier trips on the route (not-evaluated trips skipped) | trip | delays, trips | **as-of**: window ends at the preceding row |
| demand_wow_growth | `mean(estimated_daily_boardings, days d-7..d-1) / mean(days d-14..d-8) - 1` for the route; NULL without history | trip, route-day | route_daily_demand | **as-of**: only days before the service date |
| demand_mom_growth | same with 28-day windows (`d-28..d-1` vs `d-56..d-29`) | trip, route-day | route_daily_demand | **as-of**: only days before the service date |
| peak_hour_indicator | route-hour boardings / route-day boardings ≥ 0.08 **on the same day** | trip / route-period | passenger_counts, trips | **descriptive only**: uses hours after the trip. Phase 5 analytics only, never a model input |
| peak_hour_share_asof, **peak_hour_indicator_asof** | mean share of daily ridership in this route-hour over the previous 28 days of the same weekday/weekend type; flag = share ≥ 0.08 | trip | passenger_counts, trips | **as-of**: current day excluded. **Models (Phases 6-9) must use this one** |
| hourly_boardings, daily_boardings | same-day sums behind `peak_hour_indicator` | trip | passenger_counts | descriptive only |
| route_load_factor | mean trip occupancy | route-day, route | trip features | route-day: same-day outcome; route_features: static (train split) |
| route_reliability_delay_min, trip_punctuality_rate, arrival_delay_std_min | mean trip delay / punctuality rate / spread of arrival delay | route-day, route | trip features | route-day: same-day outcome; route_features: static (train split) |
| scheduled_trips, operated_trips, measured_trips, demand_coverage | trip counts per route-day; `coverage = measured / operated` | route-day | trips | same-day outcome |
| passenger_count | sum of **measured** boardings per route-day | route-day | passenger_counts | same-day outcome |
| estimated_daily_boardings | `passenger_count / measured_trips * operated_trips` (unmeasured trips scaled, not counted as zero) | route-day | derived | daily forecasting target |
| stop boarding_count | smart-card entry taps per stop/day | stop-day | tickets, stops | same-day outcome; stated smart-card limitation |
| day_of_week / weekend_indicator / hour | calendar derivatives of service_date / scheduled departure | trip | trips | static (known in advance) |
| split | chronological train/validation/test date assignment | all model grains | trips | an entire date belongs to exactly one split |

## Delay coverage (why `delay_minutes` is 0 for some trips and NULL for others)

`Delays` is an **exception log**, not a measurement of every trip. The Phase 1 generator (`data_generator/simulation.py`, `_derive_delays`) writes a record only for an **operated** trip that is at least 5 min late at its timing point, that runs early (≤ -2 min at the last stop), or that breaks down. Big delays (≥ 10 min) get a second record at the last stop. Therefore:

| delay_source | condition | delay_minutes |
|---|---|---|
| `record` | trip has ≥ 1 clean delay record | mean of its records |
| `within_tolerance` | completed trip, no record, no quarantined record | **0.0**. The true deviation is somewhere in (-2, 5) minutes; 0 stands for "inside tolerance", and severity/punctuality are exact for these trips because the On Time / punctual band is defined as that same interval |
| `not_evaluated` | cancelled trip (never ran), or a delay record for the trip was quarantined in Phase 3 (DQ08a) | **NULL**. The measurement does not exist or was lost |

Consequence: trips with `delay_source = 'not_evaluated'` are excluded from delay-severity classification. `arrival_delay_min` covers every completed trip if a full-coverage delay target is needed.

## Passenger-count coverage

Trips without a clean `passenger_counts` record (no counter data, or the record was quarantined for DQ06/DQ10) have NULL boardings, alightings, max_load, occupancy_pct, crowding_flag and denied_boardings. `historical_demand_average` and all aggregates use `avg()`/`sum()`, which skip NULLs. Route-day demand uses `estimated_daily_boardings`, which scales measured trips up to all operated trips.

## Chronological split

`split_dates()` sorts the distinct service dates. The first `round(n * train_fraction)` dates are train, the next `round(n * validation_fraction)` are validation, and the rest (most recent) are test. Both fractions are read from `config/phase4.yaml`. Changing them and rerunning is the only change needed.

## Accepted limitations

- **Ticket orphans:** 5,973 tickets reference a passenger that is not in `passengers`, and 6,083 tickets reference a trip that is not in `trips`. Phase 4 checked every one: 100% carry the Phase 3 flag `DQ15` (unknown passenger) or `DQ16` (missing trip record) respectively (`reports/phase4_investigation.json`). These are deliberately injected defects that Phase 3 **flags and keeps** by documented rule (`documentation/cleaning_rules.md`): the taps are real journeys and still count for stop demand; only passenger segmentation (DQ15) or the trip-level join (DQ16) is impossible. There is no Phase 3 gap. Consumers exclude them with `array_contains(dq_flags, 'DQ15' | 'DQ16')`.
- **Negative headways:** the original job partitioned by route and date but not by **direction**, so a bus was compared with the previous bus running the opposite way. That produced 19,045 negative headways, and 18 of them were trips crossing midnight. This was a bug and is fixed by partitioning by direction. The remaining negatives come from overtaking: the previous scheduled bus left late by more than the scheduled gap (bunching, which the generator simulates). They are kept and flagged with `overtaking_flag`. Midnight is not a problem because headways are computed from full timestamps within a service date.

## Verification

`spark_jobs/verify_phase4.py` checks:
- **Split integrity:** each date has exactly one split, the splits are in chronological order, and their sizes match the config.
- **NULL semantics:** boardings are NULL exactly for trips without a clean count, and delay_minutes is NULL exactly for `not_evaluated` trips.
- **Historical averages:** recomputed for routes R001-R005.
- **Leakage test:** `demand_*_growth` and `peak_hour_*_asof` are recomputed on data **truncated** at the first test date, and again with that date's own demand ×10. The stored values must be identical in both cases.
