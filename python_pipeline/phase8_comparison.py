"""Phase 8 - dual-pipeline comparison (SRS steps 43-44, submission item 7).

Spark MLlib and Python predict the same unseen cases independently. This script
lines their predictions up and writes reports/comparison/task_{a,b,c}_*.csv and
reports/dual_pipeline_comparison_report.md.

Every number in the report is read from a saved metrics JSON or computed here from
the compared cases; none is typed in (SRS 1.8 rule 11).

Which models are compared:
* Python: the model config/serving.yaml serves, so the report describes what the UI uses.
* Spark: the saved, leakage-free MLlib model with the best *validation* score. Test
  scores never choose a model. A model whose inputs include occupancy_pct (measured
  only after the trip has run) is excluded, and so is one whose saved folder is empty.
  When no Spark model qualifies, the task is reported as not compared, with the reasons.

Cases are drawn from dates inside both pipelines' test splits. Python predictions are
made here with the saved Python model; Spark predictions need PySpark and the HDFS
feature tables (run inside WSL), and are cached under reports/spark_sample_predictions.

    python python_pipeline/phase8_comparison.py
"""
import json
import logging
import re
import sys
from datetime import date
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import accuracy_score, adjusted_rand_score, f1_score, mean_absolute_error

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SPARK_MODELS = ROOT / "models" / "spark"
PY_MODELS = ROOT / "models" / "python"
SAMPLES_SPARK = ROOT / "reports" / "spark_sample_predictions"
COMPARISON_DIR = ROOT / "reports" / "comparison"
REPORT = ROOT / "reports" / "dual_pipeline_comparison_report.md"

CASES = 500          # cases drawn per task
MIN_CASES = 100      # SRS submission item 7: at least 100 unseen cases
TOLERANCE = 0.10     # regression: within 10% counts as agreeing / correct
LEAKY_INPUT = re.compile(r"\boccupancy_pct\b")
# Trained by spark_jobs/phase6_colab_missing_task_a.py, whose NUMERIC list includes
# occupancy_pct. Their metrics JSONs do not record the feature list, so the name check
# above cannot see it.
LEAKY_SPARK = {("delay_severity", "decision_tree_sample"), ("delay_severity", "gbt_one_vs_rest_sample")}

TASKS = {
    "delay_severity": {"name": "Task A (delay severity)", "kind": "classification", "metric": "macro_f1",
                       "keys": ["trip_id"], "out": "task_a_delay_severity_comparison.csv"},
    "crowding_flag": {"name": "Task B (crowding risk)", "kind": "classification", "metric": "macro_f1",
                      "keys": ["trip_id"], "out": "task_b_crowding_comparison.csv"},
    "daily_boardings": {"name": "Task C (daily route demand)", "kind": "regression", "metric": "mae",
                        "keys": ["route_id", "service_date"], "out": "task_c_demand_comparison.csv"},
}
OUT_COLUMNS = ["case_id", "actual", "spark_actual", "spark_prediction", "python_prediction", "spark_value",
               "python_value", "spark_probability", "python_probability", "absolute_difference", "match",
               "agreement_status", "disagreement_explanation"]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(value, digits=4) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


# ---------------------------------------------------------------- model selection

def python_model(task: str) -> dict:
    """The served Python model and its metrics record."""
    served = yaml.safe_load((ROOT / "config" / "serving.yaml").read_text(encoding="utf-8"))["served"][task]
    algorithm, version = served["algorithm"], served["version"]
    stem = f"{task}_{algorithm}" + ("" if version == "v1" else f"_{version}")
    return {"algorithm": algorithm, "version": version, "record": read_json(PY_MODELS / "metrics" / f"{stem}.json")}


def spark_scores(record: dict, split: str) -> dict | None:
    names = {"train": ("train",), "validation": ("validation", "validation_sample"), "test": ("test", "test_full")}[split]
    metrics = record.get("metrics") or {}
    return next((metrics[n] for n in names if n in metrics), None)


def spark_model_dir(task: str, name: str) -> Path | None:
    for d in (SPARK_MODELS / task / name, SPARK_MODELS / task / f"{name}_v1"):
        if d.is_dir() and any(d.iterdir()):
            return d
    return None


