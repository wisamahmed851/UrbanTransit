"""Validate admin edits to routes/stops/vehicles against the Phase 1 contract.

The rules come from `documentation/schemas/<table>.json`, the same files the data
generator and Spark schemas follow, so the API cannot accept a row the pipeline would
reject:

* required columns: `"nullable": false`
* types: string / double / integer / date / boolean
* allowed values: a description written as `a | b | c` (e.g. route_type `brt | trunk | local | feeder`)
* string length: the MySQL column length

`dq_flags` is not editable through the API; it records Phase 3 findings.
Laravel analogy: a FormRequest whose rules() are generated from a schema file.
"""

import json
import re
from datetime import date
from pathlib import Path

from src.errors import ApiError

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "documentation" / "schemas"
ENUM_PATTERN = re.compile(r"^[a-z_]+(?: \| [a-z_]+)+$")
READ_ONLY = {"dq_flags"}


def load_contract(table: str) -> dict[str, dict]:
    """{column: {"type", "nullable", "enum"}} for one Phase 1 table."""
    spec = json.loads((SCHEMA_DIR / f"{table}.json").read_text(encoding="utf-8"))
    out = {}
    for col in spec["columns"]:
        desc = col.get("description", "").strip()
        out[col["name"]] = {
            "type": col["type"],
            "nullable": col["nullable"],
            "enum": desc.split(" | ") if ENUM_PATTERN.match(desc) else None,
        }
    return out


CONTRACTS = {t: load_contract(t) for t in ("routes", "stops", "vehicles")}


def _coerce(column: str, rule: dict, value, max_length: int | None):
    kind = rule["type"]
    if kind == "string":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty string")
        if max_length and len(value) > max_length:
            raise ValueError(f"must be at most {max_length} characters")
        if rule["enum"] and value not in rule["enum"]:
            raise ValueError(f"must be one of {rule['enum']}")
        return value
    if kind == "double":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("must be a number")
        return float(value)
    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("must be an integer")
        return value
    if kind == "date":
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValueError("must be a date in YYYY-MM-DD format") from None
    if kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError("must be true or false")
        return value
    raise ValueError(f"unsupported type {kind}")


def validate(table: str, model, body: dict, partial: bool) -> dict:
    """Return clean column values from a JSON body; 400 with every problem listed otherwise.

    `partial=True` (PATCH) only validates the keys present; the primary key cannot change.
    """
    contract = CONTRACTS[table]
    pk = model.__mapper__.primary_key[0].name
    errors = {}
    unknown = [k for k in body if k not in contract]
    for key in unknown:
        errors[key] = "read-only column" if key in READ_ONLY else "unknown column"
    if partial and pk in body:
        errors[pk] = "the primary key cannot be changed"

    clean = {}
    for column, rule in contract.items():
        if column not in body:
            if not partial and not rule["nullable"]:
                errors[column] = "is required"
            continue
        if partial and column == pk:
            continue
        value = body[column]
        if value is None:
            if not rule["nullable"]:
                errors[column] = "cannot be null"
            continue
        try:
            clean[column] = _coerce(column, rule, value, getattr(model.__table__.c[column].type, "length", None))
        except ValueError as err:
            errors[column] = str(err)

    if errors:
        raise ApiError(400, "validation_failed", f"Invalid {table} data.", {"fields": errors})
    return clean
