"""Serves generated Phase 9 recommendations and Phase 7/8 comparison evidence.

These are immutable pipeline artifacts, not hand-authored dashboard values.  MySQL
backs authentication, roles, analytics and model metrics; artifact endpoints retain
the exact recommendation evidence generated from HDFS analytics.
"""
import csv
import json
from pathlib import Path

from flask import Blueprint, jsonify

from src.security import permission_required

bp = Blueprint("operational", __name__, url_prefix="/api")
ROOT = Path(__file__).resolve().parents[2]


@bp.get("/recommendations")
@permission_required("recommendations:read")
def recommendations():
    rows = json.loads((ROOT / "reports" / "recommendations.json").read_text(encoding="utf-8"))
    return jsonify(total=len(rows), rows=rows, source="reports/recommendations.json")


@bp.get("/models/comparison")
@permission_required("models:read")
def comparison():
    directory = ROOT / "reports" / "comparison"
    tables = {}
    for path in sorted(directory.glob("*.csv")):
        with path.open(encoding="utf-8", newline="") as stream:
            tables[path.stem] = list(csv.DictReader(stream))
    return jsonify(tables=tables, source="reports/comparison/*.csv")
