"""Health, login, token handling, RBAC guards and the JSON error shape."""

from src.extensions import db
from src.models.ops import AuditLog
from src.models.rbac import User
from tests.conftest import PASSWORD


def test_health_reports_database(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["database"] == "ok"
    assert client.get("/health").status_code == 200


def test_login_returns_token_and_user(client):
    res = client.post("/api/auth/login", json={"username": "analyst", "password": PASSWORD})
    body = res.get_json()
    assert res.status_code == 200
    assert body["token_type"] == "Bearer" and body["access_token"]
    assert body["user"]["roles"] == ["analyst"]
    assert "analytics:read" in body["user"]["permissions"]


def test_bad_password_is_401_and_audited(client, app):
    res = client.post("/api/auth/login", json={"username": "analyst", "password": "wrong"})
    assert res.status_code == 401
    assert res.get_json() == {"error": {"code": "invalid_credentials", "message": "Invalid username or password."}}
    with app.app_context():
        assert db.session.execute(db.select(AuditLog).filter_by(action="auth.login_failed")).scalar_one()


def test_missing_body_fields(client):
    res = client.post("/api/auth/login", json={"username": "analyst"})
    assert res.status_code == 400
    assert res.get_json()["error"]["details"] == {"missing": ["password"]}


def test_me_requires_token_with_json_error(client, auth):
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "unauthorized"
    assert client.get("/api/auth/me", headers=auth("evaluator")).get_json()["user"]["username"] == "evaluator"


def test_garbage_token_is_401(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "invalid_token"


def test_deactivated_user_token_stops_working(client, app, auth):
    headers = auth("operator")
    with app.app_context():
        db.session.execute(db.select(User).filter_by(username="operator")).scalar_one().is_active = False
        db.session.commit()
    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "account_unavailable"


def test_permissions_per_role(client, auth):
    # analyst can read analytics but not the audit log or reference writes
    assert client.get("/api/analytics/route_performance", headers=auth("analyst")).status_code == 200
    assert client.get("/api/admin/audit-log", headers=auth("analyst")).status_code == 403
    assert client.post("/api/admin/stops", json={}, headers=auth("analyst")).status_code == 403
    # evaluator reads the audit log; admin can do everything
    assert client.get("/api/admin/audit-log", headers=auth("evaluator")).status_code == 200
    assert client.get("/api/admin/users", headers=auth("admin")).status_code == 200
    res = client.get("/api/admin/users", headers=auth("operator"))
    assert res.status_code == 403
    assert res.get_json()["error"] == {"code": "forbidden", "message": "Requires permission users:manage."}


def test_unknown_route_is_json_404(client):
    res = client.get("/api/nope")
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "not_found"


def test_cors_allows_react_dev_origin(client):
    res = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert res.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
    res = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "Access-Control-Allow-Origin" not in res.headers
