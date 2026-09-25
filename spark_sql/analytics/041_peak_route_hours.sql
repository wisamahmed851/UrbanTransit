-- name: peak_route_hours
-- kind: output
-- item: 4
-- Route-specific peaks: an hour is a route peak when >= 50% of its trips are flagged by the
-- leak-free peak_hour_indicator_asof (share of the route's daily ridership over the previous
-- 28 days >= 8%). hour_rank orders hours by that as-of share.
SELECT route_id, day_class, hour,
       count(*) AS trips,
       count(peak_hour_indicator_asof) AS asof_trips,
       round(avg(CAST(peak_hour_indicator_asof AS DOUBLE)), 4) AS peak_rate_asof,
       round(avg(peak_hour_share_asof), 4) AS avg_share_asof,
       round(avg(boardings), 2) AS avg_boardings_per_trip,
       avg(CAST(peak_hour_indicator_asof AS DOUBLE)) >= ${peak_asof_peak_rate} AS is_route_peak_hour,
       rank() OVER (PARTITION BY route_id, day_class ORDER BY avg(peak_hour_share_asof) DESC NULLS LAST) AS hour_rank
FROM v_trip
GROUP BY route_id, day_class, hour
