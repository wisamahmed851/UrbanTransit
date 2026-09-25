-- name: route_reliability
-- kind: output
-- item: 12
-- % on time (evaluated trips, on-time band from phase4.yaml), delay variation (std of arrival
-- delay), missed schedules (cancelled trips), early / late arrivals (completed trips) and
-- travel-time consistency (mean CV of travel time within route/direction/day class/period).
WITH cv AS (
  SELECT route_id, avg(cv) AS travel_time_cv
  FROM (SELECT route_id, direction, day_class, time_period,
               try_divide(stddev(travel_time_min), avg(travel_time_min)) AS cv
        FROM v_trip GROUP BY route_id, direction, day_class, time_period) x
  GROUP BY route_id
), r AS (
  SELECT route_id,
         count(*) AS scheduled_trips,
         sum(CASE WHEN trip_status = 'cancelled' THEN 1 ELSE 0 END) AS missed_trips,
         count(delay_minutes) AS evaluated_trips,
         avg(CAST(trip_punctuality AS DOUBLE)) AS on_time_rate,
         avg(CASE WHEN arrival_delay_min <= ${on_time_early_min} THEN 1.0 WHEN arrival_delay_min IS NOT NULL THEN 0.0 END) AS early_arrival_share,
         avg(CASE WHEN arrival_delay_min >= ${on_time_late_min} THEN 1.0 WHEN arrival_delay_min IS NOT NULL THEN 0.0 END) AS late_arrival_share,
         stddev(arrival_delay_min) AS arrival_delay_std
  FROM v_trip GROUP BY route_id
)
SELECT r.route_id, r.scheduled_trips, r.missed_trips,
       round(r.missed_trips / r.scheduled_trips, 4) AS missed_share,
       r.evaluated_trips,
       round(r.on_time_rate, 4) AS on_time_rate,
       round(r.early_arrival_share, 4) AS early_arrival_share,
       round(r.late_arrival_share, 4) AS late_arrival_share,
       round(r.arrival_delay_std, 3) AS arrival_delay_std,
       round(cv.travel_time_cv, 4) AS travel_time_cv,
       rank() OVER (ORDER BY r.on_time_rate DESC) AS on_time_rank
FROM r LEFT JOIN cv ON r.route_id = cv.route_id
