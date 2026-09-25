-- name: v_normal_days
-- kind: view
-- item: 0
-- Route-days used for baselines and route judgements: no spike/drop, not a holiday.
-- One abnormal day therefore cannot flag a route (SRS tricky case).
SELECT route_id, service_date
FROM special_event_route_days
WHERE day_status IN ('normal', 'insufficient_history') AND NOT is_holiday
