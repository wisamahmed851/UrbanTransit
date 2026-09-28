"""Re-score the saved Phase 7 (Python) models on this machine. Inference only: nothing is trained.

    bash python_pipeline/stage_clean_parquet.sh     # once: HDFS clean tables -> python_pipeline/local_clean
    python database/evaluate_saved_models.py        # inside WSL, venv active

Why: the model binaries in `models/python/` were trained on another machine and shared as a zip.
This script checks that those files reproduce the metrics recorded next to them
(`models/python/metrics/*.json`) on the same chronological validation and test splits, and
compares each result with the SRS targets (NFR 4: >= 85% accuracy or macro F1 >= 0.80 for
classifiers; forecasts must beat a documented baseline).

The features come from `python_pipeline/phase7_python_models.py` itself (`base_trip`,
`demand_frame`, `period`, `cls_scores`, `reg_scores`), imported rather than copied, so the
inputs are exactly the ones the models were trained on. The route-profile block in
`route_profiles` repeats the first lines of `run_clusters`, because that function also
trains and writes files, and must not be called here.

Output: `reports/saved_model_evaluation.json` and a table on stdout.
"""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.cluster import AgglomerativeClustering
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python_pipeline"))

import phase7_python_models as p7  # noqa: E402

MODELS = ROOT / "models" / "python"
SERVING = yaml.safe_load((ROOT / "config" / "serving.yaml").read_text(encoding="utf-8"))
REPORT_PATH = ROOT / "reports" / "saved_model_evaluation.json"
TOLERANCE = 0.005   # scores recomputed here may differ in the last digits across library builds

# SRS 1.7 NFR 4.
TARGET_ACCURACY, TARGET_MACRO_F1 = 0.85, 0.80


def recorded(task: str, algorithm: str) -> dict:
    return json.loads((MODELS / "metrics" / f"{task}_{algorithm}.json").read_text(encoding="utf-8"))


def compare(expected: dict, actual: dict, keys: tuple[str, ...]) -> dict:
    """Recorded vs recomputed value for each metric, and whether they agree within TOLERANCE."""
    out = {}
    for k in keys:
        e, a = expected.get(k), actual.get(k)
        out[k] = {"recorded": e, "recomputed": a,
                  "match": e is not None and a is not None and abs(e - a) <= TOLERANCE * max(1.0, abs(e))}
    return out


def served_algorithm(task: str) -> str:
    return SERVING["served"][task]["algorithm"]


def generalisation(train: float, test: float, higher_is_better: bool = True) -> dict:
    """Train (the 70% the model learned from) vs test (unseen). A small gap means the
    score on unseen data tracks the training score, i.e. the model is not overfitted."""
    gap = train - test if higher_is_better else test - train
    return {"train": train, "test": test, "gap": round(gap, 6),
            "relative_gap_pct": round(gap / abs(train) * 100, 2) if train else None}


