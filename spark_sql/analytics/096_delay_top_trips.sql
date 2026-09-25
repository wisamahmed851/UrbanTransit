-- name: delay_top_trips
-- kind: output
-- item: 9
-- Trip-level view: the 500 most delayed evaluated trips (recorded delay).
SELECT trip_id, route_id, direction, service_date, time_period, day_class, vehicle_id,
       round(delay_minutes, 2) AS delay_minutes, delay_severity, round(arrival_delay_min, 2) AS arrival_delay_min
FROM v_trip
WHERE delay_minutes IS NOT NULL
ORDER BY delay_minutes DESC, trip_id
LIMIT 500