def spark_model(task: str) -> dict:
    """Best leakage-free saved Spark model by validation score, plus every rejected candidate."""
    metric = TASKS[task]["metric"]
    lower_is_better = metric in ("mae", "rmse")
    best, rejected = None, []
    for path in sorted((SPARK_MODELS / "metrics").glob(f"{task}_*.json")):
        name, record = path.stem[len(task) + 1:], read_json(path)
        validation = (spark_scores(record, "validation") or {}).get(metric)
        if (task, name) in LEAKY_SPARK or LEAKY_INPUT.search(json.dumps(record)):
            reason = "input includes occupancy_pct, which is known only after the trip has run"
        elif spark_model_dir(task, name) is None:
            reason = "saved model folder is missing or empty on this machine"
        elif validation is None:
            reason = f"no validation {metric} recorded"
        else:
            reason = None
        if reason:
            rejected.append((name, reason))
            continue
        if best is None or (validation < best[0] if lower_is_better else validation > best[0]):
            best = (validation, name, record)
    if best is None:
        return {"name": None, "rejected": rejected}
    return {"name": best[1], "record": best[2], "dir": spark_model_dir(task, best[1]), "rejected": rejected}


def case_window(py: dict, spark: dict) -> tuple[str, str]:
    """Dates inside both pipelines' test splits: unseen by fitting and by model choice in each."""
    tests = [py["record"]["split_dates"]["test"], spark["record"]["split_dates"]["test"]]
    lo, hi = max(t[0] for t in tests), min(t[1] for t in tests)
    if lo > hi:
        raise ValueError(f"Spark and Python test splits do not overlap: {tests}")
    return lo, hi


# ---------------------------------------------------------------- Python predictions

@cache
def python_trip_frame() -> pd.DataFrame:
    from python_pipeline import phase7_python_models as p7
    return p7.base_trip()


def python_predictions(task: str, py: dict, lo: str, hi: str) -> pd.DataFrame:
    """Predictions from the saved Python model for every case in the window."""
    import joblib
    from python_pipeline import phase7_python_models as p7
    record, algorithm, version = py["record"], py["algorithm"], py["version"]
    model = joblib.load(PY_MODELS / task / f"{algorithm}_{version}.pkl")
    if task == "daily_boardings":
        features = record["features"]
        d = p7.demand_frame()
        d = d[(d.service_date >= lo) & (d.service_date <= hi)].dropna(subset=features)
        return pd.DataFrame({"route_id": d.route_id, "service_date": d.service_date.dt.strftime("%Y-%m-%d"),
                             "python_actual": d.boardings.astype(float), "python_prediction": model.predict(d[features])})

    prep = joblib.load(PY_MODELS / task / f"{algorithm}_preprocessor_{version}.pkl")
    numeric, categorical = record["features"]["numeric"], record["features"]["categorical"]
    x = python_trip_frame().dropna(subset=[task])
    x = x[(x.service_date >= lo) & (x.service_date <= hi)].copy()
    x[numeric] = x[numeric].replace([np.inf, -np.inf], np.nan)
    proba = model.predict_proba(prep.transform(x[numeric + categorical]))
    labels = record["test"]["confusion_matrix"]["labels"]   # predict_proba column order (as model_serving.py)
    if len(labels) != proba.shape[1]:
        raise ValueError(f"{task}: {proba.shape[1]} probability columns but {len(labels)} labels in the record")
    if task == "crowding_flag":
        positive = proba[:, labels.index("1.0")]
        prediction = np.where(positive >= record["threshold"], "1.0", "0.0")
        probability = positive
    else:
        prediction, probability = np.array(labels)[proba.argmax(1)], proba.max(1)
    return pd.DataFrame({"trip_id": x.trip_id.to_numpy(), "python_actual": x[task].astype(str).to_numpy(),
                         "python_prediction": prediction, "python_probability": probability.round(6)})


# ---------------------------------------------------------------- Spark predictions

def spark_predictions(task: str, spark_sel: dict, lo: str, hi: str) -> pd.DataFrame:
    """Cached Spark cases for this model and window, or a fresh Spark run to make them."""
    cache_file = SAMPLES_SPARK / f"{task}_{spark_sel['name']}_cases_{lo}_{hi}.csv"
    if cache_file.exists():
        cached = pd.read_csv(cache_file, dtype={"spark_actual": str, "spark_prediction": str} if task != "daily_boardings" else None)
        if len(cached) >= MIN_CASES:
            return cached
    SAMPLES_SPARK.mkdir(parents=True, exist_ok=True)
    frame = run_spark_predictions(task, spark_sel, lo, hi)
    frame.to_csv(cache_file, index=False)
    return frame


