SELECT tr.*, v.capacity_total, v.vehicle_type
FROM trips tr LEFT JOIN vehicles v ON tr.vehicle_id = v.vehicle_id
