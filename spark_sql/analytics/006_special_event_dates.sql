-- name: special_event_dates
-- kind: output
-- item: 17
-- City-level view: a date with spikes on >= 3 routes is a city-wide event.
SELECT service_date, count(*) AS routes_observed,
       sum(CASE WHEN day_status = 'spike' THEN 1 ELSE 0 END) AS routes_spiking,
       sum(CASE WHEN day_status = 'drop' THEN 1 ELSE 0 END) AS routes_dropping,
       max(demand_ratio) AS max_demand_ratio,
       max(holiday_name) AS holiday_name,
       sum(event_extra_trips) AS event_extra_trips,
       CASE WHEN sum(CASE WHEN day_status = 'spike' THEN 1 ELSE 0 END) >= ${events_city_event_min_routes} THEN 'city_wide_event'
            WHEN sum(CASE WHEN day_status = 'spike' THEN 1 ELSE 0 END) > 0 THEN 'local_event'
            WHEN sum(CASE WHEN day_status = 'drop' THEN 1 ELSE 0 END) >= ${events_city_event_min_routes} THEN 'city_wide_drop'
            ELSE 'normal' END AS date_status,
       concat_ws(',', array_sort(collect_list(CASE WHEN day_status = 'spike' THEN route_id END))) AS spiking_routes
FROM special_event_route_days
GROUP BY service_date
