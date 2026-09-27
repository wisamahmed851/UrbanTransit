#!/usr/bin/env python3
"""Independent Phase 7 pandas/scikit-learn/XGBoost modelling pipeline.

This module intentionally has no Spark imports and never reads Phase 4/6 tables,
models, or predictions.  It derives inputs afresh from clean Parquet staged by
stage_clean_parquet.sh.
"""
from __future__ import annotations

import argparse, json, math
from datetime import date
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             mean_absolute_error, mean_absolute_percentage_error,
                             mean_squared_error, r2_score, silhouette_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier, XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings

LOCAL = ROOT / "python_pipeline" / "local_clean"
MODEL = ROOT / "models" / "python"
METRICS = MODEL / "metrics"
SAMPLES = ROOT / "reports" / "python_sample_predictions"
REPORT = ROOT / "reports" / "python_model_metrics.md"
DATES = {"train": ("2025-09-01", "2026-05-01"), "validation": ("2026-05-02", "2026-07-01"), "test": ("2026-07-02", "2026-08-31")}
RNG = 42


def delay_taxonomy() -> tuple[list[str], list[float]]:
    """The Phase 7 target is derived from the same declared four-class contract as Spark."""
    contract = settings.delay_severity_contract()
    return contract["labels"], contract["cutpoints_minutes"]

def read(name: str) -> pd.DataFrame:
    files = list((LOCAL / name).rglob("*.parquet"))
    if not files: raise FileNotFoundError(f"No staged clean Parquet for {name}; run stage_clean_parquet.sh")
    return pd.read_parquet(files)

def period(df: pd.DataFrame, split: str) -> pd.DataFrame:
    lo, hi = map(pd.Timestamp, DATES[split]); d = pd.to_datetime(df.service_date)
    return df[(d >= lo) & (d <= hi)].copy()

def save_json(task, algorithm, obj):
    METRICS.mkdir(parents=True, exist_ok=True)
    path = METRICS / f"{task}_{algorithm}.json"
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    return path

def cls_scores(y, p):
    labels = sorted(pd.unique(y).tolist())
    return {"accuracy": round(float(accuracy_score(y, p)), 6), "macro_f1": round(float(f1_score(y, p, average="macro", zero_division=0)), 6),
            "per_class_f1": {str(k): round(float(v), 6) for k, v in zip(labels, f1_score(y, p, labels=labels, average=None, zero_division=0))},
            "confusion_matrix": {"labels": labels, "values": confusion_matrix(y, p, labels=labels).tolist()}}

def reg_scores(y, p):
    return {"mae": round(float(mean_absolute_error(y,p)),6), "rmse": round(float(mean_squared_error(y,p)**.5),6),
            "mape": round(float(mean_absolute_percentage_error(y,p)*100),6), "r2": round(float(r2_score(y,p)),6)}


def occupancy_scores(y, p):
    """Regression scores for an occupancy ratio; ordinary MAPE is undefined at zero."""
    out = {"mae": round(float(mean_absolute_error(y, p)), 6),
           "rmse": round(float(mean_squared_error(y, p) ** .5), 6),
           "r2": round(float(r2_score(y, p)), 6)}
    observed = np.asarray(y, dtype=float)
    predicted = np.asarray(p, dtype=float)
    nonzero = observed > 0.01
    out["mape_nonzero_pct"] = (round(float(np.mean(np.abs((observed[nonzero] - predicted[nonzero]) / observed[nonzero])) * 100), 6)
                               if nonzero.any() else None)
    out["mape_note"] = "MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined."
    return out


def count_scores(y, p):
    """Regression scores for non-negative counts; MAPE excludes true zero counts."""
    out = reg_scores(y, p)
    actual, predicted = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    nonzero = actual > 0
    out.pop("mape", None)
    out["mape_nonzero_pct"] = (round(float(np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])) * 100), 6)
                               if nonzero.any() else None)
    out["mape_note"] = "MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero."
    return out

