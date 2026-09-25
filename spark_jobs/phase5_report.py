"""Phase 5 report: read the analytics Parquet back from HDFS and write the markdown reports.

Every number in reports/phase5_analytics_report.md and in the generated sections of
reports/transport_intelligence_summary.md comes from a query in this file, run against
/urbantransit/analytics/<name>; nothing is typed in by hand. NestJS analogy: phase5_analytics.py
is the service that computes, this is the controller that shapes the response for people.

Usage: python spark_jobs/phase5_report.py
"""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spark_jobs.common import PROJECT_ROOT, get_spark, hdfs_uri

REPORTS = PROJECT_ROOT / "reports"


def md_table(rows, cols=None):
    """Render a list of Row/dict objects as a markdown table."""
    rows = [r.asDict() if hasattr(r, "asDict") else r for r in rows]
    if not rows:
        return "_no rows_"
    cols = cols or list(rows[0].keys())
    def fmt(v):
        if isinstance(v, float):
            return f"{v:,.1f}" if abs(v) >= 1000 else f"{v:,.4g}"
        return f"{v:,}" if isinstance(v, int) and not isinstance(v, bool) else str(v)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(fmt(r.get(c)) for c in cols) + " |" for r in rows]
    return "\n".join(out)


def main():
    spark = get_spark("phase5-report")
    metrics = json.loads((REPORTS / "phase5_metrics.json").read_text(encoding="utf-8"))
    for name in metrics:
        spark.read.parquet(hdfs_uri("full", "analytics", name)).createOrReplaceTempView(name)
    q = lambda sql: spark.sql(sql).collect()
    facts = {}  # headline numbers, also saved as JSON for the summary and the checklist

    sections = []
    add = lambda title, body: sections.append(f"## {title}\n\n{body}\n")

    # ---- item 1 EDA
    add("1. EDA - highest / lowest demand routes",
        md_table(q("SELECT route_id, route_type, service_days, avg_daily_boardings, demand_rank FROM eda_route_demand ORDER BY demand_rank LIMIT 5"))
        + "\n\nLowest:\n\n"
        + md_table(q("SELECT route_id, route_type, service_days, avg_daily_boardings, demand_rank FROM eda_route_demand ORDER BY demand_rank DESC LIMIT 5")))
    add("1. EDA - busiest / least-used stops (expanded card taps per open day)",
        md_table(q("SELECT stop_id, stop_name, stop_type, est_boardings_per_day, est_alightings_per_day, est_turnover_per_day FROM eda_stop_usage ORDER BY usage_rank LIMIT 5"))
        + "\n\nLeast used:\n\n"
        + md_table(q("SELECT stop_id, stop_name, stop_type, card_boardings, card_alightings, est_turnover_per_day FROM eda_stop_usage ORDER BY est_turnover_per_day, stop_id LIMIT 5")))
    add("1. EDA - most / least delayed and most punctual routes",
        md_table(q("SELECT route_id, evaluated_trips, avg_delay_min, late_share, punctuality_rate FROM eda_route_delay ORDER BY most_delayed_rank LIMIT 5"))
        + "\n\nLeast delayed:\n\n"
        + md_table(q("SELECT route_id, evaluated_trips, avg_delay_min, late_share, punctuality_rate FROM eda_route_delay ORDER BY avg_delay_min LIMIT 5"))
        + "\n\nMost punctual:\n\n"
        + md_table(q("SELECT route_id, evaluated_trips, punctuality_rate FROM eda_route_delay ORDER BY punctuality_rank, route_id LIMIT 5")))
    add("1. EDA - peak hours (weekday)",
        md_table(q("SELECT hour, trips, avg_boardings_per_trip, est_boardings_per_day, avg_occupancy, peak_rate_asof FROM eda_peak_hours WHERE day_class = 'weekday' ORDER BY est_boardings_per_day DESC LIMIT 6")))
    add("1. EDA - peak days",
        md_table(q("SELECT service_date, day_of_week, day_class, holiday_name, est_system_boardings, routes_with_demand, routes_in_service FROM eda_peak_days ORDER BY busiest_rank LIMIT 5"))
        + "\n\nBy day of week (1 = Sunday):\n\n"
        + md_table(q("SELECT day_of_week, round(avg(est_system_boardings)) AS avg_system_boardings, count(*) AS days FROM eda_peak_days WHERE day_class <> 'holiday' GROUP BY day_of_week ORDER BY day_of_week")))
    add("1. EDA - route travel-time variation (highest CV)",
        md_table(q("SELECT route_id, direction, avg_travel_min, std_travel_min, cv_travel_time, p10_travel_min, p90_travel_min, actual_to_scheduled FROM eda_travel_time_variation ORDER BY variation_rank LIMIT 5")))
    add("1. EDA - stop boarding/alighting patterns (weekday counts of stop-periods)",
        md_table(q("SELECT time_period, pattern, count(*) AS stops FROM eda_stop_patterns WHERE day_class = 'weekday' GROUP BY time_period, pattern ORDER BY time_period, pattern")))

    # ---- item 2 flows
    ef = q("SELECT factor_level, count(*) AS cells, round(avg(expansion_factor), 2) AS avg_factor, round(min(expansion_factor), 2) AS min_factor, round(max(expansion_factor), 2) AS max_factor FROM ticket_expansion_factor GROUP BY factor_level ORDER BY cells DESC")
    facts["expansion"] = [r.asDict() for r in ef]
    add("2. Passenger flow - ticket expansion factor", md_table(ef))
    add("2. Passenger flow - top O-D pairs",
        md_table(q("SELECT origin_stop_id, destination_stop_id, card_journeys, est_journeys_per_day, avg_journey_km, avg_ride_min FROM flow_od_pairs ORDER BY flow_rank LIMIT 8")))
    add("2. Passenger flow - direction balance (weekday cells)",
        md_table(q("SELECT time_period, direction_balance, count(*) AS cells FROM flow_direction_demand WHERE day_class = 'weekday' GROUP BY time_period, direction_balance ORDER BY time_period, direction_balance")))
    add("2. Passenger flow - highest on-board load point per route (top 5)",
        md_table(q("SELECT route_id, direction, stop_id, stop_sequence, est_onboard_after_stop_per_day FROM (SELECT *, row_number() OVER (PARTITION BY route_id, direction ORDER BY est_onboard_after_stop_per_day DESC) rn FROM flow_route_load_profile) WHERE rn = 1 ORDER BY est_onboard_after_stop_per_day DESC LIMIT 5")))

    # ---- item 3 OD
    add("3. O-D matrix", md_table(q("SELECT count(*) AS cells, sum(card_journeys) AS card_journeys, round(sum(est_passengers)) AS est_passengers, count(DISTINCT route_id) AS routes, count(DISTINCT origin_stop_id) AS origins FROM od_matrix"))
        + "\n\nExample filter (route R001, weekday morning peak, top 5 cells):\n\n"
        + md_table(q("SELECT origin_stop_name, destination_stop_name, direction, card_journeys, est_passengers FROM od_matrix WHERE route_id = 'R001' AND day_class = 'weekday' AND time_period = 'morning_peak' ORDER BY est_passengers DESC LIMIT 5")))

    # ---- item 4 peaks
    pp = q("SELECT day_class, time_period, est_boardings_per_day, share_of_day, avg_occupancy, peak_rate_asof, is_peak_period FROM peak_period_summary ORDER BY day_class, time_period")
    add("4. Peak travel periods (leak-free peak_hour_indicator_asof)", md_table(pp))
    add("4. Route-specific peak hours (weekday, count of routes whose peak includes the hour)",
        md_table(q("SELECT hour, count(*) AS routes_peaking FROM peak_route_hours WHERE day_class = 'weekday' AND is_route_peak_hour GROUP BY hour ORDER BY hour")))
    add("4. Stop-specific peak hours (weekday, stops peaking per hour)",
        md_table(q("SELECT hour, count(*) AS stops_peaking FROM peak_stop_hours WHERE day_class = 'weekday' AND is_stop_peak_hour GROUP BY hour ORDER BY stops_peaking DESC LIMIT 8")))

    # ---- item 5-6 overcrowding
    oc = q("SELECT occupancy_category, count(*) AS trips FROM overcrowding_trips GROUP BY occupancy_category ORDER BY min(occupancy_pct)")
    facts["overcrowding_categories"] = {r["occupancy_category"]: r["trips"] for r in oc}
    add("5. Overcrowding categories (measured trips only)", md_table(oc)
        + "\n\n" + md_table(q("SELECT sum(trips) AS trips, sum(measured_trips) AS measured_trips, sum(not_measured_trips) AS not_measured_trips FROM overcrowding_summary"))
        + "\n\nHighest overload share (route, direction):\n\n"
        + md_table(q("SELECT route_id, direction, measured_trips, overload_share, avg_occupancy, max_occupancy FROM overcrowding_summary ORDER BY overload_share DESC LIMIT 5")))
    add("6. Persistent vs one-off overcrowding (route x direction x weekday x period cells)",
        md_table(q("SELECT overload_pattern, count(*) AS cells, count(DISTINCT route_id) AS routes FROM persistent_overcrowding GROUP BY overload_pattern ORDER BY cells DESC"))
        + "\n\nMost persistent cells:\n\n"
        + md_table(q("SELECT route_id, direction, day_of_week, time_period, days_observed, days_overloaded, overload_day_share FROM persistent_overcrowding WHERE overload_pattern = 'persistent' ORDER BY overload_day_share DESC, days_overloaded DESC LIMIT 8")))

    # ---- item 7
    add("7. Underutilized services",
        md_table(q("SELECT utilization_status, count(*) AS cells, count(DISTINCT route_id) AS routes FROM underutilized_services GROUP BY utilization_status ORDER BY cells DESC"))
        + "\n\nLowest-occupancy underutilized cells:\n\n"
        + md_table(q("SELECT route_id, direction, day_class, time_period, trips_per_hour, avg_occupancy, p90_occupancy, boardings_per_km FROM underutilized_services WHERE utilization_status = 'underutilized' ORDER BY avg_occupancy LIMIT 8")))

    # ---- item 8
    rc = q("SELECT route_class, count(*) AS routes, sum(CAST(overcrowded_flag AS INT)) AS with_overcrowded_flag, round(min(composite_score), 1) AS min_composite, round(max(composite_score), 1) AS max_composite FROM route_performance GROUP BY route_class ORDER BY routes DESC")
    facts["route_classes"] = {r["route_class"]: r["routes"] for r in rc}
    facts["route_classes_flagged"] = {r["route_class"]: r["with_overcrowded_flag"] for r in rc}
    facts["overcrowded_flag_routes"] = one_val = q("SELECT count(*) AS n FROM route_performance WHERE overcrowded_flag")[0]["n"]
    scope = q("SELECT overcrowded_scope, overcrowding_location, count(*) AS routes FROM route_performance WHERE overcrowded_flag GROUP BY overcrowded_scope, overcrowding_location ORDER BY routes DESC")
    facts["overcrowded_scope"] = [r.asDict() for r in scope]
    rs = yaml.safe_load((PROJECT_ROOT / "config" / "phase5.yaml").read_text(encoding="utf-8"))["route_scoring"]
    prod, alt = rs["stop_hotspot_share"], rs["stop_hotspot_sensitivity_share"]
    sens = q(f"SELECT count(*) AS flagged_routes, sum(CASE WHEN hotspot_share >= {prod} THEN 1 ELSE 0 END) AS stop_specific_at_production_{int(prod * 100)}pct, "
             f"sum(CASE WHEN hotspot_share >= {alt} THEN 1 ELSE 0 END) AS stop_specific_at_sensitivity_{int(alt * 100)}pct, "
             "max(hotspot_share) AS max_hotspot_share FROM route_performance WHERE overcrowded_flag")
    facts["hotspot_sensitivity"] = sens[0].asDict()
    mixed = q("SELECT route_id, composite_score, composite_rank, demand_score, reliability_rank, med_underload_share, med_overload_share, overcrowded_flag FROM route_performance WHERE route_class = 'Mixed / Needs Review' ORDER BY route_id")
    facts["mixed_routes"] = [r.asDict() for r in mixed]
    add("8. Route performance classes (class from composite score; overcrowded is a separate flag)", md_table(rc)
        + f"\n\nRoutes with overcrowded_flag = true (at least one persistent overload cell): {one_val}.\n\n"
        + "Flagged routes by scope (direction) and location (stop-specific vs route-wide):\n\n" + md_table(scope)
        + "\n\nStop-specific sensitivity (production threshold 60%, check at 40%):\n\n" + md_table(sens)
        + "\n\nMixed / Needs Review routes (criteria missed are in `class_reason`):\n\n" + md_table(mixed)
        + "\n\nTop composite scores:\n\n"
        + md_table(q("SELECT route_id, route_class, composite_score, demand_score, punctuality_score, reliability_score, load_score, underutilization_score, overcrowding_score FROM route_performance WHERE eligible ORDER BY composite_score DESC LIMIT 5"))
        + "\n\nBottom composite scores:\n\n"
        + md_table(q("SELECT route_id, route_class, composite_score, demand_score, punctuality_score, reliability_score, load_score, underutilization_score, overcrowding_score FROM route_performance WHERE eligible ORDER BY composite_score LIMIT 5"))
        + "\n\nTricky cases handled:\n\n"
        + md_table(q("SELECT route_id, route_class, overcrowded_flag, overcrowded_scope, overcrowding_location, hotspot_share, tricky_case_notes FROM route_performance WHERE overcrowded_scope LIKE 'direction%' OR route_class = 'Insufficient Data' OR tricky_case_notes LIKE '%did not set%' ORDER BY route_class, route_id LIMIT 15")))

    # ---- item 9
    add("9. Delay by dimension (time period, day class, distance band)",
        md_table(q("SELECT dimension, dim_value, evaluated_trips, avg_delay_min, late_share, avg_arrival_delay_min FROM delay_by_dimension WHERE dimension IN ('time_period', 'day_class', 'distance_band', 'route_type') ORDER BY dimension, dim_value")))
    add("9. Delay by hour (weekday+weekend, late share)",
        md_table(q("SELECT dim_value AS hour, evaluated_trips, late_share, avg_arrival_delay_min FROM delay_by_dimension WHERE dimension = 'hour' ORDER BY late_share DESC LIMIT 6")))
    bn = q("SELECT stop_id, stop_name, routes_serving, trips_serving, congestion_records, congestion_record_rate, top_reason FROM delay_by_stop WHERE is_bottleneck ORDER BY congestion_record_rate DESC LIMIT 10")
    facts["bottleneck_stops"] = [r.asDict() for r in bn]
    add("9. Bottleneck stops", md_table(bn))
    add("9. Congestion patterns (weekday arrival delay vs midday)",
        md_table(q("SELECT congestion_pattern, count(*) AS routes FROM delay_congestion_patterns GROUP BY congestion_pattern ORDER BY routes DESC"))
        + "\n\nStrongest peak excess:\n\n"
        + md_table(q("SELECT route_id, morning_peak_delay, midday_delay, evening_peak_delay, morning_excess_min, evening_excess_min, congestion_pattern FROM delay_congestion_patterns ORDER BY greatest(morning_excess_min, evening_excess_min) DESC LIMIT 5")))
    add("9. Delay accumulation along routes (largest mean accumulated delay)",
        md_table(q("SELECT route_id, direction, time_period, distance_km, avg_departure_deviation_min, avg_arrival_delay_min, avg_accumulated_delay_min FROM delay_accumulation ORDER BY avg_accumulated_delay_min DESC LIMIT 5"))
        + "\n\nLate records by stop position (all route types):\n\n"
        + md_table(q("SELECT position_decile, sum(late_records) AS late_records, round(sum(late_records * avg_delay_min) / sum(late_records), 2) AS avg_delay_min FROM delay_stop_position_profile GROUP BY position_decile ORDER BY position_decile")))
    add("9. Consistently delayed routes and vehicles",
        md_table(q("SELECT entity_type, count(*) AS entities, sum(CASE WHEN consistently_delayed THEN 1 ELSE 0 END) AS consistently_delayed FROM delay_consistent_entities GROUP BY entity_type"))
        + "\n\n" + md_table(q("SELECT entity_type, entity_id, days, evaluated_trips, avg_daily_late_share, share_days_above_system FROM delay_consistent_entities WHERE consistently_delayed ORDER BY share_days_above_system DESC LIMIT 8")))

    # ---- item 10-14
    add("10. Stop performance (top turnover stops)",
        md_table(q("SELECT stop_id, stop_name, est_turnover_per_day, routes_serving, trips_serving_per_day, turnover_per_trip, late_record_rate, is_bottleneck FROM stop_performance ORDER BY est_turnover_per_day DESC LIMIT 8")))
    add("11. Travel time - largest weekday peak penalty",
        md_table(q("SELECT route_id, direction, peak_actual_min, offpeak_actual_min, peak_scheduled_min, offpeak_scheduled_min, peak_minus_offpeak_min, peak_penalty_pct FROM travel_time_peak_offpeak ORDER BY peak_penalty_pct DESC LIMIT 5"))
        + "\n\nSystem scheduled vs actual by period:\n\n"
        + md_table(q("SELECT time_period, round(sum(scheduled_min * completed_trips) / sum(completed_trips), 2) AS scheduled_min, round(sum(actual_min * completed_trips) / sum(completed_trips), 2) AS actual_min, sum(completed_trips) AS trips FROM travel_time_analysis GROUP BY time_period ORDER BY time_period")))
    add("12. Route reliability (lowest on-time rate)",
        md_table(q("SELECT route_id, on_time_rate, early_arrival_share, late_arrival_share, missed_share, arrival_delay_std, travel_time_cv FROM route_reliability ORDER BY on_time_rate LIMIT 5")))
    sa = q("SELECT day_class, sum(scheduled_trips) AS scheduled, sum(missed_trips) AS missed, round(sum(early_arrivals) / sum(completed_trips), 4) AS early_share, round(sum(on_time_arrivals) / sum(completed_trips), 4) AS on_time_share, round(sum(late_arrivals) / sum(completed_trips), 4) AS late_share, round(sum(irregular_intervals) / sum(intervals_assessed), 4) AS irregular_interval_share FROM schedule_adherence GROUP BY day_class ORDER BY day_class")
    facts["schedule_adherence"] = [r.asDict() for r in sa]
    add("13. Schedule adherence", md_table(sa))
    add("14. Headway and bunching (highest bunched share)",
        md_table(q("SELECT route_id, direction, time_period, headways_assessed, avg_headway_min, avg_scheduled_gap_min, bunched_share, gap_share, overtakings FROM headway_bunching WHERE headways_assessed >= 100 ORDER BY bunched_share DESC LIMIT 8"))
        + "\n\nSystem:\n\n"
        + md_table(q("SELECT sum(headways_assessed) AS assessed, sum(bunched) AS bunched, sum(gaps) AS gaps, sum(overtakings) AS overtakings, round(sum(bunched) / sum(headways_assessed), 4) AS bunched_share, round(sum(gaps) / sum(headways_assessed), 4) AS gap_share FROM headway_bunching")))

    # ---- item 15-16
    add("15. Service frequency vs demand",
        md_table(q("SELECT frequency_match, count(*) AS cells, count(DISTINCT route_id) AS routes FROM service_frequency GROUP BY frequency_match ORDER BY cells DESC"))
        + "\n\n" + md_table(q("SELECT route_id, direction, day_class, time_period, scheduled_trips_per_hour, avg_occupancy, overload_share, peak_rate_asof FROM service_frequency WHERE frequency_match = 'too_little' ORDER BY overload_share DESC LIMIT 8")))
    add("16. Demand-supply gap and capacity suggestions",
        md_table(q("SELECT gap_status, suggestion, count(*) AS cells, count(DISTINCT route_id) AS routes FROM demand_supply_gap GROUP BY gap_status, suggestion ORDER BY cells DESC"))
        + "\n\n" + md_table(q("SELECT route_id, direction, day_class, time_period, utilization, denied_per_trip, avg_capacity, required_capacity, suggested_vehicle_type, suggestion, extra_trips_per_hour FROM demand_supply_gap WHERE gap_status = 'excess_demand' ORDER BY utilization DESC LIMIT 8")))

    # ---- item 17-19
    ev = q("SELECT date_status, count(*) AS dates FROM special_event_dates GROUP BY date_status ORDER BY dates DESC")
    facts["event_dates"] = {r["date_status"]: r["dates"] for r in ev}
    add("17. Special events", md_table(ev)
        + "\n\nCity-wide spike dates:\n\n"
        + md_table(q("SELECT service_date, routes_spiking, max_demand_ratio, holiday_name, event_extra_trips, spiking_routes FROM special_event_dates WHERE date_status IN ('city_wide_event', 'local_event') ORDER BY routes_spiking DESC, service_date LIMIT 10"))
        + "\n\nValidation against generator event trips (not used for detection):\n\n"
        + md_table(q("SELECT day_status, count(*) AS route_days, sum(CASE WHEN event_extra_trips > 0 THEN 1 ELSE 0 END) AS with_event_trips FROM special_event_route_days GROUP BY day_status ORDER BY route_days DESC")))
    an = q("SELECT anomaly_type, entity_type, signals, entities, dates FROM anomaly_summary ORDER BY signals DESC")
    facts["anomalies"] = {r["anomaly_type"]: r["signals"] for r in an}
    add("18. Anomalies", md_table(an))
    sg = q("SELECT segment, card_holders, share_of_card_holders, avg_journeys, avg_active_days_per_week, avg_peak_share, avg_journey_km, share_of_est_journeys, most_common_passenger_type FROM segment_summary ORDER BY card_holders DESC")
    facts["segments"] = [r.asDict() for r in sg]
    add("19. Passenger segmentation (registered smart-card holders only - a ~3-4% sample of riders)", md_table(sg))

    # headline facts for the intelligence summary
    one = lambda sql: q(sql)[0].asDict()
    facts["top_demand_route"] = one("SELECT route_id, avg_daily_boardings FROM eda_route_demand ORDER BY demand_rank LIMIT 1")
    facts["low_demand_route"] = one("SELECT route_id, avg_daily_boardings FROM eda_route_demand ORDER BY demand_rank DESC LIMIT 1")
    facts["busiest_stop"] = one("SELECT stop_id, stop_name, est_turnover_per_day FROM eda_stop_usage ORDER BY usage_rank LIMIT 1")
    facts["most_delayed_route"] = one("SELECT route_id, avg_delay_min, late_share FROM eda_route_delay ORDER BY most_delayed_rank LIMIT 1")
    facts["most_punctual_route"] = one("SELECT route_id, punctuality_rate FROM eda_route_delay ORDER BY punctuality_rank, route_id LIMIT 1")
    facts["top_overcrowded_route"] = one("SELECT route_id, direction, overload_share, measured_trips FROM overcrowding_summary ORDER BY overload_share DESC LIMIT 1")
    facts["persistent_cells"] = one("SELECT count(*) AS cells, count(DISTINCT route_id) AS routes FROM persistent_overcrowding WHERE overload_pattern = 'persistent'")
    facts["best_route"] = one("SELECT route_id, composite_score, route_class, overcrowded_flag FROM route_performance WHERE eligible ORDER BY composite_score DESC LIMIT 1")
    facts["worst_route"] = one("SELECT route_id, composite_score, route_class, overcrowded_flag FROM route_performance WHERE eligible ORDER BY composite_score LIMIT 1")
    facts["overcrowded_class_routes"] = [r.asDict() for r in q("SELECT route_id, composite_score, med_overload_share, demand_score, reliability_rank FROM route_performance WHERE route_class = 'Overcrowded' ORDER BY med_overload_share DESC")]
    facts["high_performing_heavy_overload"] = [r.asDict() for r in q("SELECT route_id, composite_score, composite_rank, med_overload_share, overcrowding_score FROM route_performance WHERE route_class = 'High Performing' AND med_overload_share >= 0.2 ORDER BY med_overload_share DESC")]
    # R097 was the most overcrowded route in the CMD-017 review; its outcome is reported explicitly.
    r097 = q("SELECT route_id, route_class, overcrowded_flag, composite_score, composite_rank, med_overload_share, med_overload_severity, persistent_cell_share, overcrowding_penalty, demand_score, occupancy_score, punctuality_score, delay_frequency_score, travel_time_score, reliability_score, load_score, underutilization_score, overcrowding_score, class_reason FROM route_performance WHERE route_id = 'R097'")
    facts["R097"] = r097[0].asDict() if r097 else None
    add("8. Route R097 (most overcrowded route) after the overcrowding component",
        md_table(r097, ["route_id", "route_class", "overcrowded_flag", "composite_score", "composite_rank", "med_overload_share",
                        "med_overload_severity", "persistent_cell_share", "overcrowding_penalty", "overcrowding_score"])
        + "\n\nComponent scores:\n\n"
        + md_table(r097, ["demand_score", "occupancy_score", "punctuality_score", "delay_frequency_score", "travel_time_score",
                          "reliability_score", "load_score", "underutilization_score", "overcrowding_score"]))
    facts["overcrowding_score_distribution"] = one("SELECT round(min(overcrowding_score), 1) AS min, round(percentile_approx(overcrowding_score, 0.5), 1) AS median, round(max(overcrowding_score), 1) AS max, sum(CASE WHEN overcrowding_score = 0 THEN 1 ELSE 0 END) AS routes_at_zero FROM route_performance WHERE eligible")
    facts["weekday_peak_hour"] = one("SELECT hour, est_boardings_per_day FROM eda_peak_hours WHERE day_class = 'weekday' ORDER BY est_boardings_per_day DESC LIMIT 1")
    facts["congestion_patterns"] = {r["congestion_pattern"]: r["routes"] for r in q("SELECT congestion_pattern, count(*) AS routes FROM delay_congestion_patterns GROUP BY congestion_pattern")}
    facts["top_od_pair"] = one("SELECT origin_stop_id, destination_stop_id, est_journeys_per_day FROM flow_od_pairs ORDER BY flow_rank LIMIT 1")
    facts["bunching"] = one("SELECT round(sum(bunched) / sum(headways_assessed), 4) AS bunched_share, sum(overtakings) AS overtakings FROM headway_bunching")
    facts["supply"] = {f"{r['gap_status']}": r["cells"] for r in q("SELECT gap_status, count(*) AS cells FROM demand_supply_gap GROUP BY gap_status")}
    facts["frequency"] = {r["frequency_match"]: r["cells"] for r in q("SELECT frequency_match, count(*) AS cells FROM service_frequency GROUP BY frequency_match")}

    header = ["# Phase 5 Analytics Report", "",
              "Generated by `spark_jobs/phase5_report.py` from the Parquet outputs in `/urbantransit/analytics/`. "
              "Method per item: `documentation/analytics_methodology.md`.", "",
              "## Outputs", "", md_table([{"output": k, "item": v["item"], "rows": v["rows"], "files": v["files"]} for k, v in sorted(metrics.items(), key=lambda kv: (kv[1]["item"], kv[0]))]), ""]
    (REPORTS / "phase5_analytics_report.md").write_text("\n".join(header + sections), encoding="utf-8")
    (REPORTS / "phase5_facts.json").write_text(json.dumps(facts, indent=2, default=str), encoding="utf-8")
    print(json.dumps(facts, indent=1, default=str))
    spark.stop()


if __name__ == "__main__":
    main()