def run_spark_predictions(task: str, spark_sel: dict, lo: str, hi: str) -> pd.DataFrame:
    try:
        from pyspark.ml import PipelineModel
        from pyspark.ml.functions import vector_to_array
        from pyspark.sql import functions as F
        from pyspark.sql.window import Window
        from spark_jobs.common import get_spark, hdfs_uri
    except ImportError as e:
        raise RuntimeError(f"{task}: Spark predictions for {spark_sel['name']} are not cached and PySpark is "
                           "unavailable. Run this script inside WSL where Spark and HDFS are set up.") from e

    spark = get_spark(f"phase8-{task}")
    local = lambda path: path.resolve().as_uri()   # saved models are on local disk, not HDFS
    record, model_dir = spark_sel["record"], spark_sel["dir"]
    # Derived inputs are rebuilt exactly as the Phase 6 training scripts build them.
    if task == "daily_boardings":
        demand = spark.read.parquet(hdfs_uri("full", "features", "route_daily_demand"))
        w = Window.partitionBy("route_id").orderBy("service_date")
        base = (demand.withColumn("lag_1_demand", F.lag("estimated_daily_boardings", 1).over(w))
                .withColumn("lag_7_demand", F.lag("estimated_daily_boardings", 7).over(w))
                .withColumn("lag_28_demand", F.lag("estimated_daily_boardings", 28).over(w))
                .withColumn("rolling_7_mean", F.avg("estimated_daily_boardings").over(w.rowsBetween(-7, -1)))
                .withColumn("rolling_28_mean", F.avg("estimated_daily_boardings").over(w.rowsBetween(-28, -1)))
                .withColumn("month", F.month("service_date").cast("double"))
                .withColumn("day_of_week", F.col("day_of_week").cast("double"))
                .withColumn("weekend_indicator", F.col("weekend_indicator").cast("double"))
                .withColumn("label", F.col("estimated_daily_boardings").cast("double")))
        target, order = "estimated_daily_boardings", F.xxhash64("route_id", "service_date")
    else:
        trip = spark.read.parquet(hdfs_uri("full", "features", "trip_features"))
        route = spark.read.parquet(hdfs_uri("full", "features", "route_features")).select("route_id", "n_stops")
        by_route = Window.partitionBy("route_id").orderBy("scheduled_departure", "trip_id")
        prior = Window.partitionBy("route_id", "direction", "hour").orderBy("scheduled_departure", "trip_id").rowsBetween(-56, -1)
        base = (trip.join(route, "route_id", "left")
                .withColumn("weekend_indicator", F.col("weekend_indicator").cast("double"))
                .withColumn("peak_hour_indicator_asof", F.col("peak_hour_indicator_asof").cast("double"))
                .withColumn("rolling_28_mean_occupancy", F.avg("occupancy_pct").over(by_route.rowsBetween(-28, -1)))
                .withColumn("lag_7_occupancy", F.lag("occupancy_pct", 7).over(by_route))
                .withColumn("prior_route_hour_delay_mean", F.avg("delay_minutes").over(prior))
                .withColumn("prior_route_hour_crowding_rate", F.avg(F.col("crowding_flag").cast("double")).over(prior)))
        if task == "crowding_flag":
            base = base.withColumn("label", F.col("crowding_flag").cast("double"))
        target, order = task, F.xxhash64("trip_id")

    # Windows above see the full history; only then are the cases restricted to the window.
    cases = (base.filter(F.col(target).isNotNull())
             .filter((F.col("service_date") >= F.lit(lo)) & (F.col("service_date") <= F.lit(hi)))
             .orderBy(order).limit(CASES))

    labels = record.get("labels")
    if (model_dir / "preprocessing").exists() and (model_dir / "classifier").exists():
        import importlib
        prep = PipelineModel.load(local(model_dir / "preprocessing"))
        meta = json.loads(next((model_dir / "classifier" / "metadata").glob("part-00000*")).read_text())
        # metadata names the Scala class; PySpark exposes it under the same simple name
        klass = meta["class"].rsplit(".", 1)[1]
        classifier = getattr(importlib.import_module("pyspark.ml.classification"), klass).load(local(model_dir / "classifier"))
        pred = classifier.transform(prep.transform(cases))
        if labels is None and task == "delay_severity":
            from pyspark.ml.feature import StringIndexerModel
            labels = next((list(st.labels) for st in prep.stages if isinstance(st, StringIndexerModel)
                           and st.isSet("inputCol") and st.getInputCol() == target), None)
    else:
        pred = PipelineModel.load(local(model_dir)).transform(cases)

    keys = TASKS[task]["keys"]
    if task == "daily_boardings":
        out = pred.select(*keys, F.col(target).cast("double").alias("spark_actual"),
                          F.col("prediction").alias("spark_prediction")).toPandas()
        out["service_date"] = pd.to_datetime(out.service_date).dt.strftime("%Y-%m-%d")
        spark.stop()
        return out

    pred = pred.withColumn("proba", vector_to_array("probability"))
    out = pred.select(*keys, F.col(target).cast("string").alias("spark_actual"), "prediction", "proba").toPandas()
    spark.stop()
    proba = np.vstack(out.pop("proba").to_numpy())
    if task == "crowding_flag":
        threshold = record.get("threshold")
        index = out.pop("prediction").astype(float)
        hit = proba[:, 1] >= threshold if threshold is not None else index == 1.0
        out["spark_prediction"] = np.where(hit, "1.0", "0.0")
        out["spark_probability"] = proba[:, 1].round(6)
        out["spark_actual"] = out.spark_actual.map(lambda v: str(float(v == "true" or v == "1.0" or v == "1")))
    else:
        if not labels:
            raise RuntimeError(f"{task}: cannot map Spark label indices to class names for {spark_sel['name']}")
        out["spark_prediction"] = out.pop("prediction").map(lambda i: labels[int(i)])
        out["spark_probability"] = proba.max(1).round(6)
    return out


