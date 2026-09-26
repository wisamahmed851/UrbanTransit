"""Load the committed Phase 6 evidence into MySQL: model_metrics and cluster_profiles.

    python database/load_model_metrics.py        # inside WSL, venv active (no Spark needed)

* `models/spark/metrics/*.json` -> `model_metrics`, flattened by `metrics_normaliser.py`.
* `reports/phase6_cluster_profiles.csv` -> `cluster_profiles` (one row per K-Means cluster).

Both tables are replaced in one transaction. These files are read only; they belong to
the Phase 6 work and are not modified. Results go to `reports/model_metrics_load_report.json`.
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, select  # noqa: E402

from database.metrics_normaliser import normalise  # noqa: E402
from src.app import create_app  # noqa: E402
from src.extensions import db  # noqa: E402
from src.models.ml import ClusterProfile, ModelMetric  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
METRICS_DIR = ROOT / "models" / "spark" / "metrics"
CLUSTER_CSV = ROOT / "reports" / "phase6_cluster_profiles.csv"
REPORT_PATH = ROOT / "reports" / "model_metrics_load_report.json"


def read_metric_rows() -> tuple[list[dict], dict[str, int]]:
    rows, per_file = [], {}
    for path in sorted(METRICS_DIR.glob("*.json")):
        file_rows = normalise(path.name, json.loads(path.read_text(encoding="utf-8")))
        per_file[path.name] = len(file_rows)
        rows += file_rows
    return rows, per_file


def read_cluster_rows() -> list[dict]:
    """CSV values are text; convert them to the column types (int for ids/counts, float otherwise)."""
    ints = {"prediction", "routes"}
    with CLUSTER_CSV.open(encoding="utf-8", newline="") as f:
        return [{k: (int(v) if k in ints else v if k == "plain_language_label" else float(v)) for k, v in r.items()}
                for r in csv.DictReader(f)]


def main() -> int:
    metric_rows, per_file = read_metric_rows()
    cluster_rows = read_cluster_rows()
    app = create_app()
    with app.app_context():
        with db.engine.begin() as conn:
            conn.execute(delete(ModelMetric.__table__))
            conn.execute(ModelMetric.__table__.insert(), metric_rows)
            conn.execute(delete(ClusterProfile.__table__))
            conn.execute(ClusterProfile.__table__.insert(), cluster_rows)
        with db.engine.connect() as conn:
            n_metrics = conn.execute(select(func.count()).select_from(ModelMetric.__table__)).scalar_one()
            n_clusters = conn.execute(select(func.count()).select_from(ClusterProfile.__table__)).scalar_one()

    report = {
        "metric_files": len(per_file),
        "model_metrics_rows": n_metrics,
        "rows_per_file": per_file,
        "rows_per_task": dict(Counter(r["task"] for r in metric_rows)),
        "rows_per_split_type": dict(Counter(r["split_type"] for r in metric_rows)),
        "invalid_rows": sum(r["validity_flag"] == "INVALID" for r in metric_rows),
        "cluster_profiles_rows": n_clusters,
        "result": "PASS" if n_metrics == len(metric_rows) and n_clusters == len(cluster_rows) else "FAIL",
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name, n in per_file.items():
        print(f"{n:5d}  {name}")
    print(f"model_metrics: {n_metrics} rows from {len(per_file)} files "
          f"({report['invalid_rows']} flagged INVALID); cluster_profiles: {n_clusters} rows -> {report['result']}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
