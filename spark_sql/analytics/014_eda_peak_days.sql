-- name: eda_peak_days
-- kind: output
-- item: 1
-- Busiest service dates (system total of route estimated demand). routes_with_demand <
-- routes_in_service means some routes had no counted trip that day; the total is then a
-- lower bound, so both counts are kept.
WITH dc AS (
  SELECT service_date, max(day_class) AS day_class, max(holiday_name) AS holiday_name
  FROM v_trip GROUP BY service_date
)
SELECT r.service_date, r.day_of_week, dc.day_class, dc.holiday_name,
       round(sum(r.estimated_daily_boardings)) AS est_system_boardings,
       count(r.estimated_daily_boardings) AS routes_with_demand,
       count(*) AS routes_in_service,
       rank() OVER (ORDER BY sum(r.estimated_daily_boardings) DESC) AS busiest_rank
FROM route_daily_demand r
JOIN dc ON r.service_date = dc.service_date
GROUP BY r.service_date, r.day_of_week, dc.day_class, dc.holiday_name