def base_trip() -> pd.DataFrame:
    trips, pc, delays, vehicles, routes, schedules = (read(x) for x in ("trips","passenger_counts","delays","vehicles","routes","schedules"))
    trips = trips[trips.trip_status.eq("completed")].copy()
    pc = pc.groupby("trip_id", as_index=False).agg(boardings=("boardings","sum"), max_load=("max_load","max"))
    delay = delays.groupby("trip_id", as_index=False).agg(delay_minutes=("delay_minutes","mean"))
    x = trips.merge(pc,"left","trip_id").merge(delay,"left","trip_id").merge(vehicles[["vehicle_id","capacity_total","vehicle_type"]],"left","vehicle_id").merge(routes[["route_id","route_type","distance_km"]],"left","route_id").merge(schedules[["schedule_id","planned_runtime_min","headway_min"]],"left","schedule_id")
    x["service_date"] = pd.to_datetime(x.service_date); x["hour"] = pd.to_datetime(x.scheduled_departure).dt.hour
    x["day_of_week"] = x.service_date.dt.dayofweek; x["weekend"] = (x.day_of_week >= 5).astype(int)
    x["scheduled_runtime_min"] = (pd.to_datetime(x.scheduled_arrival)-pd.to_datetime(x.scheduled_departure)).dt.total_seconds()/60
    # Clean delay logs contain exceptions; no clean record means within the documented 5-minute tolerance.
    x["delay_minutes"] = x.delay_minutes.fillna(0.0)
    labels, cutpoints = delay_taxonomy()
    x["delay_severity"] = pd.cut(x.delay_minutes, [-np.inf, *cutpoints, np.inf], labels=labels, right=False).astype(str)
    x["crowding_flag"] = ((x.max_load / x.capacity_total) > .9).astype("float")
    x.loc[x.max_load.isna() | x.capacity_total.isna() | (x.capacity_total <= 0), "crowding_flag"] = np.nan
    x = x.sort_values(["route_id","direction","scheduled_departure","trip_id"])
    x["prior_route_delay_mean"] = x.groupby(["route_id","direction"]).delay_minutes.transform(lambda s: s.shift().rolling(28,min_periods=5).mean())
    # These are all strictly earlier completed trips in the same route/time cell.
    # They are safe for a pre-departure estimate and capture recurring peak-period
    # delay patterns that a route-wide average misses.
    hour_groups = x.groupby(["route_id","direction","hour"])
    x["prior_route_hour_delay_mean"] = hour_groups.delay_minutes.transform(lambda s: s.shift().rolling(56,min_periods=5).mean())
    x["prior_route_hour_severe_rate"] = hour_groups.delay_severity.transform(
        lambda s: s.eq("Severe").shift().rolling(56,min_periods=5).mean())
    x["prior_route_crowding_rate"] = x.groupby(["route_id","direction"]).crowding_flag.transform(lambda s: s.shift().rolling(28,min_periods=5).mean())
    # Current-trip max_load / occupancy is the target, never a model input. This
    # feature ends at the preceding trip and is safe for a future-trip estimate.
    x["occupancy_pct"] = x.max_load / x.capacity_total
    x.loc[(x.capacity_total <= 0) | ~np.isfinite(x.occupancy_pct), "occupancy_pct"] = np.nan
    x["prior_route_occupancy_mean"] = x.groupby(["route_id","direction"]).occupancy_pct.transform(
        lambda s: s.shift().rolling(28, min_periods=5).mean())
    x["prior_route_hour_occupancy_mean"] = x.groupby(["route_id", "direction", "hour"]).occupancy_pct.transform(
        lambda s: s.shift().rolling(56, min_periods=5).mean())
    return x

def prep(frame, numeric, categorical):
    return ColumnTransformer([("num", Pipeline([("impute",SimpleImputer(strategy="median")),("scale",StandardScaler())]), numeric),
                              ("cat", Pipeline([("impute",SimpleImputer(strategy="most_frequent")),("encode",OrdinalEncoder(handle_unknown="use_encoded_value",unknown_value=-1))]), categorical)])

