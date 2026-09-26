"""Phase 1 reference tables (routes, stops, vehicles) for the admin CRUD screens.

Columns follow `documentation/schemas/<table>.json` (the Phase 1 contract) and are filled
from the Phase 3 clean Parquet (`/urbantransit/clean/<table>`). Two clean-only columns:

* `dq_flags` (array<string> in Parquet) is kept as JSON, so the admin screen can show
  which Phase 3 data-quality flags a row carries.
* `_source_file` (ingest lineage) is not copied; it describes the raw CSV, not the entity.

MySQL is a working copy for the admin UI. Edits here are not written back to HDFS, and the
analytics pipeline keeps reading the clean Parquet. See documentation/backend_api.md.
"""

from src.extensions import db


class ReferenceMixin:
    """Shared serialisation: every column, dates as ISO strings."""

    def to_dict(self) -> dict:
        out = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            out[col.name] = value.isoformat() if hasattr(value, "isoformat") else value
        return out


class Stop(ReferenceMixin, db.Model):
    __tablename__ = "stops"

    stop_id = db.Column(db.String(16), primary_key=True)
    stop_name = db.Column(db.String(128), nullable=False)
    latitude = db.Column(db.Double, nullable=False)
    longitude = db.Column(db.Double, nullable=False)
    zone = db.Column(db.String(8), nullable=False)
    stop_type = db.Column(db.String(32), nullable=False)
    has_shelter = db.Column(db.Boolean(create_constraint=False), nullable=False)
    opened_date = db.Column(db.Date, nullable=False)
    dq_flags = db.Column(db.JSON)


class Route(ReferenceMixin, db.Model):
    __tablename__ = "routes"

    route_id = db.Column(db.String(16), primary_key=True)
    route_code = db.Column(db.String(16), nullable=False)
    route_name = db.Column(db.String(128), nullable=False)
    route_type = db.Column(db.String(32), nullable=False)
    origin_stop_id = db.Column(db.String(16), db.ForeignKey("stops.stop_id"), nullable=False)
    destination_stop_id = db.Column(db.String(16), db.ForeignKey("stops.stop_id"), nullable=False)
    distance_km = db.Column(db.Double, nullable=False)
    base_fare = db.Column(db.Double, nullable=False)
    fare_per_km = db.Column(db.Double, nullable=False)
    launch_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), nullable=False)
    dq_flags = db.Column(db.JSON)


class Vehicle(ReferenceMixin, db.Model):
    __tablename__ = "vehicles"

    vehicle_id = db.Column(db.String(16), primary_key=True)
    registration_no = db.Column(db.String(32), nullable=False)
    vehicle_type = db.Column(db.String(32), nullable=False)
    capacity_seated = db.Column(db.Integer, nullable=False)
    capacity_total = db.Column(db.Integer, nullable=False)
    depot = db.Column(db.String(64), nullable=False)
    fuel_type = db.Column(db.String(16), nullable=False)
    commission_date = db.Column(db.Date, nullable=False)
    has_apc = db.Column(db.Boolean(create_constraint=False), nullable=False)
    status = db.Column(db.String(16), nullable=False)
    dq_flags = db.Column(db.JSON)


REFERENCE_MODELS = {"routes": Route, "stops": Stop, "vehicles": Vehicle}
