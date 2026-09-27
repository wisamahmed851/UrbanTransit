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
from sklearn.cluster import AgglomerativeClustering
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python_pipeline"))

import phase7_python_models as p7  # noqa: E402

MODELS = ROOT / "models" / "python"
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


def evaluate_classifier(trips: pd.DataFrame, task: str, algorithm: str = "xgboost") -> dict:
    """Score `<task>/<algorithm>_v1.pkl` exactly the way run_classification scored it."""
    rec = recorded(task, algorithm)
    numeric, categorical = rec["features"]["numeric"], rec["features"]["categorical"]
    model = joblib.load(MODELS / task / f"{algorithm}_v1.pkl")
    prep = joblib.load(MODELS / task / f"{algorithm}_preprocessor_v1.pkl")
    labels = rec["test"]["confusion_matrix"]["labels"]      # sorted class names, as in training

    frame = trips.dropna(subset=[task]).copy()
    frame.loc[:, numeric] = frame[numeric].replace([np.inf, -np.inf], np.nan)
    result = {"task": task, "algorithm": algorithm, "model_file": f"models/python/{task}/{algorithm}_v1.pkl",
              "features": numeric + categorical, "threshold": rec.get("threshold"), "splits": {}}
    for split in ("validation", "test"):
        part = p7.period(frame, split)
        proba = model.predict_proba(prep.transform(part[numeric + categorical]))
        if rec.get("threshold") is not None:           # binary crowding flag: tuned threshold on class "1.0"
            pred = np.where(proba[:, labels.index("1.0")] >= rec["threshold"], "1.0", "0.0")
        else:
            pred = np.array(labels)[proba.argmax(1)]
        scores = p7.cls_scores(part[task].astype(str), pred)
        result["splits"][split] = {"rows": len(part), "accuracy": scores["accuracy"], "macro_f1": scores["macro_f1"],
                                   "per_class_f1": scores["per_class_f1"], "confusion_matrix": scores["confusion_matrix"],
                                   "vs_recorded": compare(rec[split], scores, ("accuracy", "macro_f1"))}
    test = result["splits"]["test"]
    result["srs_target"] = {"rule": "accuracy >= 0.85 or macro F1 >= 0.80 (SRS NFR 4)",
                            "accuracy_met": test["accuracy"] >= TARGET_ACCURACY,
                            "macro_f1_met": test["macro_f1"] >= TARGET_MACRO_F1}
    return result


def evaluate_demand() -> dict:
    """Score the three saved regressors and the 28-day baseline on the demand frame."""
    d = p7.demand_frame()
    feats = ["lag_1", "lag_7", "lag_28", "rolling_7_mean", "rolling_28_mean"]
    splits = {s: p7.period(d, s).dropna(subset=feats) for s in ("validation", "test")}
    result = {"task": "daily_boardings", "features": feats, "algorithms": {}}
    for name in ("baseline_28day", "ridge", "random_forest", "xgboost"):
        rec, row = recorded("daily_boardings", name), {}
        model = None if name == "baseline_28day" else joblib.load(MODELS / "daily_boardings" / f"{name}_v1.pkl")
        for split, part in splits.items():
            pred = part.rolling_28_mean if model is None else model.predict(part[feats])
            scores = p7.reg_scores(part.boardings, pred)
            row[split] = {"rows": len(part), **scores, "vs_recorded": compare(rec[split], scores, ("mae", "rmse", "r2"))}
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
    task, algorithm = "occupancy_forecast", "random_forest"
    rec = recorded(task, algorithm)
    numeric, categorical = rec["features"]["numeric"], rec["features"]["categorical"]
    model = joblib.load(MODELS / task / f"{algorithm}_v1.pkl")
    prep = joblib.load(MODELS / task / f"{algorithm}_preprocessor_v1.pkl")
    frame = trips.dropna(subset=["occupancy_pct", "prior_route_occupancy_mean"]).copy()
    frame.loc[:, numeric] = frame[numeric].replace([np.inf, -np.inf], np.nan)
    result = {"task": task, "algorithm": algorithm, "target": rec["target"], "splits": {}}
    for split in ("validation", "test"):
        part = p7.period(frame, split)
        scores = p7.occupancy_scores(part.occupancy_pct, model.predict(prep.transform(part[numeric + categorical])))
        result["splits"][split] = {"rows": len(part), **scores,
                                   "vs_recorded": compare(rec[split], scores, ("mae", "rmse", "r2"))}
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
    """Agglomerative clustering cannot score new points, so it is refitted (deterministic) and its
    labels are compared with the saved model's `labels_`; K-Means k=5 is scored with `predict`."""
    rec = recorded("route_clustering", "agglomerative_k5")
    r = route_profiles(trips)
    X = joblib.load(MODELS / "route_clustering" / "scaler_v1.pkl").transform(
        SimpleImputer(strategy="median").fit_transform(r[rec["features"]]))
    saved = joblib.load(MODELS / "route_clustering" / "agglomerative_k5_v1.pkl")
    refit = AgglomerativeClustering(n_clusters=5).fit_predict(X)
    kmeans = joblib.load(MODELS / "route_clustering" / "kmeans_k5_v1.pkl")
    return {
        "task": "route_clustering", "routes": len(r), "selected": "agglomerative_k5",
        "agglomerative_k5": {"silhouette": round(float(silhouette_score(X, saved.labels_)), 6),
                             "recorded_silhouette": rec["silhouette"],
                             "labels_identical_to_saved_model": bool((refit == saved.labels_).all()),
                             "clusters": int(len(set(saved.labels_)))},
        # run_clusters saves only the best model; this file is left over from an older run.
        "kmeans_k5_v1.pkl": {"expects_features": int(kmeans.n_features_in_), "current_features": X.shape[1],
                             "status": "stale file from an earlier 9-feature run; not scored, not served"
                             if kmeans.n_features_in_ != X.shape[1] else "compatible"},
    }


