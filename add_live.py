import sys

c = open('src/blueprints/network.py').read()
if 'def live_vehicles' in c:
    sys.exit(0)

code = """
@bp.get("/live_vehicles")
@permission_required("analytics:read")
def live_vehicles():
    \"\"\"Simulate a live feed by mapping current real-world time into the replay window.\"\"\"
    window = _cached("replay", _replay_window)
    if not window["start"]:
        raise ApiError(404, "no_replay_data", "No GPS data loaded.")
    start_dt = datetime.fromisoformat(window["start"])
    end_dt = datetime.fromisoformat(window["end"])
    duration = end_dt - start_dt
    now = datetime.now()
    offset_seconds = now.timestamp() % duration.total_seconds()
    at = start_dt + timedelta(seconds=offset_seconds)
    seconds = int_arg("window", 30, 10, 300)

    latest = (select(GpsEvent.vehicle_id, func.max(GpsEvent.event_time).label("t"))
              .where(GpsEvent.event_time > at - timedelta(seconds=seconds), GpsEvent.event_time <= at)
              .group_by(GpsEvent.vehicle_id).subquery())
    rows = db.session.execute(
        select(GpsEvent, Route.route_code, Route.route_type)
        .join(latest, and_(latest.c.vehicle_id == GpsEvent.vehicle_id, latest.c.t == GpsEvent.event_time))
        .outerjoin(Route, Route.route_id == GpsEvent.route_id)
        .order_by(GpsEvent.vehicle_id, GpsEvent.event_id)).all()

    seen, out = set(), []
    for ev, route_code, route_type in rows:
        if ev.vehicle_id in seen:
            continue
        seen.add(ev.vehicle_id)
        out.append({
            "vehicle_id": ev.vehicle_id, "trip_id": ev.trip_id, "route_id": ev.route_id,
            "route_code": route_code, "route_type": route_type, "stop_id": ev.stop_id,
            "event_type": ev.event_type, "event_time": ev.event_time.isoformat(),
            "longitude": ev.longitude, "latitude": ev.latitude, "speed_kmh": ev.speed_kmh,
        })
    return jsonify(at=at.isoformat(), window_seconds=seconds, active=len(out), vehicles=out, source="Simulated Live Feed")
"""

open('src/blueprints/network.py', 'a').write(code)