def run_classification(task, target, drop, xgb_classes, version="v1", enhanced_delay=False, full_train=False):
    x = base_trip().dropna(subset=[target]).copy()
    numeric = ["hour","day_of_week","weekend","distance_km","planned_runtime_min","headway_min","scheduled_runtime_min",drop]
    categorical = ["route_id","vehicle_id","direction","route_type","vehicle_type"]
    numeric = [c for c in numeric if c not in {target,"occupancy_pct"}]
    if task == "delay_severity" and enhanced_delay:
        numeric += ["prior_route_hour_delay_mean", "prior_route_hour_severe_rate"]
    # Task B never uses current occupancy, max-load, boardings, or any direct target proxy.
    cols=numeric+categorical
    x.loc[:, numeric] = x[numeric].replace([np.inf, -np.inf], np.nan)
    tr, va, te = (period(x,s) for s in ("train","validation","test"))
    # Keep fitting bounded in WSL; validation/test remain complete chronological splits.
    if len(tr)>400000 and not full_train:
        # Deterministic capped stratified fit set; validation and test stay complete.
        cap = 400000 // tr[target].nunique()
        tr = tr.groupby(target, group_keys=False).apply(lambda g: g.sample(n=min(len(g), cap), random_state=RNG), include_groups=True).reset_index(drop=True)
    encoder=prep(tr, numeric, categorical); Xtr=encoder.fit_transform(tr[cols]); Xv=encoder.transform(va[cols]); Xt=encoder.transform(te[cols])
    ytr,yv,yt=tr[target].astype(str),va[target].astype(str),te[target].astype(str)
    algorithms={
      "logistic_regression": LogisticRegression(max_iter=500,class_weight="balanced",n_jobs=-1),
      "random_forest": RandomForestClassifier(n_estimators=180,max_depth=12,min_samples_leaf=3,class_weight="balanced",n_jobs=-1,random_state=RNG),
      "xgboost": XGBClassifier(n_estimators=300,max_depth=8,learning_rate=.08,subsample=.85,colsample_bytree=.9,tree_method="hist",n_jobs=-1,random_state=RNG,eval_metric="mlogloss" if xgb_classes>2 else "logloss")}
    results={}; chosen=[]
    for name,m in algorithms.items():
        if name=="xgboost":
            labels=sorted(ytr.unique()); lookup={v:i for i,v in enumerate(labels)}; a,b,c=ytr.map(lookup),yv.map(lookup),yt.map(lookup)
            m.fit(Xtr,a,sample_weight=compute_sample_weight("balanced",a)); pv=m.predict_proba(Xv); pt=m.predict_proba(Xt); predv=np.array(labels)[pv.argmax(1)]; predt=np.array(labels)[pt.argmax(1)]
        else:
            m.fit(Xtr,ytr); pv=m.predict_proba(Xv); pt=m.predict_proba(Xt); predv=m.classes_[pv.argmax(1)]; predt=m.classes_[pt.argmax(1)]
        threshold=None
        if task=="crowding_flag":
            pos = list(m.classes_).index("1.0") if name!="xgboost" else labels.index("1.0")
            trials=[]
            for t in np.arange(.15,.71,.05): trials.append((float(t),cls_scores(yv,np.where(pv[:,pos]>=t,"1.0","0.0"))["macro_f1"]))
            threshold,maxf=max(trials,key=lambda z:z[1]); predv=np.where(pv[:,pos]>=threshold,"1.0","0.0"); predt=np.where(pt[:,pos]>=threshold,"1.0","0.0")
            default=cls_scores(yt,np.where(pt[:,pos]>=.5,"1.0","0.0"))
        val,test=cls_scores(yv,predv),cls_scores(yt,predt)
        record={"task":task,"algorithm":name,"version":version,"feature_set":"enhanced_strict_prior_route_hour_history" if task=="delay_severity" and enhanced_delay else "baseline_safe_features","features":{"numeric":numeric,"categorical":categorical},"split_dates":DATES,"validation":val,"test":test,"threshold":threshold,"test_default_threshold":default if task=="crowding_flag" else None,"model_scope":"independent pandas/PyArrow clean-Parquet pipeline"}
        metric_name = f"{name}_{version}" if version != "v1" else name
        save_json(task,metric_name,record); results[name]=(record,m,pt,predt,labels if name=="xgboost" else list(m.classes_),encoder); chosen.append((val["macro_f1"],name))
    _,name=max(chosen); record,m,probs,preds,classes,encoder=results[name]
    out=MODEL/task; out.mkdir(parents=True,exist_ok=True); joblib.dump(m,out/f"{name}_{version}.pkl"); joblib.dump(encoder,out/f"{name}_preprocessor_{version}.pkl")
    posprob=probs.max(1); sample=te[["trip_id","route_id","service_date",target]].copy(); sample["predicted"]=preds; sample["probability"]=posprob; sample["split"]="test"; SAMPLES.mkdir(parents=True,exist_ok=True); sample.head(20).to_csv(SAMPLES/f"{task}_{version}_best.csv",index=False)
    return results

