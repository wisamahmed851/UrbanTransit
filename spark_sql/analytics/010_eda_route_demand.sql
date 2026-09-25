-- name: eda_route_demand
-- kind: output
-- item: 1
-- Highest / lowest demand routes. Demand = estimated_daily_boardings (Phase 4: measured
-- boardings scaled to all operated trips; unmeasured trips are never counted as zero).
-- Ranked by the average per service day so routes launched mid-year are compared fairly.
SELECT d.route_id, r.route_code, r.route_type, r.launch_date,
       count(*) AS service_days,
       round(sum(d.estimated_daily_boardings)) AS est_total_boardings,
       round(avg(d.estimated_daily_boardings), 1) AS avg_daily_boardings,
       round(avg(d.demand_coverage), 3) AS avg_demand_coverage,
       dense_rank() OVER (ORDER BY avg(d.estimated_daily_boardings) DESC) AS demand_rank
FROM route_daily_demand d
JOIN routes r ON d.route_id = r.route_id
WHERE d.estimated_daily_boardings IS NOT NULL
GROUP BY d.route_id, r.route_code, r.route_type, r.launch_date
