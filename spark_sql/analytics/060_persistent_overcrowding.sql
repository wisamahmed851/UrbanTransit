-- name: persistent_overcrowding
-- kind: output
-- item: 6
-- Repeated overload vs one-off events. Cell = route x direction x day-of-week x time period.
-- A day counts as "overloaded" if any measured trip in the cell was Overcrowded/Critical.
-- Only normal days are judged (special-event spikes, drops and holidays are excluded);
-- overloads on those excluded days are reported separately as event_day_overloads.
--   persistent = overloaded on >= 4 days AND >= 50% of observed days
--   one_off    = overloaded on 1-2 days;  recurring = anything in between
WITH d AS (
  SELECT v.route_id, v.direction, v.day_of_week, v.time_period, v.service_date,
         n.route_id IS NOT NULL AS normal_day,
         max(CASE WHEN v.occupancy_category IN (${overload_list}) THEN 1 ELSE 0 END) AS overloaded,
         max(v.occupancy_pct) AS max_occ
  FROM v_trip v
  LEFT JOIN v_normal_days n ON v.route_id = n.route_id AND v.service_date = n.service_date
  WHERE v.occupancy_category IS NOT NULL
  GROUP BY v.route_id, v.direction, v.day_of_week, v.time_period, v.service_date, n.route_id
), c AS (
  SELECT route_id, direction, day_of_week, time_period,
         sum(CASE WHEN normal_day THEN 1 ELSE 0 END) AS days_observed,
         sum(CASE WHEN normal_day THEN overloaded ELSE 0 END) AS days_overloaded,
         sum(CASE WHEN NOT normal_day THEN overloaded ELSE 0 END) AS event_day_overloads,
         max(CASE WHEN normal_day THEN max_occ END) AS max_occupancy
  FROM d GROUP BY route_id, direction, day_of_week, time_period
)
SELECT c.*,
       round(try_divide(days_overloaded, days_observed), 4) AS overload_day_share,
       CASE WHEN days_observed < ${overcrowding_min_days_observed} THEN 'insufficient_data'
            WHEN days_overloaded >= ${overcrowding_persistent_min_days}
                 AND days_overloaded / days_observed >= ${overcrowding_persistent_min_share} THEN 'persistent'
            WHEN days_overloaded = 0 THEN 'none'
            WHEN days_overloaded <= ${overcrowding_one_off_max_days} THEN 'one_off'
            ELSE 'recurring' END AS overload_pattern
FROM c
