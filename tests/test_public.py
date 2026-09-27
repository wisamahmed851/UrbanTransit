"""GET /api/public/summary (CMD-026): readable without signing in, network-level totals only."""

from src.blueprints import public


def test_summary_is_public_and_aggregate(client):
    public._cache.clear()
    res = client.get("/api/public/summary")
    assert res.status_code == 200
    body = res.get_json()
    assert body["network"] == {"routes": 1, "stops": 2, "vehicles": 1}
    assert body["service"]["first_day"] == "2025-10-12" and body["service"]["avg_daily_boardings"] == 950000
    assert body["route_classes"] == {"High Performing": 1, "Low Performing": 1}
    # nothing about people: no users, passengers, cards or trips in the payload
    text = res.get_data(as_text=True).lower()
    assert all(word not in text for word in ("username", "passenger_id", "card", "trip_id"))
