"""Reference-data CRUD, validation from the Phase 1 contract, users and audit trail."""

NEW_STOP = {"stop_id": "S0900", "stop_name": "Test Stop", "latitude": 24.8, "longitude": 67.0, "zone": "B",
            "stop_type": "regular", "has_shelter": False, "opened_date": "2026-01-15"}


def test_list_search_and_get_with_analytics(client, auth):
    h = auth("analyst")
    body = client.get("/api/admin/routes", headers=h).get_json()
    assert body["total"] == 1 and body["rows"][0]["route_id"] == "R001"
    assert client.get("/api/admin/stops?q=Airport", headers=h).get_json()["total"] == 1
    body = client.get("/api/admin/routes/R001", headers=h).get_json()
    assert body["row"]["launch_date"] == "2025-09-01"
    assert body["analytics"]["route_performance"]["route_class"] == "High Performing"
    assert body["analytics"]["route_reliability"]["on_time_rate"] == 0.81
    assert client.get("/api/admin/routes/R999", headers=h).status_code == 404
    assert client.get("/api/admin/buses", headers=h).status_code == 404


def test_create_update_delete_stop_is_audited(client, auth):
    h = auth("admin")
    res = client.post("/api/admin/stops", json=NEW_STOP, headers=h)
    assert res.status_code == 201 and res.get_json()["row"]["dq_flags"] == []
    assert client.post("/api/admin/stops", json=NEW_STOP, headers=h).status_code == 409
    res = client.patch("/api/admin/stops/S0900", json={"stop_name": "Renamed"}, headers=h)
    assert res.get_json()["row"]["stop_name"] == "Renamed"
    assert client.delete("/api/admin/stops/S0900", headers=h).status_code == 204
    actions = [e["action"] for e in client.get("/api/admin/audit-log", headers=h).get_json()["entries"]]
    assert actions[:3] == ["stops.delete", "stops.update", "stops.create"]


def test_validation_uses_phase1_contract(client, auth):
    h = auth("admin")
    res = client.post("/api/admin/stops", json={**NEW_STOP, "stop_type": "bus_shelter", "latitude": "north"}, headers=h)
    fields = res.get_json()["error"]["details"]["fields"]
    assert res.status_code == 400
    assert fields["stop_type"] == "must be one of ['hub', 'terminal', 'regular']"
    assert fields["latitude"] == "must be a number"
    res = client.post("/api/admin/stops", json={"stop_id": "S0901"}, headers=h)
    assert res.get_json()["error"]["details"]["fields"]["stop_name"] == "is required"
    res = client.patch("/api/admin/routes/R001", json={"route_id": "R777", "dq_flags": ["x"]}, headers=h)
    assert res.get_json()["error"]["details"]["fields"] == {"route_id": "the primary key cannot be changed",
                                                            "dq_flags": "read-only column"}


def test_route_foreign_keys(client, auth):
    h = auth("admin")
    res = client.patch("/api/admin/routes/R001", json={"origin_stop_id": "S9999"}, headers=h)
    assert res.status_code == 400
    res = client.delete("/api/admin/stops/S0001", headers=h)
    assert res.status_code == 409 and res.get_json()["error"]["details"]["routes"] == ["R001"]


def test_user_management(client, auth):
    h = auth("admin")
    res = client.post("/api/admin/users", json={"username": "newbie", "password": "longenough", "roles": ["analyst"]},
                      headers=h)
    assert res.status_code == 201
    user_id = res.get_json()["user"]["id"]
    assert client.post("/api/admin/users", json={"username": "x", "password": "longenough", "roles": ["king"]},
                       headers=h).status_code == 400
    res = client.patch(f"/api/admin/users/{user_id}", json={"roles": ["operator"], "is_active": False}, headers=h)
    assert res.get_json()["user"]["roles"] == ["operator"] and res.get_json()["user"]["is_active"] is False
    assert client.post("/api/auth/login", json={"username": "newbie", "password": "longenough"}).status_code == 401
