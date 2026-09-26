"""CSV export of any analytics table, with the same filters and sort as the JSON endpoint.

GET /api/reports                 exportable tables
GET /api/reports/<table>.csv     streams every matching row (no paging), e.g.
                                 /api/reports/od_matrix.csv?route_id=R001&day_class=weekday

Decimals are written with their exact stored digits (str(Decimal)), NULL as an empty cell.
"""

import csv
import io
from datetime import date
from decimal import Decimal

from flask import Blueprint, Response, jsonify, request, stream_with_context

from src.extensions import db
from src.models.analytics import ANALYTICS_TABLES
from src.security import permission_required
from src.services import analytics_query as aq
from src.services import audit

bp = Blueprint("reports", __name__, url_prefix="/api/reports")
FETCH_BATCH = 5000


def _csv_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (Decimal, date)):
        return str(value)
    return value


@bp.get("")
@permission_required("reports:export")
def list_exports():
    return jsonify(reports=[{"table": t, "url": f"/api/reports/{t}.csv", "filters": aq.supported_filters(tbl)}
                            for t, tbl in ANALYTICS_TABLES.items()])


@bp.get("/<name>.csv")
@permission_required("reports:export")
def export_csv(name: str):
    table = aq.get_table(name)
    query = aq.build_query(table)                # validates filters before streaming starts
    columns = [c.name for c in aq.data_columns(table)]
    audit.record("reports.export", entity=f"analytics/{name}", details={"query": request.args.to_dict()}, commit=True)

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(columns)
        result = db.session.execute(query.execution_options(yield_per=FETCH_BATCH))
        for row in result:
            writer.writerow([_csv_value(v) for v in row])
            if buffer.tell() > 64 * 1024:
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate()
        yield buffer.getvalue()

    return Response(stream_with_context(generate()), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
