"""Phase 6 model evidence: flattened metrics and the K-Means cluster profiles.

`model_metrics` holds one row per (source file, split, metric). The Phase 6 JSON files
use four different layouts, so they are normalised into flat rows
(`database/metrics_normaliser.py`) instead of one rigid schema. Anything that is not a
single number (row counts, k, split dates, feature lists, confusion matrices, trial
parameters) goes into `extra_json`.

`validity_flag` is set to INVALID for every `delay_severity` row. Those models use
`occupancy_pct`, a same-trip outcome, as an input (occupancy leakage). The metrics are
shown for transparency but must not back predictions.
"""

from src.extensions import db


class ModelMetric(db.Model):
    __tablename__ = "model_metrics"

    id = db.Column(db.Integer, primary_key=True)
    source_file = db.Column(db.String(128), nullable=False, index=True)  # models/spark/metrics/<file>
    task = db.Column(db.String(64), nullable=False, index=True)
    algorithm = db.Column(db.String(128), nullable=False)
    split_type = db.Column(db.String(32), nullable=False)    # train | validation | test | test_full | ...
    metric_name = db.Column(db.String(64), nullable=False)   # accuracy | macro_f1 | per_class_f1[Minor] | mae | silhouette ...
    metric_value = db.Column(db.Double)
    extra_json = db.Column(db.JSON)
    validity_flag = db.Column(db.String(16))                 # INVALID, or NULL when no flag has been raised
    validity_note = db.Column(db.String(255))

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class ClusterProfile(db.Model):
    """Mean route features per K-Means (k=4) cluster, from reports/phase6_cluster_profiles.csv.

    Column names are the CSV header, unchanged; `prediction` is the cluster id. No
    route-to-cluster assignment exists yet, so there is deliberately no route_id here.
    """

    __tablename__ = "cluster_profiles"

    prediction = db.Column(db.Integer, primary_key=True, autoincrement=False)
    route_load_factor = db.Column(db.Double)
    route_reliability_delay_min = db.Column(db.Double)
    trip_punctuality_rate = db.Column(db.Double)
    avg_trip_boardings = db.Column(db.Double)
    avg_daily_boardings = db.Column(db.Double)
    crowding_rate = db.Column(db.Double)
    bunching_rate = db.Column(db.Double)
    arrival_delay_std_min = db.Column(db.Double)
    routes = db.Column(db.Integer)
    plain_language_label = db.Column(db.String(128))

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
