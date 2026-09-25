SELECT tr.*, s.planned_runtime_min, s.headway_min
FROM trips tr LEFT JOIN schedules s ON tr.schedule_id = s.schedule_id