def print_summary(report: dict) -> None:
    for c in report["classifiers"]:
        for split, s in c["splits"].items():
            ok = all(v["match"] for v in s["vs_recorded"].values())
            print(f"{c['task']:16s} {c['algorithm']:8s} {split:10s} rows={s['rows']:>8,d} "
                  f"acc={s['accuracy']:.4f} macroF1={s['macro_f1']:.4f}  recorded={'MATCH' if ok else 'DIFFERS'}")
        print(f"{'':16s} SRS target: accuracy met={c['srs_target']['accuracy_met']}, macro F1 met={c['srs_target']['macro_f1_met']}")
    for name, a in report["demand"]["algorithms"].items():
        t = a["test"]
        ok = all(v["match"] for s in ("validation", "test") for v in a[s]["vs_recorded"].values())
        print(f"daily_boardings  {name:14s} test MAE={t['mae']:8.1f} RMSE={t['rmse']:8.1f} R2={t['r2']:.3f}  recorded={'MATCH' if ok else 'DIFFERS'}")
    print(f"{'':16s} SRS target: {report['demand']['srs_target']}")
    occupancy = report["occupancy_forecast"]
    test = occupancy["splits"]["test"]
    ok = all(v["match"] for s in occupancy["splits"].values() for v in s["vs_recorded"].values())
    print(f"occupancy_forecast {occupancy['algorithm']:8s} test MAE={test['mae']:.4f} RMSE={test['rmse']:.4f} R2={test['r2']:.3f}  recorded={'MATCH' if ok else 'DIFFERS'}")
    c = report["clustering"]["agglomerative_k5"]
    print(f"route_clustering agglomerative_k5 silhouette={c['silhouette']} (recorded {c['recorded_silhouette']}), "
          f"labels identical={c['labels_identical_to_saved_model']}")


def main() -> int:
    trips = p7.base_trip()
    report = {
        "purpose": "Re-score the shared Phase 7 model files on this machine; no training.",
        "split_dates": p7.DATES,
        "tolerance": TOLERANCE,
        "classifiers": [evaluate_classifier(trips, "crowding_flag"), evaluate_classifier(trips, "delay_severity")],
        "demand": evaluate_demand(),
        "occupancy_forecast": evaluate_occupancy(trips),
        "clustering": evaluate_clustering(trips),
    }
    checks = [v["match"] for c in report["classifiers"] for s in c["splits"].values() for v in s["vs_recorded"].values()]
    checks += [v["match"] for a in report["demand"]["algorithms"].values()
               for s in ("validation", "test") for v in a[s]["vs_recorded"].values()]
    checks += [v["match"] for s in report["occupancy_forecast"]["splits"].values()
               for v in s["vs_recorded"].values()]
    checks.append(report["clustering"]["agglomerative_k5"]["labels_identical_to_saved_model"])
    report["result"] = "PASS" if all(checks) else "DIFFERS"
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print_summary(report)
    print(f"-> {report['result']} ({sum(checks)}/{len(checks)} checks match); written to {REPORT_PATH.relative_to(ROOT)}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
