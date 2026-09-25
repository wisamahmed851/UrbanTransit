-- name: underutilized_services
-- kind: output
-- item: 7
-- Low occupancy judged together with frequency, route length, time period and day class.
--   underutilized         : low average AND low p90 occupancy AND boardings per km below the
--                           period median AND frequent enough (>= 2 trips/h) to trim service
--   low_use_low_frequency : equally empty but already infrequent - cutting it would remove
--                           coverage, so it is reported, not recommended for cuts
-- Cells with fewer than min_measured_trips counted trips are 'insufficient_data'.
WITH c AS (
  SELECT route_id, direction, day_class, time_period,
         max(distance_km) AS distance_km,
         count(DISTINCT service_date) AS days,
         sum(CASE WHEN trip_status = 'completed' THEN 1 ELSE 0 END) AS operated_trips,
         count(occupancy_pct) AS measured_trips,
         avg(occupancy_pct) AS avg_occupancy,
         percentile_approx(occupancy_pct, 0.9) AS p90_occupancy,
         avg(boardings) AS avg_boardings
  FROM v_trip GROUP BY route_id, direction, day_class, time_period
), m AS (
  SELECT c.*, operated_trips / (days * ${period_hours_case}) AS trips_per_hour,
         try_divide(avg_boardings, distance_km) AS boardings_per_km
  FROM c
), med AS (
  SELECT time_period, percentile_approx(boardings_per_km, 0.5) AS period_median_boardings_per_km
  FROM m GROUP BY time_period
)
SELECT m.route_id, m.direction, m.day_class, m.time_period, m.distance_km, m.days, m.operated_trips,
       m.measured_trips, round(m.trips_per_hour, 2) AS trips_per_hour,
       round(m.avg_occupancy, 4) AS avg_occupancy, round(m.p90_occupancy, 4) AS p90_occupancy,
       round(m.avg_boardings, 2) AS avg_boardings_per_trip, round(m.boardings_per_km, 3) AS boardings_per_km,
       round(med.period_median_boardings_per_km, 3) AS period_median_boardings_per_km,
       CASE WHEN m.measured_trips < ${underutilized_min_measured_trips} THEN 'insufficient_data'
            WHEN m.avg_occupancy < ${underutilized_max_avg_occupancy} AND m.p90_occupancy < ${underutilized_max_p90_occupancy}
                 AND m.boardings_per_km < med.period_median_boardings_per_km
                 AND m.trips_per_hour >= ${underutilized_min_trips_per_hour} THEN 'underutilized'
            WHEN m.avg_occupancy < ${underutilized_max_avg_occupancy} AND m.p90_occupancy < ${underutilized_max_p90_occupancy}
                 AND m.boardings_per_km < med.period_median_boardings_per_km THEN 'low_use_low_frequency'
            ELSE 'adequate' END AS utilization_status
FROM m JOIN med ON m.time_period = med.time_period
