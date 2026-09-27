"""Flatten the metric JSON files into `model_metrics` rows.

* `normalise`: Phase 6 Spark files (models/spark/metrics/*.json), several layouts, below.
* `normalise_python`: Phase 7 Python files (models/python/metrics/*.json), one layout.

The files come in several layouts (see documentation/backend_api.md, "Model metrics"):

| layout                         | where the numbers are                                          |
|--------------------------------|----------------------------------------------------------------|
| main Spark runs                | `metrics.{train,validation,test}` (+ `validation_tuning`)       |
| 10% sample runs                | `metrics.{validation_sample,test_full}`                        |
| full-data weighted retrains    | `metrics.{train,validation,test}` with `per_class_f1`, confusion matrix |
| XGBoost                        | `metrics.test` + `validation_selection`                        |
| demand baseline                | `metrics.{validation,test}`                                     |
| clustering                     | top-level `silhouette`, or `status` + `actual_clusters` when degenerate |
| all with trials                | `validation_trials[i].validation`                               |

Every single number becomes one row: (split_type, metric_name, metric_value). Anything
that is not a single number (row counts, k, split dates, feature lists, params, confusion
matrices, ...) goes into `extra_json`, so nothing in a file is dropped. Metric names are
kept as the files write them (`weighted_f1` and `macro_f1` stay different metrics).
"""

from numbers import Number

# Keys that are handled explicitly; every other top-level key is copied into extra_json.
HANDLED_KEYS = {"task", "algorithm", "metrics", "validation_trials", "validation_tuning",
                "validation_selection", "silhouette", "actual_clusters", "rows"}

LEAKAGE_NOTE = ("occupancy_pct, a same-trip outcome, is a model input (leakage); "
                "not valid for serving until retrained without it")


def spark_validity(data: dict) -> tuple[str | None, str | None]:
    """Flag only Spark delay runs whose recorded feature vector leaks occupancy.

    Historical artifact layouts without an explicit feature list are conservatively
    retained as invalid. A new retrain is valid only when it records its numeric
    features and demonstrably excludes `occupancy_pct`.
    """
    if data.get("task") != "delay_severity":
        return None, None
    numeric = data.get("numeric_features")
    if not isinstance(numeric, list) or "occupancy_pct" in numeric:
        return "INVALID", LEAKAGE_NOTE
    return None, None


def _is_number(value) -> bool:
    return isinstance(value, Number) and not isinstance(value, bool)


def _flatten_block(block: dict) -> tuple[list[tuple[str, float]], dict]:
    """Split one metrics block into [(metric_name, value)] and the non-numeric rest."""
    metrics, rest = [], {}
    for key, value in block.items():
        if key == "rows":
            rest["rows"] = value
        elif _is_number(value):
            metrics.append((key, float(value)))
        elif key == "per_class_f1" and isinstance(value, dict):
            metrics += [(f"per_class_f1[{label}]", float(v)) for label, v in value.items()]
        else:
            rest[key] = value
    return metrics, rest


def normalise(file_name: str, data: dict) -> list[dict]:
    """Return the flat model_metrics rows for one metric file."""
    task, algorithm = data["task"], data["algorithm"]
    file_extra = {k: v for k, v in data.items() if k not in HANDLED_KEYS}
    file_rows = data.get("rows") if isinstance(data.get("rows"), dict) else {}
    flag, note = spark_validity(data)

    def make(split_type: str, name: str, value, extra: dict) -> dict:
        return {
            "pipeline": "spark", "source_file": file_name, "task": task, "algorithm": algorithm,
            "split_type": split_type, "metric_name": name, "metric_value": value,
            "extra_json": {**file_extra, **extra}, "validity_flag": flag, "validity_note": note,
        }

    out = []
    for split, block in (data.get("metrics") or {}).items():
        metrics, rest = _flatten_block(block)
        if "rows" not in rest and split in file_rows:
            rest["rows"] = file_rows[split]
        out += [make(split, name, value, rest) for name, value in metrics]

    for key in ("validation_tuning", "validation_selection"):
        if isinstance(data.get(key), dict):
            metrics, rest = _flatten_block(data[key])
            out += [make(key, name, value, rest) for name, value in metrics]

    for i, trial in enumerate(data.get("validation_trials") or []):
        metrics, rest = _flatten_block(trial.get("validation") or {})
        trial_extra = {"trial_index": i, **{k: v for k, v in trial.items() if k != "validation"}, **rest}
        out += [make("validation_trial", name, value, trial_extra) for name, value in metrics]

    # Clustering: fitted on the train-period route profiles only (Phase 6 Task D).
    if _is_number(data.get("silhouette")):
        out.append(make("train", "silhouette", float(data["silhouette"]), {}))
    if _is_number(data.get("actual_clusters")):
        out.append(make("train", "actual_clusters", float(data["actual_clusters"]), {}))

    if not out:
        raise ValueError(f"{file_name}: no numeric metric found; the layout is not recognised")
    return out


# Phase 7 top-level keys that hold a metrics block, and the split_type each becomes.
PYTHON_BLOCKS = {"validation": "validation", "test": "test", "test_default_threshold": "test_default_threshold"}


def normalise_python(file_name: str, data: dict) -> list[dict]:
    """Rows for one Phase 7 file: `{validation, test}` blocks (classifiers, regressors) or
    `silhouette` + `clusters` (clustering). `test_default_threshold` is the crowding model
    scored at 0.5 instead of its tuned threshold.

    No validity flag is raised: the Phase 7 delay model's inputs exclude `occupancy_pct`
    (`run_classification` removes it), so the Spark leakage finding does not apply.
    """
    task, algorithm = data["task"], data["algorithm"]
    file_extra = {k: v for k, v in data.items() if k not in PYTHON_BLOCKS and k not in {"task", "algorithm", "silhouette", "clusters"}}

    def make(split_type: str, name: str, value, extra: dict) -> dict:
        return {
            "pipeline": "python", "source_file": file_name, "task": task, "algorithm": algorithm,
            "split_type": split_type, "metric_name": name, "metric_value": value,
            "extra_json": {**file_extra, **extra}, "validity_flag": None, "validity_note": None,
        }

    out = []
    for key, split in PYTHON_BLOCKS.items():
        if isinstance(data.get(key), dict):
            metrics, rest = _flatten_block(data[key])
            out += [make(split, name, value, rest) for name, value in metrics]
    if _is_number(data.get("silhouette")):
        out.append(make("train", "silhouette", float(data["silhouette"]), {}))
    if _is_number(data.get("clusters")):
        out.append(make("train", "clusters", float(data["clusters"]), {}))
    if not out:
        raise ValueError(f"{file_name}: no numeric metric found; the layout is not recognised")
    return out