def demand_frame():
    trips,pc=read("trips"),read("passenger_counts"); trips=trips[trips.trip_status.eq("completed")][["trip_id","route_id","service_date"]]
    p=pc.groupby("trip_id",as_index=False).agg(boardings=("boardings","sum")); d=trips.merge(p,"inner","trip_id"); d.service_date=pd.to_datetime(d.service_date)
    d=d.groupby(["route_id","service_date"],as_index=False).boardings.sum().sort_values(["route_id","service_date"])
    for lag in (1,7,28): d[f"lag_{lag}"]=d.groupby("route_id").boardings.shift(lag)
    for w in (7,28): d[f"rolling_{w}_mean"]=d.groupby("route_id").boardings.transform(lambda s:s.shift().rolling(w,min_periods=1).mean())
    return d

def run_demand():
    d=demand_frame(); feats=["lag_1","lag_7","lag_28","rolling_7_mean","rolling_28_mean"]; tr,va,te=(period(d,s).dropna(subset=feats) for s in ("train","validation","test"))
    base=lambda q:q.rolling_28_mean; algorithms={"baseline_28day":None,"ridge":Pipeline([("impute",SimpleImputer(strategy="median")),("scale",StandardScaler()),("model",Ridge(alpha=1.0))]),"random_forest":RandomForestRegressor(n_estimators=220,max_depth=14,min_samples_leaf=2,n_jobs=-1,random_state=RNG),"xgboost":XGBRegressor(n_estimators=350,max_depth=7,learning_rate=.05,subsample=.85,colsample_bytree=.9,tree_method="hist",n_jobs=-1,random_state=RNG)}; results={}
    for name,m in algorithms.items():
        if m is None: pv,pt=base(va),base(te)
        else: m.fit(tr[feats],tr.boardings); pv,pt=m.predict(va[feats]),m.predict(te[feats]); (MODEL/"daily_boardings").mkdir(parents=True,exist_ok=True); joblib.dump(m,MODEL/"daily_boardings"/f"{name}_v1.pkl")
        rec={"task":"daily_boardings","algorithm":name,"features":feats,"split_dates":DATES,"validation":reg_scores(va.boardings,pv),"test":reg_scores(te.boardings,pt),"lag_rule":"pandas shift() before every rolling aggregate; no current/future value"}; save_json("daily_boardings",name,rec); results[name]=(rec,pt)
    best=min((v[0]["validation"]["mae"],k) for k,v in results.items() if k!="baseline_28day")[1]; sm=te[["route_id","service_date","boardings"]].copy(); sm["predicted"]=results[best][1]; sm["split"]="test"; SAMPLES.mkdir(parents=True,exist_ok=True); sm.head(20).to_csv(SAMPLES/"daily_boardings_best.csv",index=False); return results


