"""Analytics JSON endpoints, CSV export and the table spec."""

import csv
import io
import json
from pathlib import Path

from src.models.analytics import ANALYTICS_SCHEMAS

ROOT = Path(__file__).resolve().parent.parent


def test_spec_tables_exist_in_phase5_run():
    """Every mirrored table is a real Phase 5 output (reports/phase5_metrics.json)."""
    phase5 = json.loads((ROOT / "reports" / "phase5_metrics.json").read_text(encoding="utf-8"))
    assert len(ANALYTICS_SCHEMAS) == 30
    assert set(ANALYTICS_SCHEMAS) <= set(phase5)


def test_spec_keeps_mixed_decimal_precisions():
    types = {(t, c): ty for t, cols in ANALYTICS_SCHEMAS.items() for c, ty in cols}
    assert types[("route_performance", "underutilization_score")] == "decimal(16,1)"
    assert types[("route_performance", "med_late_share")] == "decimal(6,4)"
    assert types[("passenger_segments", "active_days_per_week")] == "decimal(30,3)"
    assert types[("passenger_segments", "active_span_weeks")] == "decimal(14,2)"
    assert types[("demand_supply_gap", "required_capacity")] == "decimal(14,1)"
    assert len(ANALYTICS_SCHEMAS["route_performance"]) == 44


def test_list_tables(client, auth):
    body = client.get("/api/analytics", headers=auth("analyst")).get_json()
    tables = {t["name"]: t for t in body["tables"]}
    assert len(tables) == 30
    assert tables["route_performance"]["rows"] == 2
    assert tables["od_matrix"]["filters"] == ["route_id", "stop_id", "direction", "day_class", "time_period"]
    assert tables["eda_peak_days"]["filters"] == ["day_class", "date_from", "date_to"]


def test_rows_filter_sort_and_types(client, auth):
    h = auth("analyst")
    body = client.get("/api/analytics/route_performance?sort=-composite_score", headers=h).get_json()
    assert [r["route_id"] for r in body["rows"]] == ["R001", "R002"]
    assert "id" not in body["rows"][0]
    assert body["rows"][0]["med_late_share"] == 0.0512       # decimal -> JSON number
    assert body["rows"][0]["overcrowded_flag"] is True
    body = client.get("/api/analytics/route_performance?route_id=R002", headers=h).get_json()
    assert body["total"] == 1 and body["rows"][0]["route_class"] == "Low Performing"


def test_stop_filter_matches_origin_or_destination(client, auth):
    body = client.get("/api/analytics/od_matrix?stop_id=S0001", headers=auth("analyst")).get_json()
    assert body["total"] == 2
    body = client.get("/api/analytics/od_matrix?stop_id=S0001&direction=1&time_period=evening_peak",
                      headers=auth("analyst")).get_json()
    assert body["total"] == 1 and body["rows"][0]["origin_stop_id"] == "S0002"


def test_date_range(client, auth):
    body = client.get("/api/analytics/eda_peak_days?date_from=2026-01-01&date_to=2026-12-31",
                      headers=auth("analyst")).get_json()
    assert [r["service_date"] for r in body["rows"]] == ["2026-03-01"]


def test_invalid_requests_are_400_or_404(client, auth):
    h = auth("analyst")
    res = client.get("/api/analytics/route_performance?date_from=2026-01-01", headers=h)
    assert res.status_code == 400 and res.get_json()["error"]["code"] == "unsupported_filter"
    assert res.get_json()["error"]["details"]["supported_filters"] == ["route_id"]
    assert client.get("/api/analytics/od_matrix?direction=2", headers=h).status_code == 400
    assert client.get("/api/analytics/eda_peak_days?date_from=01-01-2026", headers=h).status_code == 400
    assert client.get("/api/analytics/route_performance?sort=nope", headers=h).status_code == 400
    assert client.get("/api/analytics/route_performance?limit=5000", headers=h).status_code == 400
    res = client.get("/api/analytics/overcrowding_trips", headers=h)     # skipped table
    assert res.status_code == 404 and res.get_json()["error"]["code"] == "unknown_table"


def test_paging(client, auth):
    body = client.get("/api/analytics/od_matrix?limit=2&offset=2", headers=auth("analyst")).get_json()
    assert body["total"] == 3 and len(body["rows"]) == 1


def test_csv_export(client, auth):
    res = client.get("/api/reports/route_performance.csv?sort=route_id", headers=auth("analyst"))
    assert res.status_code == 200 and res.mimetype == "text/csv"
    rows = list(csv.reader(io.StringIO(res.get_data(as_text=True))))
    assert rows[0] == [c for c, _ in ANALYTICS_SCHEMAS["route_performance"]]
    header = rows[0]
    assert len(rows) == 3
    assert rows[1][header.index("route_id")] == "R001"
    assert rows[1][header.index("overcrowded_flag")] == "true"
    assert rows[1][header.index("route_code")] == ""            # NULL -> empty cell


def test_csv_export_filters_and_audit(client, auth):
    h = auth("analyst")
    res = client.get("/api/reports/od_matrix.csv?route_id=R002", headers=h)
    assert len(res.get_data(as_text=True).strip().splitlines()) == 2
    assert client.get("/api/reports/od_matrix.csv?date_from=2026-01-01", headers=h).status_code == 400
    log = client.get("/api/admin/audit-log?action=reports.export", headers=auth("evaluator")).get_json()
    assert log["entries"][0]["entity"] == "analytics/od_matrix"


def test_evaluator_can_export_but_not_predict(client, auth):
    assert client.get("/api/reports", headers=auth("evaluator")).status_code == 200
    assert client.post("/api/predictions/delay", json={}, headers=auth("evaluator")).status_code == 403