# ---------------------------------------------------------------- comparison

def compare(task: str, sdf: pd.DataFrame, pdf: pd.DataFrame) -> pd.DataFrame:
    keys = TASKS[task]["keys"]
    merged = sdf.merge(pdf, on=keys, how="inner")
    df = pd.DataFrame({"case_id": merged[keys].astype(str).agg("_".join, axis=1),
                       "actual": merged.python_actual, "spark_actual": merged.spark_actual,
                       "spark_prediction": merged.spark_prediction, "python_prediction": merged.python_prediction})
    if TASKS[task]["kind"] == "regression":
        s, p = merged.spark_prediction.astype(float), merged.python_prediction.astype(float)
        sa, pa = merged.spark_actual.astype(float), merged.python_actual.astype(float)
        df["spark_value"], df["python_value"] = s.round(3), p.round(3)
        df["spark_probability"] = df["python_probability"] = ""
        df["absolute_difference"] = (s - p).abs().round(3)
        df["match"] = (s - p).abs() / p.abs().clip(lower=1e-9) <= TOLERANCE
        spark_err, py_err = (s - sa).abs() / sa.abs().clip(lower=1e-9), (p - pa).abs() / pa.abs().clip(lower=1e-9)
        spark_ok, py_ok = spark_err <= TOLERANCE, py_err <= TOLERANCE
        detail = [f"Spark off by {a:.1%}, Python off by {b:.1%} of their actuals" for a, b in zip(spark_err, py_err)]
    else:
        df["spark_value"] = df["python_value"] = ""
        df["spark_probability"], df["python_probability"] = merged.spark_probability, merged.python_probability
        df["absolute_difference"] = ""
        df["match"] = merged.spark_prediction == merged.python_prediction
        spark_ok = merged.spark_prediction == merged.spark_actual
        py_ok = merged.python_prediction == merged.python_actual
        detail = [f"actual {a}: Spark {s}, Python {p}" for a, s, p in
                  zip(merged.python_actual, merged.spark_prediction, merged.python_prediction)]
    df["agreement_status"] = np.select([spark_ok & py_ok, spark_ok, py_ok],
                                       ["BothCorrect", "SparkOnlyCorrect", "PyOnlyCorrect"], "BothWrong")
    df["disagreement_explanation"] = np.where(df.match, "Pipelines agree.", detail)
    return df[OUT_COLUMNS]


def case_scores(task: str, df: pd.DataFrame) -> dict:
    """Each pipeline scored on the compared cases against its own pipeline's actual value."""
    if TASKS[task]["kind"] == "regression":
        return {"spark": mean_absolute_error(df.spark_actual.astype(float), df.spark_value.astype(float)),
                "python": mean_absolute_error(df.actual.astype(float), df.python_value.astype(float))}
    return {pipe: {"accuracy": accuracy_score(actual, df[f"{pipe}_prediction"]),
                   "macro_f1": f1_score(actual, df[f"{pipe}_prediction"], average="macro", zero_division=0)}
            for pipe, actual in (("spark", df.spark_actual), ("python", df.actual))}


