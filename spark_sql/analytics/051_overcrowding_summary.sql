-- name: overcrowding_summary
-- kind: output
-- item: 5
-- Category counts per route and direction. not_measured_trips is reported separately so the
-- category shares are computed over measured trips only.
SELECT route_id, direction,
       count(*) AS trips,
       count(occupancy_category) AS measured_trips,
       count(*) - count(occupancy_category) AS not_measured_trips,
       ${category_count_columns},
       round(try_divide(sum(CASE WHEN occupancy_category IN (${overload_list}) THEN 1 ELSE 0 END),
                        count(occupancy_category)), 4) AS overload_share,
       round(avg(occupancy_pct), 4) AS avg_occupancy,
       round(max(occupancy_pct), 4) AS max_occupancy
FROM v_trip
GROUP BY route_id, direction