def evaluate_classifier(trips: pd.DataFrame, task: str, algorithm: str = "xgboost") -> dict:
    """Score `<task>/<algorithm>_v1.pkl` exactly the way run_classification scored it.

    `train` is scored too (no recorded value to match: Phase 7 does not save it), so the
    train-vs-test gap shows whether the held-out score tracks the training score."""
    rec = recorded(task, algorithm)
    numeric, categorical = rec["features"]["numeric"], rec["features"]["categorical"]
    model = joblib.load(MODELS / task / f"{algorithm}_v1.pkl")
    prep = joblib.load(MODELS / task / f"{algorithm}_preprocessor_v1.pkl")
    labels = rec["test"]["confusion_matrix"]["labels"]      # sorted class names, as in training

    frame = trips.dropna(subset=[task]).copy()
    frame.loc[:, numeric] = frame[numeric].replace([np.inf, -np.inf], np.nan)
    result = {"task": task, "algorithm": algorithm, "model_file": f"models/python/{task}/{algorithm}_v1.pkl",
              "features": numeric + categorical, "threshold": rec.get("threshold"), "splits": {}}
    for split in ("train", "validation", "test"):
        part = p7.period(frame, split)
        proba = model.predict_proba(prep.transform(part[numeric + categorical]))
        if rec.get("threshold") is not None:           # binary crowding flag: tuned threshold on class "1.0"
            pred = np.where(proba[:, labels.index("1.0")] >= rec["threshold"], "1.0", "0.0")
        else:
            pred = np.array(labels)[proba.argmax(1)]
        scores = p7.cls_scores(part[task].astype(str), pred)
        result["splits"][split] = {"rows": len(part), **scores}
        # Training can use a deterministic cap/stratified sample; validation and test
        # are always the complete chronological splits and are the reproducibility gate.
        if split != "train" and split in rec:
            result["splits"][split]["vs_recorded"] = compare(rec[split], scores, ("accuracy", "macro_f1"))
    s = result["splits"]
    result["train_vs_test"] = {m: generalisation(s["train"][m], s["test"][m]) for m in ("accuracy", "macro_f1")}
    result["srs_target"] = {"rule": f"accuracy >= {TARGET_ACCURACY} or macro F1 >= {TARGET_MACRO_F1} (SRS NFR 4)",
                            "accuracy_met": s["test"]["accuracy"] >= TARGET_ACCURACY,
                            "macro_f1_met": s["test"]["macro_f1"] >= TARGET_MACRO_F1}
    return result


def evaluate_demand() -> dict:
    """Score the three saved regressors and the 28-day baseline on the demand frame."""
    d = p7.demand_frame()
    feats = ["lag_1", "lag_7", "lag_28", "rolling_7_mean", "rolling_28_mean"]
    splits = {s: p7.period(d, s).dropna(subset=feats) for s in ("train", "validation", "test")}
    result = {"task": "daily_boardings", "features": feats, "algorithms": {}}
    for name in ("baseline_28day", "ridge", "random_forest", "xgboost"):
        rec, row = recorded("daily_boardings", name), {}
        model = None if name == "baseline_28day" else joblib.load(MODELS / "daily_boardings" / f"{name}_v1.pkl")
        for split, part in splits.items():
            pred = part.rolling_28_mean if model is None else model.predict(part[feats])
            scores = p7.reg_scores(part.boardings, pred)
            row[split] = {"rows": len(part), **scores}
            if split in rec:
                row[split]["vs_recorded"] = compare(rec[split], scores, ("mae", "rmse", "r2"))
        row["train_vs_test"] = {"r2": generalisation(row["train"]["r2"], row["test"]["r2"]),
                                "mae": generalisation(row["train"]["mae"], row["test"]["mae"], higher_is_better=False)}
        result["algorithms"][name] = row
    base_mae = result["algorithms"]["baseline_28day"]["test"]["mae"]
    # run_demand serves the lowest validation MAE among the trained models.
    best = min((v["validation"]["mae"], k) for k, v in result["algorithms"].items() if k != "baseline_28day")[1]
    best_mae = result["algorithms"][best]["test"]["mae"]
    result["selected"] = best
    result["srs_target"] = {"rule": "selected model beats the documented 28-day baseline (SRS step 24)",
                            "baseline_test_mae": base_mae, "selected_test_mae": best_mae,
                            "improvement_pct": round((base_mae - best_mae) / base_mae * 100, 2), "met": best_mae < base_mae}
    return result


