SELECT tr.*, r.route_code, r.route_type, r.distance_km
FROM trips tr LEFT JOIN routes r ON tr.route_id = r.route_id
