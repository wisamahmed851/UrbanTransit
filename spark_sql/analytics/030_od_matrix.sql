-- name: od_matrix
-- kind: output
-- item: 3
-- partitions: 4
-- Origin-destination matrix, filterable by route, period, stop and service type
-- (service_type = routes.route_type) and day type. est_passengers = card journeys x
-- expansion factor; card_journeys keeps the raw sample so small cells can be judged.
-- Example filter:  SELECT * FROM od_matrix WHERE route_id = 'R012' AND time_period = 'morning_peak'
SELECT k.entry_stop_id AS origin_stop_id, so.stop_name AS origin_stop_name,
       k.exit_stop_id AS destination_stop_id, sd.stop_name AS destination_stop_name,
       k.route_id, k.route_type AS service_type, k.direction,
       k.entry_time_period AS time_period, k.day_class, k.day_type,
       count(*) AS card_journeys,
       round(sum(k.expansion_factor), 2) AS est_passengers,
       count(DISTINCT k.service_date) AS days_observed
FROM v_ticket k
LEFT JOIN stops so ON k.entry_stop_id = so.stop_id
LEFT JOIN stops sd ON k.exit_stop_id = sd.stop_id
GROUP BY k.entry_stop_id, so.stop_name, k.exit_stop_id, sd.stop_name, k.route_id, k.route_type, k.direction,
         k.entry_time_period, k.day_class, k.day_type