def summary(df: pd.DataFrame) -> dict:
    shares = df.agreement_status.value_counts(normalize=True)
    return {"cases": len(df), "agree": df.match.mean(),
            **{k: shares.get(k, 0.0) for k in ("BothCorrect", "SparkOnlyCorrect", "PyOnlyCorrect", "BothWrong")}}


def clustering() -> dict:
    """Task D: silhouettes come from the metrics JSONs; agreement is the adjusted Rand index."""
    py = python_model("route_clustering")
    candidates = [(read_json(p), p.stem[len("route_clustering_"):]) for p in (SPARK_MODELS / "metrics").glob("route_clustering_*.json")]
    candidates = [(r["silhouette"], name) for r, name in candidates if "silhouette" in r and spark_model_dir("route_clustering", name)]
    spark_silhouette, spark_name = max(candidates)
    out = {"python": py["algorithm"], "python_silhouette": py["record"]["silhouette"],
           "spark": spark_name, "spark_silhouette": spark_silhouette, "ari": None, "crosstab": None, "routes": 0}
    spark_file = SAMPLES_SPARK / f"route_clustering_{spark_name}.csv"
    if spark_file.exists():
        import joblib
        from database.evaluate_saved_models import route_profiles
        # The saved model's labels_ follow route_profiles order (as database/load_model_outputs.py).
        labels = joblib.load(PY_MODELS / "route_clustering" / f"{py['algorithm']}_{py['version']}.pkl").labels_
        p = route_profiles(python_trip_frame())[["route_id"]].assign(python_cluster=labels)
        d = pd.read_csv(spark_file).merge(p, on="route_id")
        out.update(routes=len(d), ari=adjusted_rand_score(d.predicted_cluster, d.python_cluster),
                   crosstab=pd.crosstab(d.predicted_cluster, d.python_cluster,
                                        rownames=["Spark cluster"], colnames=["Python cluster"]).to_string())
    return out


def features_of(record: dict) -> str:
    if "numeric_features" in record:
        feats = record["numeric_features"] + record.get("categorical_features", [])
    elif isinstance(record.get("features"), dict):
        feats = record["features"]["numeric"] + record["features"]["categorical"]
    else:
        feats = record.get("features") or []
    return ", ".join(f"`{f}`" for f in feats) or "not recorded in its metrics JSON"


def run() -> None:
    COMPARISON_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for task, spec in TASKS.items():
        py, spark_sel = python_model(task), spark_model(task)
        result = {"python": py, "spark": spark_sel}
        if spark_sel["name"] is None:
            logger.warning("%s: no leakage-free Spark model with saved files; not compared", task)
            pd.DataFrame(columns=OUT_COLUMNS).to_csv(COMPARISON_DIR / spec["out"], index=False)
            results[task] = result
            continue
        lo, hi = case_window(py, spark_sel)
        df = compare(task, spark_predictions(task, spark_sel, lo, hi), python_predictions(task, py, lo, hi))
        if len(df) < MIN_CASES:
            raise RuntimeError(f"{task}: only {len(df)} matched cases; SRS requires at least {MIN_CASES}")
        df.to_csv(COMPARISON_DIR / spec["out"], index=False)
        result.update(window=(lo, hi), cases=df, scores=case_scores(task, df), summary=summary(df))
        results[task] = result
        logger.info("%s: %d cases, agreement %.1f%%", task, len(df), 100 * df.match.mean())
    REPORT.write_text(report(results, clustering()), encoding="utf-8")
    logger.info("Wrote %s", REPORT)


# ---------------------------------------------------------------- report

