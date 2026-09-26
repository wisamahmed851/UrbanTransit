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
LOCAL = ROOT / "python_pipeline" / "local_clean"
MODEL = ROOT / "models" / "python"
METRICS = MODEL / "metrics"
SAMPLES = ROOT / "reports" / "python_sample_predictions"
REPORT = ROOT / "reports" / "python_model_metrics.md"
DATES = {"train": ("2025-09-01", "2026-05-01"), "validation": ("2026-05-02", "2026-07-01"), "test": ("2026-07-02", "2026-08-31")}
RNG = 42

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
    x["delay_severity"] = pd.cut(x.delay_minutes, [-np.inf,5,10,20,np.inf], labels=["On Time","Minor","Moderate","Severe"], right=False).astype(str)
    x["crowding_flag"] = ((x.max_load / x.capacity_total) > .9).astype("float")
    x.loc[x.max_load.isna() | x.capacity_total.isna() | (x.capacity_total <= 0), "crowding_flag"] = np.nan
    x = x.sort_values(["route_id","direction","scheduled_departure","trip_id"])
    x["prior_route_delay_mean"] = x.groupby(["route_id","direction"]).delay_minutes.transform(lambda s: s.shift().rolling(28,min_periods=5).mean())
    x["prior_route_crowding_rate"] = x.groupby(["route_id","direction"]).crowding_flag.transform(lambda s: s.shift().rolling(28,min_periods=5).mean())
    return x

def prep(frame, numeric, categorical):
    return ColumnTransformer([("num", Pipeline([("impute",SimpleImputer(strategy="median")),("scale",StandardScaler())]), numeric),
                              ("cat", Pipeline([("impute",SimpleImputer(strategy="most_frequent")),("encode",OrdinalEncoder(handle_unknown="use_encoded_value",unknown_value=-1))]), categorical)])

def run_classification(task, target, drop, xgb_classes):
    x = base_trip().dropna(subset=[target]).copy()
    numeric = ["hour","day_of_week","weekend","distance_km","planned_runtime_min","headway_min","scheduled_runtime_min",drop]
    categorical = ["route_id","vehicle_id","direction","route_type","vehicle_type"]
    numeric = [c for c in numeric if c not in {target,"occupancy_pct"}]
    # Task B never uses current occupancy, max-load, boardings, or any direct target proxy.
    cols=numeric+categorical
    x.loc[:, numeric] = x[numeric].replace([np.inf, -np.inf], np.nan)
    tr, va, te = (period(x,s) for s in ("train","validation","test"))
    # Keep fitting bounded in WSL; validation/test remain complete chronological splits.
    if len(tr)>400000:
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
        record={"task":task,"algorithm":name,"features":{"numeric":numeric,"categorical":categorical},"split_dates":DATES,"validation":val,"test":test,"threshold":threshold,"test_default_threshold":default if task=="crowding_flag" else None,"model_scope":"independent pandas/PyArrow clean-Parquet pipeline"}
        save_json(task,name,record); results[name]=(record,m,pt,predt,labels if name=="xgboost" else list(m.classes_),encoder); chosen.append((val["macro_f1"],name))
    _,name=max(chosen); record,m,probs,preds,classes,encoder=results[name]
    out=MODEL/task; out.mkdir(parents=True,exist_ok=True); joblib.dump(m,out/f"{name}_v1.pkl"); joblib.dump(encoder,out/f"{name}_preprocessor_v1.pkl")
    posprob=probs.max(1); sample=te[["trip_id","route_id","service_date",target]].copy(); sample["predicted"]=preds; sample["probability"]=posprob; sample["split"]="test"; SAMPLES.mkdir(parents=True,exist_ok=True); sample.head(20).to_csv(SAMPLES/f"{task}_best.csv",index=False)
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
    p=argparse.ArgumentParser(); p.add_argument("--task",choices=["a","b","c","d","all"],default="all"); a=p.parse_args(); results={}
    if a.task in ("a","all"): results["delay_severity"]=run_classification("delay_severity","delay_severity","prior_route_delay_mean",4)
    if a.task in ("b","all"): results["crowding_flag"]=run_classification("crowding_flag","crowding_flag","prior_route_crowding_rate",2)
    if a.task in ("c","all"): results["daily_boardings"]=run_demand()
    if a.task in ("d","all"):
        o,n,pf=run_clusters(); results["route_clustering"]={k:(v[0],) for k,v in o.items()}
    write_docs(results)

if __name__ == "__main__": main()
