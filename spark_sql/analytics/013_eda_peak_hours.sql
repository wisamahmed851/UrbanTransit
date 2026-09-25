-- name: eda_peak_hours
-- kind: output
-- item: 1
-- Demand by hour and day class. est_boardings_per_day scales the mean of MEASURED trips to all
-- operated trips. peak_rate_asof = share of trips flagged by the leak-free Phase 4 indicator.
SELECT day_class, hour,
       count(DISTINCT service_date) AS days,
       count(*) AS trips,
       count(boardings) AS measured_trips,
       round(avg(boardings), 2) AS avg_boardings_per_trip,
       round(avg(boardings) * sum(CASE WHEN trip_status = 'completed' THEN 1 ELSE 0 END)
             / count(DISTINCT service_date), 1) AS est_boardings_per_day,
       round(avg(occupancy_pct), 4) AS avg_occupancy,
       round(avg(CAST(peak_hour_indicator_asof AS DOUBLE)), 4) AS peak_rate_asof
FROM v_trip
GROUP BY day_class, hour
