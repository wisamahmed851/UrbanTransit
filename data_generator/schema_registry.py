"""Schema registry: one place that reads the table definitions in documentation/schemas/.

The JSON files in documentation/schemas/ are the single source of truth for the
12 tables (columns, types, primary keys, foreign keys). Everything else reads them:

* the data generator uses them to write columns in the documented order,
* validate_dataset.py uses the PK/FK definitions,
* spark_jobs/schemas.py is checked against them,
* this module renders documentation/data_dictionary.md and documentation/erd.md.

Laravel analogy: the JSON files play the role of your migrations - the one
definition of each table - and this module is a tiny "schema builder" that other
code asks for column lists instead of hard-coding them.

Run `python data_generator/schema_registry.py` to regenerate the two docs.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = PROJECT_ROOT / "documentation" / "schemas"

# Canonical order: reference (dimension) tables first, then event (fact) tables.
TABLE_ORDER = [
    "stops", "routes", "route_stops", "service_calendar", "schedules", "vehicles",
    "passengers", "trips", "passenger_counts", "tickets", "delays", "gps_events",
]


def load_schema(table: str) -> dict:
    """Return the parsed JSON schema for one table."""
    with open(SCHEMA_DIR / f"{table}.json", encoding="utf-8") as f:
        return json.load(f)


def load_schemas() -> dict[str, dict]:
    """Return {table_name: schema} for all 12 tables, in TABLE_ORDER."""
    return {t: load_schema(t) for t in TABLE_ORDER}


def column_names(table: str) -> list[str]:
    """Column names of a table, in the documented order (used for CSV headers)."""
    return [c["name"] for c in load_schema(table)["columns"]]


# ---------------------------------------------------------------------------
# Documentation renderers
# ---------------------------------------------------------------------------

def render_data_dictionary(schemas: dict[str, dict]) -> str:
    """Build documentation/data_dictionary.md as Markdown text."""
    lines = [
        "# Data Dictionary - UrbanTransit IQ",
        "",
        "_Generated from `documentation/schemas/*.json` by `data_generator/schema_registry.py`. "
        "Do not edit by hand: change the JSON schema and regenerate._",
        "",
        "Timestamps are local transit time (Asia/Karachi, UTC+05:00) written as "
        "`YYYY-MM-DD HH:MM:SS` without a zone suffix. Dates are `YYYY-MM-DD`.",
        "",
        "| Table | Format | Primary key | Description |",
        "|---|---|---|---|",
    ]
    for name, s in schemas.items():
        lines.append(f"| [{name}](#{name}) | {s['file_format']} | {', '.join(s['primary_key'])} | {s['description']} |")
    for name, s in schemas.items():
        lines += ["", f"## {name}", "", s["description"], "",
                  f"- **File layout:** `raw_data/<mode>/{s['file_layout']}`",
                  f"- **Primary key:** `{', '.join(s['primary_key'])}`"]
        if s["foreign_keys"]:
            fks = "; ".join(
                f"`{', '.join(fk['columns'])}` -> `{fk['references']['table']}.{', '.join(fk['references']['columns'])}`"
                for fk in s["foreign_keys"])
            lines.append(f"- **Foreign keys:** {fks}")
        lines += ["", "| Column | Type | Nullable | Key | Description |", "|---|---|---|---|---|"]
        fk_cols = {c for fk in s["foreign_keys"] for c in fk["columns"]}
        for c in s["columns"]:
            key = "PK" if c["name"] in s["primary_key"] else ""
            if c["name"] in fk_cols:
                key = (key + " FK").strip()
            ctype = c["type"].replace("|", "/")
            lines.append(f"| {c['name']} | `{ctype}` | {'yes' if c['nullable'] else 'no'} | {key} | {c['description']} |")
    return "\n".join(lines) + "\n"


def _mermaid_type(t: str) -> str:
    """Mermaid ER diagrams only accept simple type words."""
    return "array" if t.startswith("array") else t


def render_erd(schemas: dict[str, dict]) -> str:
    """Build documentation/erd.md with a Mermaid entity-relationship diagram."""
    lines = [
        "# Entity-Relationship Diagram - UrbanTransit IQ",
        "",
        "_Generated from the PK/FK definitions in `documentation/schemas/*.json`._",
        "",
        "Reading guide: `||--o{` means *one* row on the left relates to *zero or more* rows on the right "
        "(Laravel: `hasMany` / `belongsTo`).",
        "",
        "```mermaid",
        "erDiagram",
    ]
    # Relationships: parent ||--o{ child : "fk column"
    for child, s in schemas.items():
        for fk in s["foreign_keys"]:
            parent = fk["references"]["table"]
            lines.append(f'    {parent.upper()} ||--o{{ {child.upper()} : "{", ".join(fk["columns"])}"')
    # Entities with columns
    for name, s in schemas.items():
        fk_cols = {c for fk in s["foreign_keys"] for c in fk["columns"]}
        lines.append(f"    {name.upper()} {{")
        for c in s["columns"]:
            marks = []
            if c["name"] in s["primary_key"]:
                marks.append("PK")
            if c["name"] in fk_cols:
                marks.append("FK")
            lines.append(f"        {_mermaid_type(c['type'])} {c['name']} {','.join(marks)}".rstrip())
        lines.append("    }")
    lines += ["```", "",
              "## How the tables fit together", "",
              "- **Network (reference) tables:** `stops`, `routes`, `route_stops` (ordered stops per route and direction), "
              "`vehicles`, `passengers`.",
              "- **Planning tables:** `service_calendar` (which days a timetable runs) and `schedules` "
              "(headways and planned running times per route, direction, service and period).",
              "- **Operations (event) tables:** `trips` (each planned journey, with scheduled vs actual times and vehicle), "
              "and four tables derived from the same trip simulation: `passenger_counts` (APC loads), `tickets` "
              "(card tap-in/tap-out), `delays` (stop-level deviations with reasons) and `gps_events` (vehicle positions).",
              ""]
    return "\n".join(lines)


def main() -> None:
    schemas = load_schemas()
    (PROJECT_ROOT / "documentation" / "data_dictionary.md").write_text(render_data_dictionary(schemas), encoding="utf-8")
    (PROJECT_ROOT / "documentation" / "erd.md").write_text(render_erd(schemas), encoding="utf-8")
    n_cols = sum(len(s["columns"]) for s in schemas.values())
    n_fks = sum(len(s["foreign_keys"]) for s in schemas.values())
    print(f"Rendered data_dictionary.md and erd.md: {len(schemas)} tables, {n_cols} columns, {n_fks} foreign keys")


if __name__ == "__main__":
    main()
