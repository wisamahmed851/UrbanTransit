-- name: service_frequency
-- kind: output
-- item: 15
-- Scheduled frequency vs demand, occupancy, as-of peak demand and delay:
--   too_little  : average occupancy >= 0.85 or >= 20% of counted trips Overcrowded/Critical
--   too_much    : average occupancy < 0.30, p90 < 0.50 and >= 2 trips/h
--   well_matched: everything else;  insufficient_data: < 30 counted trips
WITH c AS (
  SELECT route_id, direction, day_class, time_period,
         count(DISTINCT service_date) AS days,
         count(*) AS scheduled_trips,
         sum(CASE WHEN trip_status = 'completed' THEN 1 ELSE 0 END) AS operated_trips,
         count(occupancy_pct) AS measured_trips,
         avg(boardings) AS avg_boardings,
         avg(occupancy_pct) AS avg_occupancy,
         percentile_approx(occupancy_pct, 0.9) AS p90_occupancy,
         avg(CASE WHEN occupancy_category IN (${overload_list}) THEN 1.0 WHEN occupancy_category IS NOT NULL THEN 0.0 END) AS overload_share,
         avg(CAST(peak_hour_indicator_asof AS DOUBLE)) AS peak_rate_asof,
         avg(arrival_delay_min) AS avg_arrival_delay_min
  FROM v_trip GROUP BY route_id, direction, day_class, time_period
)
SELECT route_id, direction, day_class, time_period, days, scheduled_trips, operated_trips, measured_trips,
       round(scheduled_trips / (days * ${period_hours_case}), 2) AS scheduled_trips_per_hour,
       round(avg_boardings, 2) AS avg_boardings_per_trip,
       round(avg_occupancy, 4) AS avg_occupancy, round(p90_occupancy, 4) AS p90_occupancy,
       round(overload_share, 4) AS overload_share, round(peak_rate_asof, 4) AS peak_rate_asof,
       round(avg_arrival_delay_min, 3) AS avg_arrival_delay_min,
       CASE WHEN measured_trips < ${underutilized_min_measured_trips} THEN 'insufficient_data'
            WHEN avg_occupancy >= ${frequency_too_little_avg_occupancy}
                 OR overload_share >= ${frequency_too_little_overload_share} THEN 'too_little'
            WHEN avg_occupancy < ${frequency_too_much_avg_occupancy} AND p90_occupancy < ${frequency_too_much_p90_occupancy}
                 AND scheduled_trips / (days * ${period_hours_case}) >= ${frequency_min_trips_per_hour} THEN 'too_much'
            ELSE 'well_matched' END AS frequency_match
FROM c
