-- name: v_ticket
-- kind: view
-- cache: true
-- item: 0
-- Smart-card journeys (a ~3-4% sample of riders) with their trip context and expansion
-- factor. Tickets flagged DQ16 (trip record missing) drop out here: no trip, no route/period.
-- journey_km = distance along the route between the two stops; straight-line (haversine)
-- distance is used only when a stop is not on the trip's route/direction.
WITH rsd AS (
  SELECT route_id, direction, stop_id, min(distance_from_start_km) AS km
  FROM route_stops GROUP BY route_id, direction, stop_id
)
SELECT k.ticket_id, k.passenger_id, k.trip_id, k.entry_stop_id, k.exit_stop_id, k.entry_time, k.exit_time,
       k.ticket_type, k.fare_category, k.dq_flags,
       v.route_id, v.direction, v.route_type, v.service_date, v.day_of_week, v.time_period, v.day_type,
       v.day_class, v.year_month,
       hour(k.entry_time) AS entry_hour,
       ${time_period_case_entry} AS entry_time_period,
       ${time_period_case_exit} AS exit_time_period,
       (unix_timestamp(k.exit_time) - unix_timestamp(k.entry_time)) / 60 AS ride_min,
       e.expansion_factor,
       coalesce(abs(re.km - rs.km),
                2 * 6371 * asin(sqrt(pow(sin(radians(s2.latitude - s1.latitude) / 2), 2)
                  + cos(radians(s1.latitude)) * cos(radians(s2.latitude))
                  * pow(sin(radians(s2.longitude - s1.longitude) / 2), 2)))) AS journey_km
FROM tickets k
JOIN v_trip v ON k.trip_id = v.trip_id
JOIN ticket_expansion_factor e
  ON v.route_id = e.route_id AND v.year_month = e.year_month AND v.time_period = e.time_period
LEFT JOIN rsd rs ON rs.route_id = v.route_id AND rs.direction = v.direction AND rs.stop_id = k.entry_stop_id
LEFT JOIN rsd re ON re.route_id = v.route_id AND re.direction = v.direction AND re.stop_id = k.exit_stop_id
LEFT JOIN stops s1 ON s1.stop_id = k.entry_stop_id
LEFT JOIN stops s2 ON s2.stop_id = k.exit_stop_id