def run_occupancy_forecast(version="v1", full_train=False):
    """Estimate a trip's peak occupancy ratio before it departs.

    ``occupancy_pct`` is the target (max on-board load / assigned vehicle capacity).
    Current-trip load, boardings, occupancy and crowding flag are intentionally not
    features; the only occupancy signal is a prior-trip rolling mean.
    """
    x = base_trip().dropna(subset=["occupancy_pct"]).copy()
    numeric = ["hour", "day_of_week", "weekend", "distance_km", "planned_runtime_min",
               "headway_min", "scheduled_runtime_min", "capacity_total", "prior_route_occupancy_mean",
               "prior_route_hour_occupancy_mean"]
    categorical = ["route_id", "vehicle_id", "direction", "route_type", "vehicle_type"]
    cols = numeric + categorical
    x.loc[:, numeric] = x[numeric].replace([np.inf, -np.inf], np.nan)
    tr, va, te = (period(x, split).dropna(subset=["prior_route_occupancy_mean", "prior_route_hour_occupancy_mean"])
                  for split in ("train", "validation", "test"))
    if len(tr) > 400000 and not full_train:
        tr = tr.sample(n=400000, random_state=RNG).reset_index(drop=True)
    encoder = prep(tr, numeric, categorical)
    Xtr, Xv, Xt = encoder.fit_transform(tr[cols]), encoder.transform(va[cols]), encoder.transform(te[cols])
    output = MODEL / "occupancy_forecast"; output.mkdir(parents=True, exist_ok=True)
    # Candidate choice is based strictly on validation MAE. All candidates use the
    # same leakage-safe inputs and untouched chronological test split.
    candidates = {
        "ridge": Ridge(alpha=5.0),
        "random_forest": RandomForestRegressor(n_estimators=180, max_depth=16,
                                                  min_samples_leaf=3, n_jobs=-1, random_state=RNG),
    }
    results = {}
    for name, model in candidates.items():
        model.fit(Xtr, tr.occupancy_pct)
        rec = {
            "task": "occupancy_forecast", "algorithm": name, "version": version,
            "target": "occupancy_pct", "target_definition": "trip max_load / vehicle capacity_total",
            "target_unit": "ratio of assigned vehicle capacity", "feature_set": "strict_prior_route_and_route_hour_history",
            "features": {"numeric": numeric, "categorical": categorical}, "split_dates": DATES,
            "validation": occupancy_scores(va.occupancy_pct, model.predict(Xv)),
            "test": occupancy_scores(te.occupancy_pct, model.predict(Xt)),
            "leakage_guard": "Current-trip max_load, boardings, occupancy_pct and crowding_flag are excluded; every occupancy-history feature ends at the preceding trip.",
            "model_scope": "independent pandas/PyArrow clean-Parquet pipeline",
        }
        save_json("occupancy_forecast", name if version == "v1" else f"{name}_{version}", rec)
        joblib.dump(model, output / f"{name}_{version}.pkl")
        results[name] = (rec, model)
    best_name = min(results, key=lambda name: results[name][0]["validation"]["mae"])
    record, model = results[best_name]
    record["selection"] = {"selected_algorithm": best_name, "criterion": "lowest validation MAE",
                           "candidates": {name: value[0]["validation"] for name, value in results.items()}}
    save_json("occupancy_forecast", f"selected_{version}", record)
    joblib.dump(encoder, output / f"{best_name}_preprocessor_{version}.pkl")
    sample = te[["trip_id", "route_id", "service_date", "occupancy_pct"]].copy()
    sample["predicted"] = model.predict(Xt); sample["split"] = "test"
    SAMPLES.mkdir(parents=True, exist_ok=True)
    sample.head(20).to_csv(SAMPLES / f"occupancy_forecast_{version}_best.csv", index=False)
    return record


STOP_PERIODS = ("early", "am_peak", "midday", "pm_peak", "evening")


def time_period(hours: pd.Series) -> pd.Series:
    """Stable, operator-readable period buckets for tap-in demand."""
    return pd.cut(hours, [-1, 5, 9, 15, 19, 23], labels=STOP_PERIODS).astype(str)


