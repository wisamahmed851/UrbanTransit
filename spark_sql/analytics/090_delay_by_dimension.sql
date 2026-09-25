-- name: delay_by_dimension
-- kind: output
-- item: 9
-- Delay by route, vehicle, hour, day of week, direction, time period, day class, route
-- distance band and route type, in one long table (dimension, dim_value).
-- delay_minutes covers evaluated trips only; arrival_delay_min covers every completed trip.
SELECT dimension, dim_value,
       count(*) AS trips,
       count(delay_minutes) AS evaluated_trips,
       round(avg(delay_minutes), 3) AS avg_delay_min,
       round(avg(CASE WHEN delay_minutes >= ${on_time_late_min} THEN 1.0
                      WHEN delay_minutes IS NOT NULL THEN 0.0 END), 4) AS late_share,
       round(avg(arrival_delay_min), 3) AS avg_arrival_delay_min,
       round(percentile_approx(arrival_delay_min, 0.9), 2) AS p90_arrival_delay_min
FROM (SELECT v.*, ${distance_band_case} AS distance_band FROM v_trip v) t
LATERAL VIEW stack(9,
    'route', route_id,
    'vehicle', vehicle_id,
    'hour', lpad(CAST(hour AS STRING), 2, '0'),
    'day_of_week', CAST(day_of_week AS STRING),
    'direction', CAST(direction AS STRING),
    'time_period', time_period,
    'day_class', day_class,
    'distance_band', distance_band,
    'route_type', route_type) s AS dimension, dim_value
WHERE dim_value IS NOT NULL
GROUP BY dimension, dim_value
