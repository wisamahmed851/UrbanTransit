-- name: special_event_route_days
-- kind: output
-- item: 17
-- Each route-day's estimated demand vs a ROBUST baseline: the median of the same route on
-- the same weekday AND the same calendar day type (weekday / ramadan_weekday / saturday /
-- sunday / holiday) over the previous 8 weeks (the current week is excluded). A median is
-- not moved by a few spike days, so events never redefine "normal" demand; matching the day
-- type stops the reduced Ramadan timetable (or a holiday) from becoming the baseline for
-- ordinary days.
-- event_extra_trips (generator-scheduled event trips) is shown for validation only;
-- detection uses demand alone.
WITH dt AS (
  SELECT service_date, max_by(day_type, n) AS day_type
  FROM (SELECT service_date, day_type, count(*) AS n FROM v_trip GROUP BY service_date, day_type) x
  GROUP BY service_date
), d AS (
  SELECT r.route_id, r.service_date, r.day_of_week, dt.day_type, r.estimated_daily_boardings AS demand,
         datediff(r.service_date, DATE'2000-01-01') AS day_idx
  FROM route_daily_demand r JOIN dt ON r.service_date = dt.service_date
  WHERE r.estimated_daily_boardings IS NOT NULL
), b AS (
  SELECT d.*, array_sort(collect_list(demand) OVER (
           PARTITION BY route_id, day_of_week, day_type ORDER BY day_idx
           RANGE BETWEEN ${events_baseline_days} PRECEDING AND 7 PRECEDING)) AS hist
  FROM d
), m AS (
  SELECT route_id, service_date, day_of_week, day_type, demand, size(hist) AS baseline_days,
         CASE WHEN size(hist) = 0 THEN NULL
              WHEN size(hist) % 2 = 1 THEN element_at(hist, CAST((size(hist) + 1) div 2 AS INT))
              ELSE (element_at(hist, CAST(size(hist) div 2 AS INT))
                    + element_at(hist, CAST(size(hist) div 2 + 1 AS INT))) / 2 END AS baseline
  FROM b
), x AS (
  SELECT route_id, service_date, count(*) AS event_extra_trips
  FROM v_trip WHERE trip_type = 'event_extra' GROUP BY route_id, service_date
)
SELECT m.route_id, m.service_date, m.day_of_week, m.day_type,
       round(m.demand, 1) AS observed_demand, round(m.baseline, 1) AS baseline_demand, m.baseline_days,
       round(try_divide(m.demand, m.baseline), 3) AS demand_ratio,
       h.holiday_name IS NOT NULL AS is_holiday, h.holiday_name,
       coalesce(x.event_extra_trips, 0) AS event_extra_trips,
       CASE WHEN m.baseline_days < ${events_min_baseline_days} THEN 'insufficient_history'
            WHEN try_divide(m.demand, m.baseline) >= ${events_spike_ratio} THEN 'spike'
            WHEN try_divide(m.demand, m.baseline) <= ${events_drop_ratio} THEN 'drop'
            ELSE 'normal' END AS day_status
FROM m
LEFT JOIN holidays h ON m.service_date = h.service_date
LEFT JOIN x ON m.route_id = x.route_id AND m.service_date = x.service_date
