-- name: delay_consistent_entities
-- kind: output
-- item: 9
-- Routes and vehicles that are CONSISTENTLY delayed: their daily late share (evaluated trips,
-- delay >= 5 min) is above the system's late share for that same day on >= 75% of their days.
-- Comparing with the same day's system rate removes city-wide bad days (weather, protests).
WITH late AS (
  SELECT v.*, CASE WHEN delay_minutes >= ${on_time_late_min} THEN 1.0 WHEN delay_minutes IS NOT NULL THEN 0.0 END AS is_late
  FROM v_trip v
), sys AS (
  SELECT service_date, avg(is_late) AS system_late_share FROM late GROUP BY service_date
), e AS (
  SELECT 'route' AS entity_type, route_id AS entity_id, service_date, count(is_late) AS n, avg(is_late) AS late_share
  FROM late GROUP BY route_id, service_date
  UNION ALL
  SELECT 'vehicle', vehicle_id, service_date, count(is_late), avg(is_late)
  FROM late WHERE vehicle_id IS NOT NULL GROUP BY vehicle_id, service_date
), g AS (
  SELECT e.entity_type, e.entity_id, count(*) AS days, sum(e.n) AS evaluated_trips,
         avg(e.late_share) AS avg_daily_late_share,
         avg(CASE WHEN e.late_share > s.system_late_share THEN 1.0 ELSE 0.0 END) AS share_days_above_system
  FROM e JOIN sys s ON e.service_date = s.service_date
  WHERE e.late_share IS NOT NULL
  GROUP BY e.entity_type, e.entity_id
)
SELECT entity_type, entity_id, days, evaluated_trips,
       round(avg_daily_late_share, 4) AS avg_daily_late_share,
       round(share_days_above_system, 4) AS share_days_above_system,
       (days >= ${delay_min_days}
        AND (entity_type = 'route' OR evaluated_trips >= ${delay_min_vehicle_trips})
        AND share_days_above_system >= ${delay_consistent_share_of_days}) AS consistently_delayed
FROM g