def evaluate_occupancy(trips: pd.DataFrame) -> dict:
    """Re-score the numeric occupancy model without retraining it."""
    task = "occupancy_forecast"
    algorithm = served_algorithm(task)
    rec = recorded(task, algorithm)
    numeric, categorical = rec["features"]["numeric"], rec["features"]["categorical"]
    model = joblib.load(MODELS / task / f"{algorithm}_v1.pkl")
    prep = joblib.load(MODELS / task / f"{algorithm}_preprocessor_v1.pkl")
    frame = trips.dropna(subset=["occupancy_pct", "prior_route_occupancy_mean",
                                 "prior_route_hour_occupancy_mean"]).copy()
    frame.loc[:, numeric] = frame[numeric].replace([np.inf, -np.inf], np.nan)
    result = {"task": task, "algorithm": algorithm, "target": rec["target"], "splits": {}}
    for split in ("train", "validation", "test"):
        part = p7.period(frame, split)
        scores = p7.occupancy_scores(part.occupancy_pct, model.predict(prep.transform(part[numeric + categorical])))
        result["splits"][split] = {"rows": len(part), **scores}
        if split != "train" and split in rec:
            result["splits"][split]["vs_recorded"] = compare(rec[split], scores, ("mae", "rmse", "r2"))
    s = result["splits"]
    result["train_vs_test"] = {"r2": generalisation(s["train"]["r2"], s["test"]["r2"]),
                               "mae": generalisation(s["train"]["mae"], s["test"]["mae"], higher_is_better=False)}
    # SRS step 24 baseline: the prior route/direction/hour mean occupancy (strictly earlier
    # trips; falls back to the route/direction mean where the hour cell has no history).
    test = p7.period(frame, "test")
    naive = test.prior_route_hour_occupancy_mean.fillna(test.prior_route_occupancy_mean)
    base = p7.occupancy_scores(test.occupancy_pct, naive)
    result["srs_target"] = {"rule": "model beats the prior route-hour mean occupancy baseline on test MAE (SRS step 24)",
                            "baseline_test_mae": base["mae"], "selected_test_mae": s["test"]["mae"],
                            "improvement_pct": round((base["mae"] - s["test"]["mae"]) / base["mae"] * 100, 2),
                            "met": s["test"]["mae"] < base["mae"]}
    return result


def route_profiles(trips: pd.DataFrame) -> pd.DataFrame:
    """The eight route features of run_clusters (train period), one row per route, sorted by route_id."""
    x = p7.period(trips, "train")
    x["occupancy"] = x.max_load / x.capacity_total
    x["travel"] = (pd.to_datetime(x.actual_arrival) - pd.to_datetime(x.actual_departure)).dt.total_seconds() / 60
    daily = x.groupby(["route_id", "service_date"]).boardings.sum().rename("daily").reset_index()
    growth = daily.sort_values(["route_id", "service_date"])
    growth["mom"] = growth.groupby("route_id").daily.pct_change(28)
    r = x.groupby("route_id").agg(avg_occupancy=("occupancy", "mean"), avg_delay_minutes=("delay_minutes", "mean"),
                                  reliability_score=("delay_minutes", lambda s: (s < 5).mean()),
                                  trip_frequency=("trip_id", "count"), load_factor=("occupancy", "mean"),
                                  avg_travel_time=("travel", "mean")).reset_index()
    z = daily.groupby("route_id").daily.agg(avg_daily_boardings="mean", peak="max").reset_index()
    z["peak_demand_ratio"] = z.peak / z.avg_daily_boardings
    return (r.merge(z[["route_id", "avg_daily_boardings", "peak_demand_ratio"]], "left", "route_id")
             .merge(growth.groupby("route_id").mom.mean().rename("demand_mom_growth"), "left", "route_id"))


def evaluate_clustering(trips: pd.DataFrame) -> dict:
    """Re-score the clustering algorithm selected in the serving configuration."""
    algorithm = served_algorithm("route_clustering")
    rec = recorded("route_clustering", algorithm)
    r = route_profiles(p7.period(trips, "train"))
    X = joblib.load(MODELS / "route_clustering" / "scaler_v1.pkl").transform(
        SimpleImputer(strategy="median").fit_transform(r[rec["features"]]))
    saved = joblib.load(MODELS / "route_clustering" / f"{algorithm}_v1.pkl")
    labels = saved.predict(X) if hasattr(saved, "predict") else saved.labels_
    score = round(float(silhouette_score(X, labels)), 6)
    return {
        "task": "route_clustering", "routes": len(r), "selected": algorithm,
        "model_file": f"models/python/route_clustering/{algorithm}_v1.pkl",
        "silhouette": score, "recorded_silhouette": rec["silhouette"],
        "metric_match": abs(score - rec["silhouette"]) <= TOLERANCE,
        "clusters": int(len(set(labels))),
    }