def stop_period_demand_frame() -> pd.DataFrame:
    """Daily smart-card tap-ins for each observed stop and service-period cell.

    This uses the ticket's entry tap-in directly. It deliberately does not inflate
    smart-card journeys into all passenger demand: cash riders are not observed.
    """
    tickets = read("tickets")[["entry_stop_id", "service_date", "entry_time"]].dropna().copy()
    tickets["service_date"] = pd.to_datetime(tickets.service_date)
    tickets["hour"] = pd.to_datetime(tickets.entry_time).dt.hour
    tickets["time_period"] = time_period(tickets.hour)
    observed = tickets.groupby(["entry_stop_id", "service_date", "time_period"], as_index=False).size().rename(columns={"size": "tap_ins"})
    # Zero is a valid observed count. Generate it only for a stop-period cell that
    # has appeared, rather than claiming unobserved service periods are zero demand.
    cells = observed[["entry_stop_id", "time_period"]].drop_duplicates()
    dates = pd.date_range(observed.service_date.min(), observed.service_date.max(), freq="D")
    grid = cells.merge(pd.DataFrame({"service_date": dates}), how="cross")
    d = grid.merge(observed, how="left", on=["entry_stop_id", "service_date", "time_period"])
    d["tap_ins"] = d.tap_ins.fillna(0.0).astype(float)
    d["day_of_week"] = d.service_date.dt.dayofweek
    d["weekend"] = (d.day_of_week >= 5).astype(int)
    d = d.sort_values(["entry_stop_id", "time_period", "service_date"])
    keys = ["entry_stop_id", "time_period"]
    for lag in (1, 7, 28):
        d[f"lag_{lag}"] = d.groupby(keys).tap_ins.shift(lag)
    for window in (7, 28):
        d[f"rolling_{window}_mean"] = d.groupby(keys).tap_ins.transform(
            lambda s: s.shift().rolling(window, min_periods=1).mean())
    return d


