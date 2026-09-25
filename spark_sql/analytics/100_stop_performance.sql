-- name: stop_performance
-- kind: output
-- item: 10
-- One row per stop: demand (expanded card taps), turnover, delay, trip frequency, route
-- connectivity, weekday demand by period and the bottleneck flag from delay_by_stop.
WITH n AS (
  SELECT count(DISTINCT service_date) AS days FROM v_trip
), tp AS (
  SELECT stop_id,
         sum(CASE WHEN time_period = 'morning_peak' THEN est_boardings_per_day END) AS weekday_morning_peak_boardings,
         sum(CASE WHEN time_period = 'midday' THEN est_boardings_per_day END) AS weekday_midday_boardings,
         sum(CASE WHEN time_period = 'evening_peak' THEN est_boardings_per_day END) AS weekday_evening_peak_boardings,
         sum(CASE WHEN time_period IN ('early_morning', 'evening') THEN est_boardings_per_day END) AS weekday_offpeak_boardings
  FROM eda_stop_patterns WHERE day_class = 'weekday' GROUP BY stop_id
)
SELECT u.stop_id, u.stop_name, u.zone, u.stop_type,
       u.est_boardings_per_day, u.est_alightings_per_day, u.est_turnover_per_day,
       b.routes_serving,
       round(b.trips_serving / n.days, 1) AS trips_serving_per_day,
       round(try_divide(u.est_turnover_per_day, b.trips_serving / n.days), 3) AS turnover_per_trip,
       b.late_records, b.avg_record_delay_min, b.late_record_rate, b.congestion_record_rate, b.top_reason,
       coalesce(b.is_bottleneck, false) AS is_bottleneck,
       round(tp.weekday_morning_peak_boardings, 2) AS weekday_morning_peak_boardings,
       round(tp.weekday_midday_boardings, 2) AS weekday_midday_boardings,
       round(tp.weekday_evening_peak_boardings, 2) AS weekday_evening_peak_boardings,
       round(tp.weekday_offpeak_boardings, 2) AS weekday_offpeak_boardings
FROM eda_stop_usage u
CROSS JOIN n
LEFT JOIN delay_by_stop b ON u.stop_id = b.stop_id
LEFT JOIN tp ON u.stop_id = tp.stop_id
