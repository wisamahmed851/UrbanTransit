"""Load locally staged clean Parquet reference/network tables into the app database.

Use this on Windows/XAMPP when the full HDFS stack is not running. The source is the
pristine Parquet written by ``data_generator.generate --clean-out``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, func, select

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.app import create_app  # noqa: E402
from src.extensions import db  # noqa: E402
from src.models.network import RouteStop  # noqa: E402
from src.models.reference import Route, Stop, Vehicle  # noqa: E402


TABLES = ((Stop, "stops"), (Vehicle, "vehicles"), (Route, "routes"), (RouteStop, "route_stops"))


def records(folder: Path, model) -> list[dict]:
    frame = pd.read_parquet(folder)
    columns = [column.name for column in model.__table__.columns]
    if "dq_flags" in columns and "dq_flags" not in frame:
        frame["dq_flags"] = [[] for _ in range(len(frame))]
    missing = [column for column in columns if column not in frame]
    if missing:
        raise ValueError(f"{model.__tablename__}: staged Parquet is missing {missing}")
    frame = frame[columns].copy()
    for column in model.__table__.columns:
        if column.name not in frame:
            continue
        if column.type.python_type.__name__ == "date":
            frame[column.name] = pd.to_datetime(frame[column.name]).dt.date
    frame = frame.astype(object).where(pd.notna(frame), None)
    return frame.to_dict("records")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "python_pipeline" / "local_clean")
    parser.add_argument("--batch-size", type=int, default=5000)
    args = parser.parse_args()
    rows = {model: records(args.source / name, model) for model, name in TABLES}

    app = create_app()
    with app.app_context(), db.engine.begin() as conn:
        for model, _ in reversed(TABLES):
            conn.execute(delete(model.__table__))
        for model, _ in TABLES:
            values = rows[model]
            for start in range(0, len(values), args.batch_size):
                conn.execute(model.__table__.insert(), values[start:start + args.batch_size])

    with app.app_context(), db.engine.connect() as conn:
        counts = {
            model.__tablename__: conn.execute(select(func.count()).select_from(model.__table__)).scalar_one()
            for model, _ in TABLES
        }
    for name, count in counts.items():
        print(f"{count:7,d}  {name}")
    print("LOCAL_REFERENCE_LOAD: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