def stop_period_splits(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Use the latest available ticket months without pretending they extend to August.

    The staged ticket source ends in January 2026, unlike the APC source used for
    route-day demand.  A 31-day validation month and untouched final 31-day test
    month preserve chronological evaluation while keeping enough prior history.
    """
    end = pd.Timestamp(d.service_date.max()).normalize()
    test_start = end - pd.Timedelta(days=30)
    validation_start = test_start - pd.Timedelta(days=31)
    ready = d.dropna(subset=["lag_1", "lag_7", "lag_28"]).copy()
    train = ready[ready.service_date < validation_start].copy()
    validation = ready[(ready.service_date >= validation_start) & (ready.service_date < test_start)].copy()
    test = ready[ready.service_date >= test_start].copy()
    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError("Ticket history cannot form chronological train/validation/test splits.")
    dates = {
        "train": [str(train.service_date.min().date()), str(train.service_date.max().date())],
        "validation": [str(validation.service_date.min().date()), str(validation.service_date.max().date())],
        "test": [str(test.service_date.min().date()), str(test.service_date.max().date())],
    }
    return train, validation, test, dates


def run_stop_period_demand(version="v1"):
    """Train a stop × period tap-in demand forecast and trailing-average baseline."""
    d = stop_period_demand_frame()
    numeric = ["day_of_week", "weekend", "lag_1", "lag_7", "lag_28", "rolling_7_mean", "rolling_28_mean"]
    categorical = ["entry_stop_id", "time_period"]
    features = numeric + categorical
    tr, va, te, split_dates = stop_period_splits(d)
    encoder = prep(tr, numeric, categorical)
    Xtr, Xv, Xt = encoder.fit_transform(tr[features]), encoder.transform(va[features]), encoder.transform(te[features])
    candidates = {
        "ridge": Ridge(alpha=3.0),
        "random_forest": RandomForestRegressor(n_estimators=160, max_depth=16,
                                                  min_samples_leaf=2, n_jobs=-1, random_state=RNG),
    }
    results = {"baseline_28day": (count_scores(va.tap_ins, va.rolling_28_mean),
                                   count_scores(te.tap_ins, te.rolling_28_mean), None)}
    output = MODEL / "stop_period_demand"; output.mkdir(parents=True, exist_ok=True)
    for name, model in candidates.items():
        model.fit(Xtr, tr.tap_ins)
        validation = count_scores(va.tap_ins, np.clip(model.predict(Xv), 0, None))
        test = count_scores(te.tap_ins, np.clip(model.predict(Xt), 0, None))
        results[name] = (validation, test, model)
        save_json("stop_period_demand", name if version == "v1" else f"{name}_{version}", {
            "task": "stop_period_demand", "algorithm": name, "version": version,
            "target": "daily_smart_card_tap_ins",
            "target_definition": "ticket entry tap-ins per entry_stop_id × service_date × time_period",
            "coverage_note": "Smart-card and mobile-QR transactions only; cash riders are not observed.",
            "features": {"numeric": numeric, "categorical": categorical}, "split_dates": split_dates,
            "validation": validation, "test": test,
            "leakage_guard": "Lag and rolling features use only earlier same stop-period days.",
            "model_scope": "independent pandas/PyArrow clean-Parquet pipeline",
        })
        joblib.dump(model, output / f"{name}_{version}.pkl")
    selected = min(candidates, key=lambda name: results[name][0]["mae"])
    selected_record = {
        "task": "stop_period_demand", "algorithm": selected, "version": version,
        "target": "daily_smart_card_tap_ins",
        "target_definition": "ticket entry tap-ins per entry_stop_id × service_date × time_period",
        "coverage_note": "Smart-card and mobile-QR transactions only; cash riders are not observed.",
        "features": {"numeric": numeric, "categorical": categorical}, "split_dates": split_dates,
        "validation": results[selected][0], "test": results[selected][1],
        "baseline_28day": {"validation": results["baseline_28day"][0], "test": results["baseline_28day"][1]},
        "selection": {"selected_algorithm": selected, "criterion": "lowest validation MAE"},
        "leakage_guard": "Lag and rolling features use only earlier same stop-period days.",
        "model_scope": "independent pandas/PyArrow clean-Parquet pipeline",
    }
    save_json("stop_period_demand", f"selected_{version}", selected_record)
    joblib.dump(encoder, output / f"{selected}_preprocessor_{version}.pkl")
    sample = te[["entry_stop_id", "service_date", "time_period", "tap_ins"]].copy()
    sample["predicted"] = np.clip(results[selected][2].predict(Xt), 0, None)
    sample["split"] = "test"
    SAMPLES.mkdir(parents=True, exist_ok=True)
    sample.head(20).to_csv(SAMPLES / f"stop_period_demand_{version}_best.csv", index=False)
    return selected_record

def run_clusters():
    x=base_trip(); x=period(x,"train"); x["occupancy"]=(x.max_load/x.capacity_total); x["travel"]=(pd.to_datetime(x.actual_arrival)-pd.to_datetime(x.actual_departure)).dt.total_seconds()/60
    daily=x.groupby(["route_id","service_date"]).boardings.sum().rename("daily").reset_index(); growth=daily.sort_values(["route_id","service_date"]); growth["mom"]=growth.groupby("route_id").daily.pct_change(28)
    r=x.groupby("route_id").agg(avg_occupancy=("occupancy","mean"),avg_delay_minutes=("delay_minutes","mean"),reliability_score=("delay_minutes",lambda s:(s<5).mean()),trip_frequency=("trip_id","count"),load_factor=("occupancy","mean"),avg_travel_time=("travel","mean")).reset_index(); z=daily.groupby("route_id").daily.agg(avg_daily_boardings="mean",peak="max").reset_index(); z["peak_demand_ratio"]=z.peak/z.avg_daily_boardings; r=r.merge(z[["route_id","avg_daily_boardings","peak_demand_ratio"]],"left","route_id").merge(growth.groupby("route_id").mom.mean().rename("demand_mom_growth"),"left","route_id")
    # The eight Phase 6 concepts are recomputed from raw clean data here; daily
    # boardings is descriptive for profiles but not a clustering input.
    fs=["avg_occupancy","avg_delay_minutes","reliability_score","trip_frequency","peak_demand_ratio","load_factor","avg_travel_time","demand_mom_growth"]
    clean=SimpleImputer(strategy="median").fit_transform(r[fs]); scaler=StandardScaler(); X=scaler.fit_transform(clean); (MODEL/"route_clustering").mkdir(parents=True,exist_ok=True); joblib.dump(scaler,MODEL/"route_clustering"/"scaler_v1.pkl"); candidates={}
    for k in (3,4,5): candidates[f"kmeans_k{k}"]=KMeans(n_clusters=k,n_init=20,random_state=RNG); candidates[f"agglomerative_k{k}"]=AgglomerativeClustering(n_clusters=k)
    for eps in (.6,.8,1.0): candidates[f"dbscan_eps{eps}"]=DBSCAN(eps=eps,min_samples=4)
    out={}; best=None
    for name,m in candidates.items():
        lab=m.fit_predict(X); valid=len(set(lab))>1 and len(set(lab)-( {-1} if -1 in lab else set()))>1
        score=float(silhouette_score(X,lab)) if valid else None; rec={"task":"route_clustering","algorithm":name,"features":fs,"silhouette":round(score,6) if score is not None else None,"clusters":int(len(set(lab)))}; save_json("route_clustering",name,rec); out[name]=(rec,m,lab)
        if score is not None and (best is None or score>best[0]): best=(score,name)
    _,name=best; rec,m,lab=out[name]; joblib.dump(m,MODEL/"route_clustering"/f"{name}_v1.pkl"); prof=r.assign(cluster=lab).groupby("cluster")[fs+["avg_daily_boardings"]].mean().round(3)
    def profile_label(row):
        if row.avg_daily_boardings > 8000: return "Very-high-demand trunk routes"
        if row.demand_mom_growth > .5: return "Low-demand rapidly growing routes"
        if row.avg_delay_minutes > 3: return "Delay-prone mid-demand routes"
        if row.avg_occupancy > .5: return "High-load reliable routes"
        return "Low-demand reliable routes"
    prof["profile_label"] = prof.apply(profile_label, axis=1)
    prof.to_csv(ROOT/"reports"/"python_cluster_profiles.csv")
    SAMPLES.mkdir(parents=True, exist_ok=True)
    r.assign(predicted_cluster=lab, split="train").loc[:, ["route_id", "predicted_cluster", "split"]].head(20).to_csv(SAMPLES/"route_clustering_best.csv", index=False)
    return out, name, prof

def write_docs(results):
    lines=["# Python Model Metrics", "", "Independent Phase 7 pandas/PyArrow pipeline. Chronological split: train 2025-09-01..2026-05-01; validation 2026-05-02..2026-07-01; test 2026-07-02..2026-08-31.", ""]
    grouped = {}
    for path in sorted(METRICS.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8")); grouped.setdefault(rec["task"], []).append(rec)
    for task, recs in grouped.items():
        lines += [f"## {task}", "", "| algorithm | validation | test / silhouette |", "|---|---|---|"]
        for rec in recs:
            lines.append(f"| {rec['algorithm']} | `{rec.get('validation',{})}` | `{rec.get('test',rec.get('silhouette',''))}` |")
        lines.append("")
    REPORT.write_text("\n".join(lines),encoding="utf-8")

def main():
    p=argparse.ArgumentParser(); p.add_argument("--task",choices=["a","b","c","d","e","f","all"],default="all"); p.add_argument("--version", default="v1"); p.add_argument("--enhanced-delay", action="store_true", help="Use only strictly-prior route-hour delay history for Task A."); p.add_argument("--full-train", action="store_true", help="Train classifiers/occupancy model on every chronological training-split row instead of the deterministic 400k-row cap."); a=p.parse_args(); results={}
    if a.task in ("a","all"): results["delay_severity"]=run_classification("delay_severity","delay_severity","prior_route_delay_mean",4,a.version,a.enhanced_delay,a.full_train)
    if a.task in ("b","all"): results["crowding_flag"]=run_classification("crowding_flag","crowding_flag","prior_route_crowding_rate",2)
    if a.task in ("c","all"): results["daily_boardings"]=run_demand()
    if a.task in ("e","all"): results["occupancy_forecast"]=run_occupancy_forecast(a.version, a.full_train)
    if a.task in ("f","all"): results["stop_period_demand"]=run_stop_period_demand(a.version)
    if a.task in ("d","all"):
        o,n,pf=run_clusters(); results["route_clustering"]={k:(v[0],) for k,v in o.items()}
    write_docs(results)

if __name__ == "__main__": main()
