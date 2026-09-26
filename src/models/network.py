"""Network geometry and GPS replay data for the map (CMD-022).

* `route_stops`: ordered stops of every route and direction (Phase 1 bridge table, Phase 3
  clean copy). Joined with `stops` coordinates it draws the route lines.
* `gps_events`: simulated AVL pings from the Phase 1 generator. They cover a **7-day sample
  window only** (10-16 Nov 2025), so the map replays them with a visible date. There is no
  real-time feed; nothing in the API calls these positions "live".

Columns follow the clean Parquet (`documentation/schemas/<table>.json`); `_source_file` is
not copied and `dq_flags` is kept as JSON, as for the other reference tables.
"""

from src.extensions import db
from src.models.reference import ReferenceMixin


class RouteStop(ReferenceMixin, db.Model):
    __tablename__ = "route_stops"

    route_id = db.Column(db.String(16), db.ForeignKey("routes.route_id"), primary_key=True)
    direction = db.Column(db.Integer, primary_key=True, autoincrement=False)
    stop_sequence = db.Column(db.Integer, primary_key=True, autoincrement=False)
    stop_id = db.Column(db.String(16), db.ForeignKey("stops.stop_id"), nullable=False, index=True)
    distance_from_start_km = db.Column(db.Double, nullable=False)
    scheduled_offset_min = db.Column(db.Double, nullable=False)
    is_timing_point = db.Column(db.Boolean(create_constraint=False), nullable=False)
    dq_flags = db.Column(db.JSON)


class GpsEvent(db.Model):
    __tablename__ = "gps_events"

    event_id = db.Column(db.String(32), primary_key=True)
    vehicle_id = db.Column(db.String(16), nullable=False)
    trip_id = db.Column(db.String(16))
    route_id = db.Column(db.String(16))
    stop_id = db.Column(db.String(16))           # null while in transit
    event_time = db.Column(db.DateTime, nullable=False)
    event_type = db.Column(db.String(32), nullable=False)   # stop_arrival | stop_departure | in_transit
    latitude = db.Column(db.Double, nullable=False)
    longitude = db.Column(db.Double, nullable=False)
    speed_kmh = db.Column(db.Double)
    dq_flags = db.Column(db.JSON)
    event_date = db.Column(db.Date, nullable=False)

    # "latest ping per vehicle before time T" scans a short time range, then groups by vehicle.
    __table_args__ = (db.Index("ix_gps_events_time_vehicle", "event_time", "vehicle_id"),)
