-- name: schedule_adherence
-- kind: output
-- item: 13
-- Early / on-time / late arrivals (completed trips, arrival_delay_min against the -2..5 min
-- band), missed (cancelled) trips and irregular intervals (headway bunched or gapped against
-- the scheduled gap), per route and day class.
WITH a AS (
  SELECT route_id, day_class,
         count(*) AS scheduled_trips,
         sum(CASE WHEN trip_status = 'cancelled' THEN 1 ELSE 0 END) AS missed_trips,
         count(arrival_delay_min) AS completed_trips,
         sum(CASE WHEN arrival_delay_min <= ${on_time_early_min} THEN 1 ELSE 0 END) AS early_arrivals,
         sum(CASE WHEN arrival_delay_min > ${on_time_early_min} AND arrival_delay_min < ${on_time_late_min} THEN 1 ELSE 0 END) AS on_time_arrivals,
         sum(CASE WHEN arrival_delay_min >= ${on_time_late_min} THEN 1 ELSE 0 END) AS late_arrivals
  FROM v_trip GROUP BY route_id, day_class
), h AS (
  SELECT route_id, day_class,
         count(headway_status) AS intervals_assessed,
         sum(CASE WHEN headway_status IN ('bunched', 'gap') THEN 1 ELSE 0 END) AS irregular_intervals
  FROM v_headway GROUP BY route_id, day_class
)
SELECT a.route_id, a.day_class, a.scheduled_trips, a.missed_trips, a.completed_trips,
       a.early_arrivals, a.on_time_arrivals, a.late_arrivals,
       round(try_divide(a.early_arrivals, a.completed_trips), 4) AS early_share,
       round(try_divide(a.on_time_arrivals, a.completed_trips), 4) AS on_time_share,
       round(try_divide(a.late_arrivals, a.completed_trips), 4) AS late_share,
       round(a.missed_trips / a.scheduled_trips, 4) AS missed_share,
       h.intervals_assessed, h.irregular_intervals,
       round(try_divide(h.irregular_intervals, h.intervals_assessed), 4) AS irregular_interval_share
FROM a LEFT JOIN h ON a.route_id = h.route_id AND a.day_class = h.day_class
