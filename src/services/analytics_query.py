"""Filtering, sorting and paging for the analytics tables, shared by JSON and CSV endpoints.

Supported query parameters (each only on tables that have the column):

| parameter              | column(s)                                                    |
|------------------------|--------------------------------------------------------------|
| route_id               | route_id                                                     |
| stop_id                | stop_id, or origin_stop_id OR destination_stop_id (O-D tables) |
| direction              | direction (0 or 1)                                           |
| day_class              | day_class (weekday / weekend / holiday)                      |
| time_period            | time_period (early_morning ... evening)                      |
| date_from, date_to     | service_date, inclusive, YYYY-MM-DD                          |
| sort                   | comma-separated columns, `-` prefix for descending          |
| limit, offset          | paging (JSON only; CSV exports every matching row)          |

A filter the table cannot honour is a 400 error, never silently ignored, so a caller
cannot mistake an unfiltered result for a filtered one.
"""

from datetime import date
from decimal import Decimal

from flask import current_app, request
from sqlalchemy import Select, Table, func, or_, select

from src.errors import ApiError
from src.models.analytics import ANALYTICS_SCHEMAS, ANALYTICS_TABLES
from src.services.requests import int_arg

VALUE_FILTERS = ("route_id", "stop_id", "direction", "day_class", "time_period")
DATE_FILTERS = ("date_from", "date_to")
DATE_COLUMN = "service_date"


def get_table(name: str) -> Table:
    if name not in ANALYTICS_TABLES:
        raise ApiError(404, "unknown_table", f"No analytics table '{name}'.", {"available": sorted(ANALYTICS_TABLES)})
    return ANALYTICS_TABLES[name]


def data_columns(table: Table) -> list:
    """Every column except the surrogate `id`, in Parquet order."""
    return [c for c in table.columns if c.name != "id"]


def filter_columns(table: Table, param: str) -> list[str]:
    """Which columns a filter parameter maps to on this table (empty = not supported)."""
    names = set(table.c.keys())
    if param == "stop_id" and "stop_id" not in names:
        return [c for c in ("origin_stop_id", "destination_stop_id") if c in names]
    if param in DATE_FILTERS:
        return [DATE_COLUMN] if DATE_COLUMN in names else []
    return [param] if param in names else []


def supported_filters(table: Table) -> list[str]:
    return [p for p in (*VALUE_FILTERS, *DATE_FILTERS) if filter_columns(table, p)]


def _parse_date(param: str) -> date:
    try:
        return date.fromisoformat(request.args[param])
    except ValueError:
        raise ApiError(400, "invalid_parameter", f"'{param}' must be a date in YYYY-MM-DD format.") from None


def build_query(table: Table) -> Select:
    """SELECT the data columns with the request's filters and sort applied (no paging)."""
    query = select(*data_columns(table))
    unsupported = [p for p in (*VALUE_FILTERS, *DATE_FILTERS)
                   if request.args.get(p) not in (None, "") and not filter_columns(table, p)]
    if unsupported:
        raise ApiError(400, "unsupported_filter", f"Table '{table.name}' cannot be filtered by {', '.join(unsupported)}.",
                       {"supported_filters": supported_filters(table)})

    for param in VALUE_FILTERS:
        value = request.args.get(param)
        if value in (None, ""):
            continue
        if param == "direction":
            if value not in ("0", "1"):
                raise ApiError(400, "invalid_parameter", "'direction' must be 0 or 1.")
            value = int(value)
        query = query.where(or_(*[table.c[c] == value for c in filter_columns(table, param)]))

    if request.args.get("date_from"):
        query = query.where(table.c[DATE_COLUMN] >= _parse_date("date_from"))
    if request.args.get("date_to"):
        query = query.where(table.c[DATE_COLUMN] <= _parse_date("date_to"))

    return query.order_by(*_order_by(table))


def _order_by(table: Table) -> list:
    sort = request.args.get("sort", "")
    if not sort:
        return [table.c.id]                      # load order = Parquet order
    clauses = []
    for part in sort.split(","):
        name = part.strip().lstrip("-")
        if name not in table.c or name == "id":
            raise ApiError(400, "invalid_sort", f"Cannot sort '{table.name}' by '{name}'.",
                           {"columns": [c.name for c in data_columns(table)]})
        clauses.append(table.c[name].desc() if part.strip().startswith("-") else table.c[name].asc())
    return clauses + [table.c.id]                # stable paging on ties


def page() -> tuple[int, int]:
    """(limit, offset) from the request, bounded by API_MAX_LIMIT."""
    cfg = current_app.config
    return (int_arg("limit", cfg["API_DEFAULT_LIMIT"], 1, cfg["API_MAX_LIMIT"]),
            int_arg("offset", 0, 0))


def count(session, query: Select) -> int:
    return session.execute(select(func.count()).select_from(query.order_by(None).subquery())).scalar_one()


def to_json_value(value):
    """JSON-safe value: decimals as numbers (float repr is exact for these precisions), dates as ISO."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def describe(table: Table) -> dict:
    """Column names/types and filters, for the table listing endpoints."""
    return {
        "name": table.name,
        "columns": [{"name": n, "type": t} for n, t in ANALYTICS_SCHEMAS[table.name]],
        "filters": supported_filters(table),
    }
