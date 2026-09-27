"""Tables behind the model-serving endpoints (CMD-024). All are filled by
`database/load_model_outputs.py` from the Phase 7-9 outputs; the API only reads them.

| table | source | used by |
|---|---|---|
| `route_daily_boardings` | Phase 7 `demand_frame()`: completed trips' boardings per route and day | demand forecast (lag features), forecast history |
| `stop_period_boardings` | Phase 7 `stop_period_demand_frame()`: ticket tap-ins by entry stop/day/period | stop-period demand forecast |
| `trip_context` | Phase 7 `base_trip()`, last `trip_context_weeks` weeks | the "typical trip" inputs a prediction needs (headway, runtime, vehicle, recent history) |
| `recommendations` | `reports/recommendations.json` (Phase 9 engine) | recommendations page |
| `pipeline_comparison` | `reports/comparison/task_*.csv` (Phase 8) | Spark vs Python page |
| `route_clusters`, `python_cluster_profiles` | saved agglomerative k=5 model + `reports/python_cluster_profiles.csv` | route clusters |

Laravel analogy: Eloquent models over read-only reporting tables filled by an Artisan command.
"""

from src.extensions import db


class RouteDailyBoardings(db.Model):
    """Boardings per route per service day (APC counts, completed trips), as Phase 7 trains on."""

    __tablename__ = "route_daily_boardings"

    route_id = db.Column(db.String(16), primary_key=True)
    service_date = db.Column(db.Date, primary_key=True)
    boardings = db.Column(db.Integer, nullable=False)


class StopPeriodBoardings(db.Model):
    """Observed smart-card tap-ins per entry stop, service day and time period.

    It does not represent cash passengers. The API calls the target ``tap_ins`` so
    that the UI cannot accidentally present it as a complete passenger count.
    """

    __tablename__ = "stop_period_boardings"

    entry_stop_id = db.Column(db.String(16), primary_key=True)
    service_date = db.Column(db.Date, primary_key=True)
    time_period = db.Column(db.String(16), primary_key=True)
    tap_ins = db.Column(db.Integer, nullable=False)


class TripContext(db.Model):
    """What a typical trip looks like for one route, direction, day type and departure hour.

    A prediction request only names a route, direction, date and hour. The model also needs
    the schedule inputs (headway, planned runtime), the vehicle usually assigned, and the
    route's recent crowding/delay history. They are taken from here: medians/modes over the
    most recent completed trips, and the rolling history as of the last trip in the data.
    The `observed_*` columns are what actually happened in that cell, shown next to a prediction.
    """

    __tablename__ = "trip_context"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.String(16), nullable=False)
    direction = db.Column(db.Integer, nullable=False)
    day_type = db.Column(db.String(8), nullable=False)          # weekday | weekend
    hour = db.Column(db.Integer, nullable=False)
    # model inputs
    vehicle_id = db.Column(db.String(16))
    vehicle_type = db.Column(db.String(32))
    capacity_total = db.Column(db.Double)
    route_type = db.Column(db.String(32))
    distance_km = db.Column(db.Double)
    planned_runtime_min = db.Column(db.Double)
    headway_min = db.Column(db.Double)
    scheduled_runtime_min = db.Column(db.Double)
    prior_route_crowding_rate = db.Column(db.Double)
    prior_route_delay_mean = db.Column(db.Double)
    prior_route_occupancy_mean = db.Column(db.Double)
    prior_route_hour_occupancy_mean = db.Column(db.Double)
    # delay model v1 (enhanced): the same route/direction/hour's last 56 trips (CMD-028)
    prior_route_hour_delay_mean = db.Column(db.Double)
    prior_route_hour_severe_rate = db.Column(db.Double)
    # what was observed in this cell over the window
    trips_observed = db.Column(db.Integer, nullable=False)
    observed_crowding_rate = db.Column(db.Double)
    observed_mean_delay_min = db.Column(db.Double)
    mean_boardings = db.Column(db.Double)
    mean_max_load = db.Column(db.Double)
    mean_occupancy = db.Column(db.Double)
    p90_occupancy = db.Column(db.Double)
    window_start = db.Column(db.Date, nullable=False)
    window_end = db.Column(db.Date, nullable=False)

    __table_args__ = (db.UniqueConstraint("route_id", "direction", "day_type", "hour", name="uq_trip_context_cell"),)

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns if c.name != "id"}


class Recommendation(db.Model):
    """One Phase 9 recommendation, as written by recommendation_engine/engine.py."""

    __tablename__ = "recommendations"

    recommendation_id = db.Column(db.String(16), primary_key=True)
    subject_id = db.Column(db.String(32), nullable=False, index=True)    # route (R012), stop (S0457), ...
    category = db.Column(db.String(32), nullable=False, index=True)      # CAPACITY | FREQUENCY | SCHEDULE | ...
    priority = db.Column(db.String(16), nullable=False, index=True)      # Critical | High | Medium | Low
    priority_rank = db.Column(db.Integer, nullable=False)                # 1 = Critical ... 4 = Low, for sorting
    action = db.Column(db.Text, nullable=False)
    evidence = db.Column(db.Text, nullable=False)
    estimated_impact = db.Column(db.Text)

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class PipelineComparison(db.Model):
    """One unseen test case scored by both pipelines (Phase 8), task a/b/c."""

    __tablename__ = "pipeline_comparison"

    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(32), nullable=False, index=True)          # delay_severity | crowding_flag | daily_boardings
    case_id = db.Column(db.String(64), nullable=False)
    actual = db.Column(db.String(32))
    spark_prediction = db.Column(db.String(32))
    python_prediction = db.Column(db.String(32))
    spark_value = db.Column(db.String(255))                              # probability vector or predicted value, as written
    python_value = db.Column(db.String(64))
    absolute_difference = db.Column(db.Double)
    match = db.Column(db.Boolean(create_constraint=False), nullable=False)
    agreement_status = db.Column(db.String(32), nullable=False, index=True)  # BothCorrect | SparkOnlyCorrect | PyOnlyCorrect | BothWrong
    explanation = db.Column(db.Text)

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns if c.name != "id"}


class RouteCluster(db.Model):
    """Route -> cluster assignment from the saved Phase 7 agglomerative (k=5) model."""

    __tablename__ = "route_clusters"

    route_id = db.Column(db.String(16), primary_key=True)
    algorithm = db.Column(db.String(64), nullable=False)
    cluster = db.Column(db.Integer, nullable=False, index=True)


class PythonClusterProfile(db.Model):
    """Mean train-period route features per Phase 7 cluster (reports/python_cluster_profiles.csv)."""

    __tablename__ = "python_cluster_profiles"

    cluster = db.Column(db.Integer, primary_key=True, autoincrement=False)
    avg_occupancy = db.Column(db.Double)
    avg_delay_minutes = db.Column(db.Double)
    reliability_score = db.Column(db.Double)
    trip_frequency = db.Column(db.Double)
    peak_demand_ratio = db.Column(db.Double)
    load_factor = db.Column(db.Double)
    avg_travel_time = db.Column(db.Double)
    demand_mom_growth = db.Column(db.Double)
    avg_daily_boardings = db.Column(db.Double)
    profile_label = db.Column(db.String(128))
    routes = db.Column(db.Integer)

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
