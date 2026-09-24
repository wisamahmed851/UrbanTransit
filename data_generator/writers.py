"""Write tables to disk in the documented column order and formats (CSV, JSON, JSON Lines)."""

import json
from pathlib import Path

import pandas as pd

from .schema_registry import column_names


def _prepare(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Order columns as in documentation/schemas/<table>.json and write booleans as true/false."""
    cols = column_names(table)
    missing = set(cols) - set(df.columns)
    if missing:
        raise ValueError(f"{table}: generator did not produce columns {sorted(missing)}")
    out = df[cols].copy()
    for c in out.columns:
        if out[c].dtype == bool:
            out[c] = out[c].map({True: "true", False: "false"})
    return out


def write_csv(df: pd.DataFrame, path: Path, table: str) -> int:
    """Write one CSV file with a header row; returns the number of data rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _prepare(df, table).to_csv(path, index=False)
    return len(df)


def write_json(records: list, path: Path) -> int:
    """Write a JSON array (used for the nested service calendar)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    return len(records)


def write_jsonl(df: pd.DataFrame, path: Path, table: str) -> int:
    """Write JSON Lines: one JSON object per line (used for GPS events)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _prepare(df, table).to_json(path, orient="records", lines=True, force_ascii=False)
    return len(df)
