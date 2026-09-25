-- name: route_performance
-- kind: output
-- item: 8
-- Composite route score and class. Tricky cases (documented in analytics_methodology.md):
--  * one abnormal day      : metrics are MEDIANS of daily values over normal days only
--                            (event spikes/drops and holidays excluded), and "Overcrowded"
--                            needs a persistent cell - one-off overloads never flag a route.
--  * one direction only    : overload judged per direction; overcrowded_scope says which.
--  * specific stops only   : if >= 60% of a route's overloaded trips peak at one stop,
--                            overcrowding_location = 'stop_specific' with that stop.
--  * new / sparse routes   : < 28 normal service days or < 50% counted trips -> 'Insufficient Data'
--                            (not scored, not ranked against mature routes).
-- Scores are 0-100 percentile ranks among eligible routes (occupancy and utilisation are
-- absolute: occupancy peaks at the 0.70 target, utilisation = 1 - under - over share).
WITH t AS (
  SELECT v.* FROM v_trip v
  JOIN v_normal_days n ON v.route_id = n.route_id AND v.service_date = n.service_date
), day AS (
  SELECT route_id, service_date,
         avg(occupancy_pct) AS occ,
         percentile_approx(occupancy_pct, 0.9) AS p90_occ,
         avg(CAST(trip_punctuality AS DOUBLE)) AS punct,
         avg(CASE WHEN delay_minutes >= ${on_time_late_min} THEN 1.0 WHEN delay_minutes IS NOT NULL THEN 0.0 END) AS late_share,
         avg(try_divide(travel_time_min, scheduled_runtime_min)) AS tt_ratio,
         stddev(arrival_delay_min) AS arr_std,
         avg(CASE WHEN occupancy_category IN (${underload_list}) THEN 1.0 WHEN occupancy_category IS NOT NULL THEN 0.0 END) AS under_share,
         avg(CASE WHEN occupancy_category IN (${overload_list}) THEN 1.0 WHEN occupancy_category IS NOT NULL THEN 0.0 END) AS over_share,
         count(occupancy_pct) AS measured,
         sum(CASE WHEN trip_status = 'completed' THEN 1 ELSE 0 END) AS operated
  FROM t GROUP BY route_id, service_date
), agg AS (
  SELECT route_id, count(*) AS normal_service_days,
         percentile_approx(occ, 0.5) AS med_occupancy,
         percentile_approx(p90_occ, 0.5) AS med_p90_occupancy,
         percentile_approx(punct, 0.5) AS med_punctuality,
         percentile_approx(late_share, 0.5) AS med_late_share,
         percentile_approx(tt_ratio, 0.5) AS med_travel_time_ratio,
         percentile_approx(arr_std, 0.5) AS med_arrival_delay_std,
         percentile_approx(under_share, 0.5) AS med_underload_share,
         percentile_approx(over_share, 0.5) AS med_overload_share,
         try_divide(sum(measured), sum(operated)) AS demand_coverage
  FROM day GROUP BY route_id
), dem AS (
  SELECT r.route_id, percentile_approx(r.estimated_daily_boardings, 0.5) AS med_daily_boardings
  FROM route_daily_demand r
  JOIN v_normal_days n ON r.route_id = n.route_id AND r.service_date = n.service_date
  GROUP BY r.route_id
), pers AS (
  SELECT route_id,
         sum(CASE WHEN overload_pattern = 'persistent' THEN 1 ELSE 0 END) AS persistent_cells,
         sum(CASE WHEN overload_pattern = 'recurring' THEN 1 ELSE 0 END) AS recurring_cells,
         sum(CASE WHEN overload_pattern = 'one_off' THEN 1 ELSE 0 END) AS one_off_cells,
         sum(event_day_overloads) AS event_day_overloads,
         concat_ws(',', array_sort(collect_set(CASE WHEN overload_pattern = 'persistent' THEN CAST(direction AS STRING) END))) AS persistent_directions
  FROM persistent_overcrowding GROUP BY route_id
), hot AS (
  SELECT route_id, max_by(max_load_stop_id, n) AS hotspot_stop_id, try_divide(max(n), sum(n)) AS hotspot_share
  FROM (SELECT route_id, max_load_stop_id, count(*) AS n FROM t
        WHERE occupancy_category IN (${overload_list}) AND max_load_stop_id IS NOT NULL
        GROUP BY route_id, max_load_stop_id) x
  GROUP BY route_id
), excluded AS (
  SELECT route_id, sum(CASE WHEN day_status IN ('spike', 'drop') OR is_holiday THEN 1 ELSE 0 END) AS excluded_abnormal_days
  FROM special_event_route_days GROUP BY route_id
), base AS (
  SELECT r.route_id, r.route_code, r.route_type, r.launch_date,
         a.normal_service_days, a.demand_coverage, d.med_daily_boardings,
         a.med_occupancy, a.med_p90_occupancy, a.med_punctuality, a.med_late_share, a.med_travel_time_ratio,
         a.med_arrival_delay_std, a.med_underload_share, a.med_overload_share,
         coalesce(p.persistent_cells, 0) AS persistent_cells, coalesce(p.recurring_cells, 0) AS recurring_cells,
         coalesce(p.one_off_cells, 0) AS one_off_cells, coalesce(p.event_day_overloads, 0) AS event_day_overloads,
         nullif(p.persistent_directions, '') AS persistent_directions,
         h.hotspot_stop_id, h.hotspot_share, coalesce(e.excluded_abnormal_days, 0) AS excluded_abnormal_days,
         coalesce(a.normal_service_days >= ${route_scoring_min_service_days}
                  AND a.demand_coverage >= ${route_scoring_min_demand_coverage}
                  AND d.med_daily_boardings IS NOT NULL AND a.med_occupancy IS NOT NULL, false) AS eligible
  FROM routes r
  LEFT JOIN agg a ON r.route_id = a.route_id
  LEFT JOIN dem d ON r.route_id = d.route_id
  LEFT JOIN pers p ON r.route_id = p.route_id
  LEFT JOIN hot h ON r.route_id = h.route_id
  LEFT JOIN excluded e ON r.route_id = e.route_id
), s AS (
  SELECT base.*,
         100 * percent_rank() OVER (PARTITION BY eligible ORDER BY med_daily_boardings) AS demand_score,
         100 * greatest(0, 1 - abs(med_occupancy - ${route_scoring_target_occupancy}) / ${route_scoring_target_occupancy}) AS occupancy_score,
         100 * percent_rank() OVER (PARTITION BY eligible ORDER BY med_punctuality) AS punctuality_score,
         100 * percent_rank() OVER (PARTITION BY eligible ORDER BY med_late_share DESC) AS delay_frequency_score,
         100 * percent_rank() OVER (PARTITION BY eligible ORDER BY med_travel_time_ratio DESC) AS travel_time_score,
         100 * percent_rank() OVER (PARTITION BY eligible ORDER BY med_arrival_delay_std DESC) AS reliability_score,
         100 * percent_rank() OVER (PARTITION BY eligible ORDER BY med_p90_occupancy DESC) AS load_score,
         100 * greatest(0, 1 - med_underload_share - med_overload_share) AS utilization_score
  FROM base
), c AS (
  SELECT s.*,
         (${route_scoring_weights_demand} * demand_score + ${route_scoring_weights_occupancy} * occupancy_score
          + ${route_scoring_weights_punctuality} * punctuality_score + ${route_scoring_weights_delay_frequency} * delay_frequency_score
          + ${route_scoring_weights_travel_time} * travel_time_score + ${route_scoring_weights_reliability} * reliability_score
          + ${route_scoring_weights_load} * load_score + ${route_scoring_weights_utilization} * utilization_score)
         / (${route_scoring_weights_demand} + ${route_scoring_weights_occupancy} + ${route_scoring_weights_punctuality}
            + ${route_scoring_weights_delay_frequency} + ${route_scoring_weights_travel_time} + ${route_scoring_weights_reliability}
            + ${route_scoring_weights_load} + ${route_scoring_weights_utilization}) AS composite_score,
         (punctuality_score + delay_frequency_score + reliability_score) / 3 AS reliability_index
  FROM s
), r AS (
  SELECT c.*,
         percent_rank() OVER (PARTITION BY eligible ORDER BY composite_score) AS composite_pr,
         percent_rank() OVER (PARTITION BY eligible ORDER BY reliability_index) AS reliability_pr
  FROM c
)
SELECT route_id, route_code, route_type, launch_date, eligible, normal_service_days, excluded_abnormal_days,
       round(demand_coverage, 4) AS demand_coverage, round(med_daily_boardings, 1) AS med_daily_boardings,
       round(med_occupancy, 4) AS med_occupancy, round(med_p90_occupancy, 4) AS med_p90_occupancy,
       round(med_punctuality, 4) AS med_punctuality, round(med_late_share, 4) AS med_late_share,
       round(med_travel_time_ratio, 4) AS med_travel_time_ratio, round(med_arrival_delay_std, 3) AS med_arrival_delay_std,
       round(med_underload_share, 4) AS med_underload_share, round(med_overload_share, 4) AS med_overload_share,
       persistent_cells, recurring_cells, one_off_cells, event_day_overloads,
       CASE WHEN NOT eligible THEN NULL ELSE round(demand_score, 1) END AS demand_score,
       CASE WHEN NOT eligible THEN NULL ELSE round(occupancy_score, 1) END AS occupancy_score,
       CASE WHEN NOT eligible THEN NULL ELSE round(punctuality_score, 1) END AS punctuality_score,
       CASE WHEN NOT eligible THEN NULL ELSE round(delay_frequency_score, 1) END AS delay_frequency_score,
       CASE WHEN NOT eligible THEN NULL ELSE round(travel_time_score, 1) END AS travel_time_score,
       CASE WHEN NOT eligible THEN NULL ELSE round(reliability_score, 1) END AS reliability_score,
       CASE WHEN NOT eligible THEN NULL ELSE round(load_score, 1) END AS load_score,
       CASE WHEN NOT eligible THEN NULL ELSE round(utilization_score, 1) END AS utilization_score,
       CASE WHEN NOT eligible THEN NULL ELSE round(composite_score, 1) END AS composite_score,
       CASE WHEN NOT eligible THEN 'Insufficient Data'
            WHEN persistent_cells > 0 THEN 'Overcrowded'
            WHEN demand_score >= 100 * ${route_scoring_high_percentile} AND reliability_pr <= ${route_scoring_low_percentile}
                 THEN 'High Demand but Unreliable'
            WHEN reliability_pr >= ${route_scoring_high_percentile}
                 AND (demand_score <= 100 * ${route_scoring_low_percentile} OR med_underload_share >= 0.5)
                 THEN 'Reliable but Underutilized'
            WHEN composite_pr >= ${route_scoring_high_percentile} THEN 'High Performing'
            WHEN composite_pr <= ${route_scoring_low_percentile} THEN 'Low Performing'
            ELSE 'Average' END AS route_class,
       CASE WHEN persistent_cells = 0 THEN NULL
            WHEN persistent_directions LIKE '%,%' THEN 'both_directions'
            ELSE concat('direction_', persistent_directions, '_only') END AS overcrowded_scope,
       CASE WHEN persistent_cells = 0 THEN NULL
            WHEN hotspot_share >= ${route_scoring_stop_hotspot_share} THEN 'stop_specific'
            ELSE 'route_wide' END AS overcrowding_location,
       hotspot_stop_id, round(hotspot_share, 4) AS hotspot_share,
       concat_ws('; ',
         CASE WHEN persistent_cells = 0 AND (one_off_cells > 0 OR recurring_cells > 0)
              THEN concat(one_off_cells + recurring_cells, ' non-persistent overload cells did not flag the route') END,
         CASE WHEN excluded_abnormal_days > 0 THEN concat(excluded_abnormal_days, ' event/holiday days excluded from baseline') END,
         CASE WHEN NOT eligible AND normal_service_days < ${route_scoring_min_service_days} THEN 'too few service days (new route)' END,
         CASE WHEN NOT eligible AND demand_coverage < ${route_scoring_min_demand_coverage} THEN 'low passenger-count coverage' END
       ) AS tricky_case_notes
FROM r
