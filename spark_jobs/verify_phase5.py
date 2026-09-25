"""Verify the Phase 5 checklist against the real outputs; writes reports/phase5_verification.json.

Checks (each PASS/FAIL with the evidence it is based on):
  1. every analytics output named in spark_sql/analytics/*.sql exists in HDFS and reads back
  2. NULL-aware: unmeasured trips are excluded (not zero/Low) and counts reconcile exactly
  3. peak analyses use only the leak-free *_asof columns
  4. route scoring tricky cases (persistence, direction/stop scope, ineligible routes)
  5. overcrowding categories recomputed independently from config/thresholds.yaml match
  6. ticket analyses apply the expansion factor and carry the sampling note
  7. documentation files exist and cover all 19 items
  8. no secrets or large files among the changed files
  9. Phase 4 delay_severity matches the bands in config/thresholds.yaml
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml
from pyspark.sql import functions as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spark_jobs.common import PROJECT_ROOT, get_spark, hdfs_uri

SQL_DIR = PROJECT_ROOT / "spark_sql" / "analytics"
MAX_FILE_MB = 5


def outputs():
    """Output names declared by the SQL headers (kind output or both)."""
    names = []
    for p in sorted(SQL_DIR.glob("*.sql")):
        h = dict(re.findall(r"^--\s*(name|kind):\s*(\S+)", p.read_text(encoding="utf-8"), flags=re.M))
        if h.get("kind", "output") in ("output", "both"):
            names.append(h["name"])
    return names


def main():
    spark = get_spark("verify-phase5")
    a = lambda n: spark.read.parquet(hdfs_uri("full", "analytics", n))
    feat = spark.read.parquet(hdfs_uri("full", "features", "trip_features"))
    checks = {}

    # 1. outputs exist and read back
    rows = {}
    for n in outputs():
        try:
            rows[n] = a(n).count()
        except Exception as e:  # noqa: BLE001
            rows[n] = f"ERROR {str(e)[:80]}"
    bad = {k: v for k, v in rows.items() if not isinstance(v, int) or v == 0}
    checks["1_outputs_readable"] = {"pass": not bad, "outputs": len(rows), "problems": bad}

    # 2. NULL-aware reconciliation
    measured = feat.filter("occupancy_pct IS NOT NULL").count()
    total = feat.count()
    oc = a("overcrowding_trips")
    ocs = a("overcrowding_summary").agg(F.sum("measured_trips").alias("m"), F.sum("not_measured_trips").alias("n")).first()
    delay_eval = feat.filter("delay_minutes IS NOT NULL").count()
    route_eval = a("eda_route_delay").agg(F.sum("evaluated_trips")).first()[0]
    rp = a("route_performance")
    # Measurement columns that are NULL when not measured must never be zero-filled. Counts of
    # card taps from the (complete) ticket log, e.g. coalesce(b.card_boardings, 0), are observed
    # zeros and are deliberately not matched: the column name must be exactly the measurement.
    zero_fill = []
    for p in sorted(SQL_DIR.glob("*.sql")):
        for m in re.finditer(r"coalesce\(\s*(?:\w+\.)?(boardings|alightings|occupancy_pct|max_load|delay_minutes|arrival_delay_min|travel_time_min|estimated_daily_boardings)\s*,\s*0",
                             p.read_text(encoding="utf-8"), flags=re.I):
            zero_fill.append(f"{p.name}: {m.group(0)}")
    evidence = {"trips": total, "measured_occupancy": measured, "overcrowding_trips_rows": oc.count(),
                "null_category_rows": oc.filter("occupancy_category IS NULL").count(),
                "summary_measured": ocs["m"], "summary_not_measured": ocs["n"],
                "evaluated_delay_trips": delay_eval, "eda_route_delay_evaluated_sum": route_eval,
                "ineligible_routes_with_score": rp.filter("NOT eligible AND composite_score IS NOT NULL").count(),
                "sql_zero_fills_of_measurements": zero_fill}
    checks["2_null_aware"] = {"pass": evidence["overcrowding_trips_rows"] == measured and evidence["null_category_rows"] == 0
                              and ocs["m"] + ocs["n"] == total and ocs["m"] == measured and route_eval == delay_eval
                              and evidence["ineligible_routes_with_score"] == 0 and not zero_fill, **evidence}

    # 3. peaks use only the leak-free indicator
    leaky = [p.name for p in SQL_DIR.glob("*.sql")
             if re.search(r"\b(peak_hour_indicator|hourly_boardings|daily_boardings)\b(?!_asof)",
                          re.sub(r"--[^\n]*", "", p.read_text(encoding="utf-8")))]
    peak_cols = {n: [c for c in a(n).columns if "asof" in c] for n in ("peak_period_summary", "peak_route_hours", "eda_peak_hours")}
    checks["3_peak_leak_free"] = {"pass": not leaky and all(peak_cols.values()), "files_referencing_descriptive_peak": leaky,
                                  "asof_columns": peak_cols}

    # 4. route scoring: class from the composite score, overcrowded as an independent flag, tricky cases
    rs = yaml.safe_load((PROJECT_ROOT / "config" / "phase5.yaml").read_text(encoding="utf-8"))["route_scoring"]
    hi, lo = rs["high_performing_rank"], rs["low_performing_rank"]
    srs_classes = ["High Performing", "High Demand but Unreliable", "Reliable but Underutilized", "Overcrowded", "Low Performing"]
    dist = {r[0]: r[1] for r in rp.groupBy("route_class").count().collect()}
    # composite must equal the documented weighted mean of the nine SRS Step 15 components
    w = rs["weights"]
    recomputed = sum(F.col(f"{k}_score") * v for k, v in w.items()) / sum(w.values())
    composite_mismatch = rp.filter("eligible").filter(F.abs(F.col("composite_score") - recomputed) > 0.15).count()
    ev = {
        "class_distribution": dist,
        "composite_components": list(w),
        "composite_recompute_mismatches": composite_mismatch,
        "eligible_without_overcrowding_score": rp.filter("eligible AND overcrowding_score IS NULL").count(),
        "flag_by_class": {r[0]: r[1] for r in rp.filter("overcrowded_flag").groupBy("route_class").count().collect()},
        "srs_classes_empty": [c for c in srs_classes if dist.get(c, 0) == 0],
        "class_tier_violations": rp.filter(f"eligible AND ((composite_rank >= {hi}) <> (route_class = 'High Performing') "
                                           f"OR (composite_rank <= {lo}) <> (route_class = 'Low Performing'))").count(),
        "flag_not_equal_persistent": rp.filter("overcrowded_flag <> (persistent_cells > 0)").count(),
        "flagged_missing_scope": rp.filter("overcrowded_flag AND (overcrowded_scope IS NULL OR overcrowding_location IS NULL)").count(),
        "routes_with_only_one_off_or_recurring_overloads_not_flagged": rp.filter("persistent_cells = 0 AND (one_off_cells > 0 OR recurring_cells > 0) AND NOT overcrowded_flag").count(),
        "ineligible_not_insufficient": rp.filter("NOT eligible AND route_class <> 'Insufficient Data'").count(),
        "mixed_without_reason": rp.filter("route_class = 'Mixed / Needs Review' AND (class_reason IS NULL OR class_reason = '')").count(),
        "old_average_class_present": dist.get("Average", 0),
        "scope_counts": {f"{r[0]}|{r[1]}": r[2] for r in rp.filter("overcrowded_flag").groupBy("overcrowded_scope", "overcrowding_location").count().collect()},
        "abnormal_days_excluded_from_baselines": a("special_event_route_days").filter("day_status IN ('spike','drop') OR is_holiday").count(),
    }
    checks["4_route_scoring_tricky_cases"] = {"pass": not ev["srs_classes_empty"] and ev["class_tier_violations"] == 0
                                              and composite_mismatch == 0 and len(w) == 9 and "overcrowding" in w
                                              and ev["eligible_without_overcrowding_score"] == 0
                                              and ev["flag_not_equal_persistent"] == 0 and ev["flagged_missing_scope"] == 0
                                              and ev["ineligible_not_insufficient"] == 0 and ev["mixed_without_reason"] == 0
                                              and ev["old_average_class_present"] == 0, **ev}

    # 5. categories vs thresholds.yaml, recomputed independently
    cats = yaml.safe_load((PROJECT_ROOT / "config" / "thresholds.yaml").read_text(encoding="utf-8"))["occupancy_categories"]
    expr = None
    for c in cats:
        cond = F.col("occupancy_pct") <= c["max_ratio"] if c["max_ratio"] is not None else F.lit(True)
        expr = F.when(cond, c["name"]) if expr is None else expr.when(cond, c["name"])
    # recompute from the unrounded feature value to avoid boundary rounding effects
    recomputed = feat.filter("occupancy_pct IS NOT NULL").select("trip_id", expr.alias("expected"))
    mism = oc.select("trip_id", "occupancy_category").join(recomputed, "trip_id").filter("occupancy_category <> expected").count()
    bounds = [r.asDict() for r in oc.groupBy("occupancy_category").agg(F.min("occupancy_pct").alias("min"), F.max("occupancy_pct").alias("max"), F.count("*").alias("trips")).collect()]
    checks["5_categories_match_thresholds"] = {"pass": mism == 0, "mismatches": mism, "config": cats, "observed_bounds": bounds}

    # 6. ticket analyses: expansion applied and sampling noted
    ef = a("ticket_expansion_factor")
    od = a("od_matrix").agg(F.sum("card_journeys").alias("card"), F.sum("est_passengers").alias("est"),
                            F.sum(F.col("est_passengers").isNull().cast("int")).alias("null_est")).first()
    tickets = spark.read.parquet(hdfs_uri("full", "clean", "tickets"))
    dq16 = tickets.filter(F.array_contains("dq_flags", "DQ16")).count()
    fmin, fmax = ef.agg(F.min("expansion_factor"), F.max("expansion_factor")).first()
    noted = {p.name: "sample" in p.read_text(encoding="utf-8").lower()
             for p in [SQL_DIR / "003_v_ticket.sql", SQL_DIR / "030_od_matrix.sql", SQL_DIR / "190_passenger_segments.sql",
                       PROJECT_ROOT / "documentation" / "analytics_methodology.md"] if p.exists()}
    ev6 = {"factor_null_or_nonpositive": ef.filter("expansion_factor IS NULL OR expansion_factor <= 0").count(),
           "factor_min": fmin, "factor_max": fmax, "od_card_journeys": od["card"], "tickets_minus_dq16": tickets.count() - dq16,
           "od_null_est": od["null_est"], "od_implied_factor": round(od["est"] / od["card"], 3), "sampling_note_present": noted}
    checks["6_ticket_expansion_and_sampling"] = {"pass": ev6["factor_null_or_nonpositive"] == 0 and od["card"] == ev6["tickets_minus_dq16"]
                                                 and od["null_est"] == 0 and fmin <= ev6["od_implied_factor"] <= fmax
                                                 and len(noted) == 4 and all(noted.values()), **ev6}

    # 7. docs
    meth = PROJECT_ROOT / "documentation" / "analytics_methodology.md"
    summ = PROJECT_ROOT / "reports" / "transport_intelligence_summary.md"
    missing_items = [i for i in range(1, 20) if not meth.exists() or not re.search(rf"^## {i}\. ", meth.read_text(encoding="utf-8"), flags=re.M)]
    checks["7_docs_written"] = {"pass": meth.exists() and summ.exists() and not missing_items,
                                "methodology": meth.exists(), "summary": summ.exists(), "items_missing_in_methodology": missing_items}

    # 8. secrets / large files among changed + untracked (not ignored) files
    st = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=PROJECT_ROOT, capture_output=True, text=True).stdout
    changed = [l[3:].strip().strip('"') for l in st.splitlines() if l[3:].strip()]
    big, secret = [], []
    pat = re.compile(r"(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9/+_\-]{8,}", re.I)
    for f in changed:
        p = PROJECT_ROOT / f
        if not p.is_file():
            continue
        if p.stat().st_size > MAX_FILE_MB * 1024 * 1024:
            big.append(f"{f} ({p.stat().st_size / 1e6:.1f} MB)")
        if p.suffix in (".py", ".sql", ".md", ".yaml", ".yml", ".json", ".sh", ".env", ".txt") and pat.search(p.read_text(encoding="utf-8", errors="ignore")):
            secret.append(f)
    checks["8_no_secrets_or_large_files"] = {"pass": not big and not secret, "changed_files": len(changed), "large": big, "secret_like": secret}

    # 9. delay_severity stored by Phase 4 matches the bands now in thresholds.yaml (no silent drift)
    from spark_jobs.phase4_features import load_cfg, severity, severity_bands
    sev = feat.select("delay_severity", severity(F.col("delay_minutes"), load_cfg()).alias("expected"))
    sev_mism = sev.filter(~F.col("delay_severity").eqNullSafe(F.col("expected"))).count()
    checks["9_delay_severity_matches_thresholds"] = {
        "pass": sev_mism == 0, "mismatches": sev_mism, "bands": severity_bands(),
        "stored_classes": {str(r[0]): r[1] for r in feat.groupBy("delay_severity").count().collect()}}

    out = {"result": "PASS" if all(c["pass"] for c in checks.values()) else "FAIL", "checks": checks}
    (PROJECT_ROOT / "reports" / "phase5_verification.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v["pass"] for k, v in checks.items()} | {"result": out["result"]}, indent=1))
    spark.stop()
    if out["result"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
