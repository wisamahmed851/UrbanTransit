-- name: v_trip
-- kind: view
-- cache: true
-- item: 0
-- Base trip view for every analysis. It deliberately does NOT expose the descriptive
-- (same-day, leaky) peak_hour_indicator / hourly_boardings / daily_boardings columns,
-- so peak analyses can only use the leak-free *_asof columns.
-- occupancy_category is NULL when occupancy_pct is NULL (unmeasured trip), never 'Low'.
SELECT t.trip_id, t.route_id, t.direction, t.service_date, t.service_id, t.schedule_id, t.vehicle_id, t.year_month,
       t.scheduled_departure, t.scheduled_arrival, t.actual_departure, t.actual_arrival, t.trip_status, t.trip_type,
       t.boardings, t.alightings, t.max_load, t.denied_boardings, t.capacity_total, t.distance_km, t.route_type,
       t.planned_runtime_min, t.headway_min, t.passenger_count_measured, t.occupancy_pct, t.travel_time_min,
       t.schedule_deviation_min, t.arrival_delay_min, t.delay_source, t.delay_minutes, t.delay_severity,
       t.trip_punctuality, t.hour, t.day_of_week, t.weekend_indicator, t.headway_minutes, t.overtaking_flag,
       t.peak_hour_share_asof, t.peak_hour_indicator_asof, t.split,
       sc.day_type,
       CASE WHEN sc.day_type = 'holiday' OR h.service_date IS NOT NULL THEN 'holiday'
            WHEN t.weekend_indicator THEN 'weekend' ELSE 'weekday' END AS day_class,
       h.holiday_name,
       ${time_period_case_trip} AS time_period,
       ${occupancy_case} AS occupancy_category,
       (unix_timestamp(t.scheduled_arrival) - unix_timestamp(t.scheduled_departure)) / 60 AS scheduled_runtime_min,
       pc.max_load_stop_id
FROM trip_features t
LEFT JOIN service_calendar sc ON t.service_id = sc.service_id
LEFT JOIN holidays h ON t.service_date = h.service_date
LEFT JOIN (SELECT trip_id, max(max_load_stop_id) AS max_load_stop_id FROM passenger_counts GROUP BY trip_id) pc
       ON t.trip_id = pc.trip_id
