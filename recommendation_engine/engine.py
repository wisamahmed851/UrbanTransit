import socket
import pandas as pd
import yaml
import json
from pathlib import Path

# Monkeypatch socket.getaddrinfo to resolve WSL WebHDFS DataNode
original_getaddrinfo = socket.getaddrinfo
def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host == 'desktop-mu0snbr.localdomain':
        host = '127.0.0.1'
    return original_getaddrinfo(host, port, family, type, proto, flags)
socket.getaddrinfo = patched_getaddrinfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "thresholds.yaml"
REPORTS_DIR = PROJECT_ROOT / "reports"
HDFS_BASE = "webhdfs://localhost:9870/urbantransit/analytics"

def load_thresholds():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def load_data(table_name):
    return pd.read_parquet(f"{HDFS_BASE}/{table_name}")

def generate_recommendations():
    config = load_thresholds()
    rec_rules = config.get("recommendations", {}).get("priority_rules", {})
    
    # Load all needed data
    persistent_overcrowding = load_data("persistent_overcrowding")
    demand_supply_gap = load_data("demand_supply_gap")
    schedule_adherence = load_data("schedule_adherence")
    stop_performance = load_data("stop_performance")
    anomalies = load_data("anomalies")
    route_reliability = load_data("route_reliability")
    underutilized_services = load_data("underutilized_services")
    
    recommendations = []
    rec_id_counter = 1
    
    def add_rec(subject_id, category, action, evidence, priority, impact):
        nonlocal rec_id_counter
        recommendations.append({
            "recommendation_id": f"REC-{rec_id_counter:03d}",
            "subject_id": subject_id,
            "category": category,
            "action": action,
            "evidence": evidence,
            "priority": priority,
            "estimated_impact": impact
        })
        rec_id_counter += 1

    # FREQUENCY recommendations
    freq_candidates = pd.merge(
        persistent_overcrowding[persistent_overcrowding['overload_pattern'] == 'persistent'],
        demand_supply_gap,
        on=['route_id', 'direction', 'time_period']
    )
    for _, row in freq_candidates.iterrows():
        if row['utilization'] > 1.25 or row['gap_status'] == 'capacity_shortfall':
            obs_days = int(row['days_observed'])
            if obs_days < 40: continue
            
            overload_share = row['overload_day_share']
            if overload_share >= rec_rules.get("critical_occupancy_threshold", 0.80):
                pri = "Critical"
            elif overload_share >= rec_rules.get("high_occupancy_threshold", 0.40):
                pri = "Medium"
            else:
                continue
            
            add_rec(
                subject_id=row['route_id'],
                category="FREQUENCY",
                action="Increase frequency during identified peak periods.",
                evidence=f"Route {row['route_id']} ({row['time_period']}): avg utilization {row['utilization']:.1%}, overloaded on {int(overload_share*obs_days)} of {obs_days} observed days in the evaluation period. Required capacity: {row['required_capacity']:.0f}.",
                priority=pri,
                impact=f"(Estimate) Adding {row['extra_trips_per_hour'] if pd.notna(row['extra_trips_per_hour']) else 1} trips/hr will reduce occupancy below critical thresholds."
            )

    # CAPACITY recommendations
    cap_candidates = demand_supply_gap[
        demand_supply_gap['suggestion'].astype(str).str.contains('larger_vehicle', case=False, na=False) &
        (demand_supply_gap['denied_per_trip'] >= rec_rules.get('capacity_min_denied_boardings', 5))
    ]
    for _, row in cap_candidates.iterrows():
        pri = "High"
        add_rec(
            subject_id=row['route_id'],
            category="CAPACITY",
            action="Allocate higher-capacity vehicle or add trips.",
            evidence=f"Route {row['route_id']} ({row['time_period']}): p90 load is {row['p90_load']:.1f}, suggested vehicle type: {row['suggested_vehicle_type']}, averaging {row['denied_per_trip']:.1f} denied boardings per trip over {int(row['days'])} days.",
            priority=pri,
            impact=f"(Estimate) Providing {row['suggested_capacity']} capacity per trip will eliminate {row['denied_per_trip']:.1f} denied boardings per trip."
        )

    # SCHEDULE recommendations
    schedule_recs = []
    for _, row in schedule_adherence.iterrows():
        late_share = row['late_share']
        early_share = row['early_share']
        obs_trips = int(row['completed_trips'] + row['missed_trips'])
        
        if late_share > rec_rules.get("critical_delay_trip_pct", 0.35):
            schedule_recs.append({
                'subject_id': row['route_id'], 'category': 'SCHEDULE', 'action': 'Shift departure time or adjust dwell time.',
                'evidence': f"Route {row['route_id']}: {int(late_share*obs_trips)} of {obs_trips} trips ({late_share:.1%}) are late in the evaluation period.",
                'priority': 'Critical', 'impact': '(Estimate) Adjusting schedule will improve on-time performance by up to 25%.'
            })
        elif early_share > 0.40 or late_share > 0.35:
            schedule_recs.append({
                'subject_id': row['route_id'], 'category': 'SCHEDULE', 'action': 'Shift departure time or adjust dwell time.',
                'evidence': f"Route {row['route_id']}: {int(early_share*obs_trips)} early and {int(late_share*obs_trips)} late out of {obs_trips} trips.",
                'priority': 'Low', 'impact': '(Estimate) Minor schedule adjustments will correct adherence deviations.'
            })
            
    sched_df = pd.DataFrame(schedule_recs)
    if not sched_df.empty:
        pri_order = {'Critical': 1, 'High': 2, 'Medium': 3, 'Low': 4}
        sched_df['pri_rank'] = sched_df['priority'].map(pri_order)
        sched_df = sched_df.sort_values('pri_rank').drop_duplicates(subset=['subject_id'], keep='first')
        for _, row in sched_df.iterrows():
            add_rec(row['subject_id'], row['category'], row['action'], row['evidence'], row['priority'], row['impact'])

    # STOP recommendations
    for _, row in stop_performance[stop_performance['is_bottleneck'] == True].iterrows():
        late_rate = row['late_record_rate']
        pri = "Critical" if late_rate > rec_rules.get("critical_bottleneck_delay_pct", 0.25) else "High"
        add_rec(
            subject_id=row['stop_id'],
            category="STOP",
            action="Investigate stop, extend dwell time, or review stop sequence.",
            evidence=f"Stop {row['stop_id']} ({row['stop_name']}): late record rate {late_rate:.1%}, average delay {row['avg_record_delay_min']:.1f} mins over {int(row['late_records'])} delayed records.",
            priority=pri,
            impact="(Estimate) Resolving bottleneck will reduce cascade delays on downstream stops by 15-20%."
        )

    # ANOMALY recommendations
    anomaly_counts = anomalies.groupby(['entity_id', 'anomaly_type']).size().reset_index(name='count')
    recurring_anomalies = anomaly_counts[anomaly_counts['count'] >= rec_rules.get("anomaly_min_count", 25)]
    for _, row in recurring_anomalies.iterrows():
        add_rec(
            subject_id=row['entity_id'],
            category="ANOMALY",
            action="Investigate root cause of recurring anomaly.",
            evidence=f"Entity {row['entity_id']} experienced {row['anomaly_type']} {row['count']} times in the 30-day evaluation window.",
            priority="Medium",
            impact="(Estimate) Root cause mitigation will restore normal operation stability."
        )

    # RELIABILITY recommendations
    for _, row in route_reliability.iterrows():
        if row['on_time_rate'] < rec_rules.get("high_reliability_threshold", 0.60):
            obs_trips = int(row['evaluated_trips'])
            add_rec(
                subject_id=row['route_id'],
                category="RELIABILITY",
                action="Review schedule or add buffer time.",
                evidence=f"Route {row['route_id']}: on-time rate is only {row['on_time_rate']:.1%} across {obs_trips} evaluated trips, travel time CV is {row.get('travel_time_cv', 0):.2f}.",
                priority="High",
                impact="(Estimate) Adding buffer time to schedule will increase on-time rate by >10%."
            )

    # MEDIUM / LOW underutilized services
    for _, row in underutilized_services.iterrows():
        if row.get('p90_occupancy', 1) < rec_rules.get("medium_low_occupancy_threshold", 0.05):
            obs_days = int(row['days'])
            add_rec(
                subject_id=row['route_id'],
                category="FREQUENCY",
                action="Reduce trips or assign lower capacity vehicle.",
                evidence=f"Route {row['route_id']} ({row['time_period']}): p90 occupancy is {row.get('p90_occupancy', 0):.1%} over {obs_days} observed days, utilization status: {row.get('utilization_status', 'Low')}.",
                priority="Medium",
                impact="(Estimate) Removing 1 trip/hr will save operating costs without inducing overcrowding."
            )

    # Save to JSON
    with open(REPORTS_DIR / "recommendations.json", "w") as f:
        json.dump(recommendations, f, indent=2)

    # Generate Markdown Report
    md = ["# Operational Recommendations Report\n"]
    
    # Sort by priority
    priority_order = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}
    recommendations.sort(key=lambda x: (priority_order.get(x['priority'], 5), x['category']))
    
    grouped = {}
    for r in recommendations:
        grouped.setdefault(r['priority'], {}).setdefault(r['category'], []).append(r)
        
    for pri in sorted(grouped.keys(), key=lambda x: priority_order.get(x, 5)):
        md.append(f"## {pri} Priority\n")
        for cat in sorted(grouped[pri].keys()):
            md.append(f"### {cat}\n")
            for r in grouped[pri][cat]:
                md.append(f"**{r['recommendation_id']} ({r['subject_id']})**\n")
                md.append(f"- **Action:** {r['action']}")
                md.append(f"- **Evidence:** {r['evidence']}")
                md.append(f"- **Estimated Impact:** {r['estimated_impact']}\n")
    
    with open(REPORTS_DIR / "recommendations_report.md", "w") as f:
        f.write("\n".join(md))

    # Print summary to stdout
    print("Recommendation Engine Complete")
    summary = pd.DataFrame(recommendations).groupby(['category', 'priority']).size().unstack(fill_value=0)
    print("\nCount of recommendations by category and priority:")
    print(summary.to_string())
    print(f"\nTotal recommendations generated: {len(recommendations)}")
    
    print("\nExample Recommendation:")
    print(json.dumps(recommendations[0], indent=2))

if __name__ == "__main__":
    generate_recommendations()
