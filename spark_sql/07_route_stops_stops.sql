SELECT rs.*, s.stop_name, s.latitude, s.longitude
FROM route_stops rs LEFT JOIN stops s ON rs.stop_id = s.stop_id