def report(results: dict, clusters: dict) -> str:
    lines = ["# Dual-Pipeline Comparison Report", "",
             f"Generated {date.today().isoformat()} by `python_pipeline/phase8_comparison.py`. Every figure below "
             "is read from a saved metrics JSON or computed from the compared cases.", "",
             "- **Python model:** the one `config/serving.yaml` serves.",
             "- **Spark model:** the saved, leakage-free MLlib model with the best validation score "
             "(test scores never choose a model).",
             "- **Cases:** dates inside both pipelines' test splits, so neither pipeline trained on them or used them "
             "to choose a model.",
             f"- **Regression agreement:** predictions within {TOLERANCE:.0%} of each other; a prediction is "
             f"correct when it is within {TOLERANCE:.0%} of the actual value.", "",
             "## Per-task summary", "",
             "| Task | Cases | Spark model | Python model | Spark score (cases) | Python score (cases) "
             "| Spark full test | Python full test | Agreement | Both correct | Spark only | Python only | Both wrong |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    compared = []
    for task, r in results.items():
        spec, py = TASKS[task], r["python"]
        py_name = f"{py['algorithm']} {py['version']}"
        py_test = py["record"]["test"].get(spec["metric"])
        if r["spark"]["name"] is None:
            lines.append(f"| {spec['name']} | 0 | none eligible | {py_name} | - | - | - | {fmt(py_test)} | - | - | - | - | - |")
            continue
        compared.append(task)
        s, sc, rec = r["summary"], r["scores"], r["spark"]["record"]
        spark_test = (spark_scores(rec, "test") or {}).get(spec["metric"])
        if spec["kind"] == "regression":
            case_s, case_p = f"MAE {sc['spark']:.2f}", f"MAE {sc['python']:.2f}"
            full_s, full_p = f"MAE {fmt(spark_test, 2)}", f"MAE {fmt(py_test, 2)}"
        else:
            case_s = f"acc {sc['spark']['accuracy']:.3f} / F1 {sc['spark']['macro_f1']:.3f}"
            case_p = f"acc {sc['python']['accuracy']:.3f} / F1 {sc['python']['macro_f1']:.3f}"
            full_s, full_p = f"F1 {fmt(spark_test, 3)}", f"F1 {fmt(py_test, 3)}"
        lines.append(f"| {spec['name']} | {s['cases']} | {r['spark']['name']} | {py_name} | {case_s} | {case_p} | "
                     f"{full_s} | {full_p} | {s['agree']:.1%} | {s['BothCorrect']:.1%} | {s['SparkOnlyCorrect']:.1%} | "
                     f"{s['PyOnlyCorrect']:.1%} | {s['BothWrong']:.1%} |")

    for task, r in results.items():
        spec, py, sel = TASKS[task], r["python"], r["spark"]
        lines += ["", f"## {spec['name']}", "", f"- **Python inputs:** {features_of(py['record'])}"]
        if sel["name"] is None:
            lines += ["- **Not compared:** no saved Spark model qualifies. Candidates rejected:"]
            lines += [f"  - `{name}`: {reason}" for name, reason in sel["rejected"]]
            continue
        df = r["cases"]
        lines += [f"- **Spark inputs:** {features_of(sel['record'])}",
                  f"- **Case window:** {r['window'][0]} to {r['window'][1]}"]
        if scope := sel["record"].get("model_scope"):
            lines.append(f"- **Spark training scope (from its JSON):** {scope}")
        if sel["rejected"]:
            lines.append("- **Spark candidates not used:** " +
                         "; ".join(f"`{name}` ({reason})" for name, reason in sel["rejected"]))
        if spec["kind"] == "classification":
            differ = int((df.actual.astype(str) != df.spark_actual.astype(str)).sum())
            if differ:
                lines.append(f"- **Note:** the two pipelines' actual labels differ on {differ} cases; "
                             "each pipeline is scored against its own actual.")
            lines += ["", "Examples of disagreement:", "", "```csv",
                      df[~df.match].head(5)[["case_id", "actual", "spark_prediction", "python_prediction"]].to_csv(index=False).rstrip(),
                      "```"]
        else:
            lines += ["", "Cases with the largest difference:", "", "```csv",
                      df.sort_values("absolute_difference", ascending=False).head(5)
                      [["case_id", "actual", "spark_value", "python_value", "absolute_difference"]].to_csv(index=False).rstrip(),
                      "```"]

    lines += ["", "## Task D (route clustering)", "",
              f"- **Spark:** {clusters['spark']}, silhouette {clusters['spark_silhouette']:.3f}",
              f"- **Python:** {clusters['python']}, silhouette {clusters['python_silhouette']:.3f}"]
    if clusters["ari"] is not None:
        lines += [f"- **Agreement (adjusted Rand index over {clusters['routes']} routes):** {clusters['ari']:.3f} "
                  "(1 = identical grouping, 0 = no better than chance)", "", "```", clusters["crosstab"], "```"]
    else:
        lines.append("- **Agreement:** not computed; a per-route cluster file is missing for one pipeline.")

    if compared:
        total = sum(results[t]["summary"]["cases"] for t in compared)
        agree = sum(results[t]["summary"]["agree"] * results[t]["summary"]["cases"] for t in compared) / total
        lines += ["", "## Overall", "", f"- **Case-weighted agreement over {total} cases "
                  f"({', '.join(TASKS[t]['name'] for t in compared)}):** {agree:.1%}"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    run()
