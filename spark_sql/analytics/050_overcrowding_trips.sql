-- name: overcrowding_trips
-- kind: output
-- item: 5
-- partitions: 4
-- Trip-level occupancy category from config/thresholds.yaml. Trips with NULL occupancy_pct
-- (no passenger count, or unknown vehicle capacity) are EXCLUDED, never labelled 'Low'.
SELECT trip_id, route_id, direction, service_date, day_class, time_period, hour, vehicle_id,
       capacity_total, max_load, max_load_stop_id, round(occupancy_pct, 4) AS occupancy_pct,
       occupancy_category, denied_boardings
FROM v_trip
WHERE occupancy_category IS NOT NULL
