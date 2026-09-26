"""Phase 5 analytics summary tables, read from MySQL (loaded from HDFS by the loader).

GET /api/analytics               every table: columns (Spark types), row count, filters
GET /api/analytics/<table>       rows, with filters/sort/paging (see services/analytics_query.py)

Example: /api/analytics/route_performance?sort=-composite_score&limit=10
         /api/analytics/od_matrix?route_id=R001&time_period=morning_peak&day_class=weekday
"""

from flask import Blueprint, jsonify
from sqlalchemy import select

from src.extensions import db
from src.models.analytics import ANALYTICS_TABLES
from src.security import permission_required
from src.services import analytics_query as aq

bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


@bp.get("")
@permission_required("analytics:read")
def list_tables():
    tables = []
    for table in ANALYTICS_TABLES.values():
        info = aq.describe(table)
        info["rows"] = aq.count(db.session, select(table.c.id))
        tables.append(info)
    return jsonify(tables=tables, source="hdfs:///urbantransit/analytics (Phase 5), loaded into MySQL")


@bp.get("/<name>")
@permission_required("analytics:read")
def get_rows(name: str):
    table = aq.get_table(name)
    query = aq.build_query(table)
    limit, offset = aq.page()
    total = aq.count(db.session, query)
    rows = db.session.execute(query.limit(limit).offset(offset)).mappings()
    return jsonify(
        table=name,
        total=total,
        limit=limit,
        offset=offset,
        filters=aq.supported_filters(table),
        rows=[{k: aq.to_json_value(v) for k, v in row.items()} for row in rows],
    )
