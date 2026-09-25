"""Verify Phase 4 split integrity, NULL semantics and strict-prior (leak-free) feature values.

Leakage test: the feature builders from phase4_features.py are re-run on data truncated at the
first test date D (everything after D removed) and with D's own demand multiplied by 10. The
as-of features for date D must be identical to the stored values in both cases.
"""
import json
import sys
from pathlib import Path

from pyspark.sql import functions as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spark_jobs.common import PROJECT_ROOT, get_spark, hdfs_uri
from spark_jobs.phase4_features import add_demand_growth, add_historical, add_peak_asof, load_cfg

TOL = 1e-9


def mismatches(stored, recomputed, keys, cols):
    """Rows where any column differs (NULL-safe, with a float tolerance)."""
    j = stored.select(*keys, *cols).alias("s").join(recomputed.select(*keys, *cols).alias("r"), keys)
    cond = F.lit(False)
    for c in cols:
        s, r = F.col(f"s.{c}"), F.col(f"r.{c}")
        cond = cond | ~(s.eqNullSafe(r) | (F.abs(s.cast("double") - r.cast("double")) <= TOL))
    return j.filter(cond).count()


def main():
    cfg = load_cfg()
    spark = get_spark("verify-phase4")
    feat = spark.read.parquet(hdfs_uri("full", "features", "trip_features")).cache()
    route_day = spark.read.parquet(hdfs_uri("full", "features", "route_daily_demand"))
    out = {}

    # 1. splits: one split per date, chronological order, sizes from config
    out["split_dates_with_multiple_assignments"] = feat.groupBy("service_date").agg(F.countDistinct("split").alias("n")).filter("n != 1").count()
    rng = {r["split"]: r for r in feat.groupBy("split").agg(F.min("service_date").alias("lo"), F.max("service_date").alias("hi"), F.countDistinct("service_date").alias("dates")).collect()}
    out["split_chronological"] = rng["train"]["hi"] < rng["validation"]["lo"] and rng["validation"]["hi"] < rng["test"]["lo"]
    n = sum(r["dates"] for r in rng.values())
    expected = {"train": round(n * cfg["splits"]["train_fraction"]), "validation": round(n * cfg["splits"]["validation_fraction"])}
    out["split_dates"] = {k: rng[k]["dates"] for k in rng}
    out["split_sizes_match_config"] = all(rng[k]["dates"] == v for k, v in expected.items())

    # 2. NULL semantics: unmeasured trips are NULL, never 0
    pc_trips = spark.read.parquet(hdfs_uri("full", "clean", "passenger_counts")).select("trip_id").distinct()
    out["boardings_null"] = feat.filter("boardings is null").count()
    out["trips_without_clean_passenger_count"] = feat.join(pc_trips, "trip_id", "left_anti").count()
    out["delay_minutes_null"] = feat.filter("delay_minutes is null").count()
    out["delay_not_evaluated"] = feat.filter("delay_source = 'not_evaluated'").count()
    out["null_semantics_ok"] = (out["boardings_null"] == out["trips_without_clean_passenger_count"]
                                and out["delay_minutes_null"] == out["delay_not_evaluated"]
                                and feat.filter("boardings is null and (occupancy_pct is not null or crowding_flag is not null)").count() == 0)

    # 3. historical demand/delay: recompute on a deterministic route sample (unchanged contract)
    routes = [r[0] for r in feat.select("route_id").distinct().orderBy("route_id").limit(5).collect()]
    sample = feat.filter(F.col("route_id").isin(routes))
    hist_cols = ["historical_demand_average", "historical_delay_average"]
    out["sample_routes"] = routes
    out["historical_mismatches"] = mismatches(sample, add_historical(sample.drop(*hist_cols)), ["trip_id"], hist_cols)

    # 4. leakage test at cutoff D = first test date
    d = rng["test"]["lo"]
    out["leakage_cutoff_date"] = str(d)
    boost = lambda df, c: df.withColumn(c, F.when(F.col("service_date") == F.lit(d), F.col(c) * 10).otherwise(F.col(c)))
    past = feat.filter(F.col("service_date") <= F.lit(d))
    peak_cols = ["peak_hour_share_asof", "peak_hour_indicator_asof"]
    on_d = lambda df: df.filter(F.col("service_date") == F.lit(d))
    out["peak_asof_mismatch_truncated"] = mismatches(on_d(feat), on_d(add_peak_asof(past.drop(*peak_cols), cfg)), ["trip_id"], peak_cols)
    out["peak_asof_mismatch_same_day_x10"] = mismatches(on_d(feat), on_d(add_peak_asof(boost(past, "boardings").drop(*peak_cols), cfg)), ["trip_id"], peak_cols)
    g_cols = ["demand_wow_growth", "demand_mom_growth"]
    rd_past = route_day.filter(F.col("service_date") <= F.lit(d))
    out["growth_mismatch_truncated"] = mismatches(on_d(route_day), on_d(add_demand_growth(rd_past.drop(*g_cols), cfg)), ["route_id", "service_date"], g_cols)
    out["growth_mismatch_same_day_x10"] = mismatches(on_d(route_day), on_d(add_demand_growth(boost(rd_past, "estimated_daily_boardings").drop(*g_cols), cfg)), ["route_id", "service_date"], g_cols)
    out["growth_non_null_on_cutoff"] = on_d(route_day).filter("demand_wow_growth is not null").count()

    ok = (out["split_dates_with_multiple_assignments"] == 0 and out["split_chronological"] and out["split_sizes_match_config"]
          and out["null_semantics_ok"] and out["historical_mismatches"] == 0
          and all(out[k] == 0 for k in ("peak_asof_mismatch_truncated", "peak_asof_mismatch_same_day_x10",
                                          "growth_mismatch_truncated", "growth_mismatch_same_day_x10"))
          and out["growth_non_null_on_cutoff"] > 0)
    out["result"] = "PASS" if ok else "FAIL"
    (PROJECT_ROOT / "reports" / "phase4_verification.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps(out, default=str))
    spark.stop()
    if out["result"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