def print_summary(report: dict) -> None:
    for c in report["classifiers"]:
        for split, s in c["splits"].items():
            ok = all(v["match"] for v in s.get("vs_recorded", {}).values())
            recorded_note = f"recorded={'MATCH' if ok else 'DIFFERS'}" if "vs_recorded" in s else "(not recorded)"
            print(f"{c['task']:16s} {c['algorithm']:8s} {split:10s} rows={s['rows']:>8,d} "
                  f"acc={s['accuracy']:.4f} macroF1={s['macro_f1']:.4f}  {recorded_note}")
            if "within_one_band_accuracy" in s:
                print(f"{'':16s} ordinal within-one-band accuracy={s['within_one_band_accuracy']:.4f}")
        g = c["train_vs_test"]
        print(f"{'':16s} train->test gap: accuracy {g['accuracy']['gap']:+.4f}, macro F1 {g['macro_f1']['gap']:+.4f}")
        print(f"{'':16s} SRS target: accuracy met={c['srs_target']['accuracy_met']}, macro F1 met={c['srs_target']['macro_f1_met']}")
    for name, a in report["demand"]["algorithms"].items():
        t, g = a["test"], a["train_vs_test"]["r2"]
        ok = all(v["match"] for s in ("validation", "test") for v in a[s]["vs_recorded"].values())
        print(f"daily_boardings  {name:14s} train R2={g['train']:.3f} test MAE={t['mae']:8.1f} RMSE={t['rmse']:8.1f} "
              f"R2={t['r2']:.3f}  recorded={'MATCH' if ok else 'DIFFERS'}")
    print(f"{'':16s} SRS target: {report['demand']['srs_target']}")
    occupancy = report["occupancy_forecast"]
    test, g = occupancy["splits"]["test"], occupancy["train_vs_test"]["r2"]
    ok = all(v["match"] for s in occupancy["splits"].values() for v in s.get("vs_recorded", {}).values())
    print(f"occupancy_forecast {occupancy['algorithm']:8s} train R2={g['train']:.3f} test MAE={test['mae']:.4f} "
          f"RMSE={test['rmse']:.4f} R2={test['r2']:.3f} within20pp={test['within_20pp_accuracy']:.3f}  "
          f"recorded={'MATCH' if ok else 'DIFFERS'}")
    c = report["clustering"]
    print(f"route_clustering {c['selected']} silhouette={c['silhouette']} "
          f"(recorded {c['recorded_silhouette']}), match={c['metric_match']}")


def main() -> int:
    trips = p7.base_trip()
    report = {
        "purpose": "Re-score the shared Phase 7 model files on this machine; no training.",
        "split_dates": p7.DATES,
        "tolerance": TOLERANCE,
        "classifiers": [evaluate_classifier(trips, t, served_algorithm(t)) for t in ("crowding_flag", "delay_severity")],
        "demand": evaluate_demand(),
        "occupancy_forecast": evaluate_occupancy(trips),
        "clustering": evaluate_clustering(trips),
    }
    checks = [v["match"] for c in report["classifiers"] for s in c["splits"].values()
              for v in s.get("vs_recorded", {}).values()]
    checks += [v["match"] for a in report["demand"]["algorithms"].values()
               for s in ("validation", "test") for v in a[s]["vs_recorded"].values()]
    checks += [v["match"] for s in report["occupancy_forecast"]["splits"].values()
               for v in s.get("vs_recorded", {}).values()]
    checks.append(report["clustering"]["metric_match"])
    report["result"] = "PASS" if all(checks) else "DIFFERS"
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print_summary(report)
    print(f"-> {report['result']} ({sum(checks)}/{len(checks)} checks match); written to {REPORT_PATH.relative_to(ROOT)}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
