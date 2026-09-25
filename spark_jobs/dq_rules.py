"""Generic data-quality checks used by data_quality.py and clean_data.py.

Design
------
* Each *check type* (required_value, foreign_key, duplicate_key, ...) is written once here.
* config/data_quality.yaml lists the *rules*: which check runs on which table/columns with
  which thresholds, plus the cleaning action. No ID or value from our dataset appears in
  this file, so the same code runs on new data (new stops, unknown vehicles, new defects).
* Every check returns the same shape of DataFrame - one row per violation:

      rule_id | table | record_key | column | observed_value | units

  `record_key` is the table's primary key (from documentation/schemas) joined with "|".
  `units` is 1 per row, except where a single row stands for several problems
  (e.g. 3 missing ticket records on one trip, or 2 extra copies of one duplicate).

Laravel analogy: each check is like a reusable validation rule class (`Rule::exists`,
`Rule::unique`, `min`, `max`); the YAML file is the `rules()` array that applies them.

The pipeline reads only HDFS data and config/*.yaml - never the generator's manifests.
"""

import json
from pathlib import Path

import yaml
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import LongType, StringType, StructField, StructType
from pyspark.sql.window import Window

from spark_jobs.common import hdfs_uri
from spark_jobs.schemas import FORMATS, SCHEMAS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = PROJECT_ROOT / "documentation" / "schemas"
DQ_CONFIG = PROJECT_ROOT / "config" / "data_quality.yaml"

VIOLATION_SCHEMA = StructType([
    StructField("rule_id", StringType()), StructField("table", StringType()),
    StructField("record_key", StringType()), StructField("column", StringType()),
    StructField("observed_value", StringType()), StructField("units", LongType()),
])


def load_dq_config() -> dict:
    with open(DQ_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def primary_key(table: str) -> list[str]:
    """Primary-key columns of a table, from documentation/schemas/<table>.json."""
    return json.loads((SCHEMA_DIR / f"{table}.json").read_text(encoding="utf-8"))["primary_key"]


def key_expr(table: str):
    """Column expression for the record key: PK values joined with '|'."""
    return F.concat_ws("|", *[F.col(c).cast("string") for c in primary_key(table)])


class DQData:
    """Lazy access to one dataset's Phase 2 outputs in HDFS (Parquet + ingestion quarantine)."""

    def __init__(self, spark: SparkSession, mode: str):
        self.spark, self.mode = spark, mode
        self._tables, self._quarantine = {}, {}

    def table(self, name: str) -> DataFrame:
        """Phase 2 Parquet (type-valid rows) of a table."""
        if name not in self._tables:
            self._tables[name] = self.spark.read.parquet(hdfs_uri(self.mode, "parquet", name))
        return self._tables[name]

    def quarantine(self, name: str) -> DataFrame:
        """Rows quarantined at ingestion, with their raw text re-read as string columns.

        Columns: raw_record, failed_columns, source_file, record_key, plus every table column as string.
        """
        if name not in self._quarantine:
            fields = SCHEMAS[name].fields
            as_str = StructType([StructField(f.name, StringType(), True) for f in fields])
            path = hdfs_uri(self.mode, "quarantine", name)
            q = self.spark.read.schema("table STRING, source_file STRING, raw_record STRING, failed_columns STRING, "
                                       "reason STRING, quarantined_at STRING").json(path)
            parsed = (F.from_csv(F.col("raw_record"), as_str.simpleString(), {"header": "false"})
                      if FORMATS[name] == "csv" else F.from_json(F.col("raw_record"), as_str))
            q = q.withColumn("_p", parsed).select("raw_record", "failed_columns", "source_file", "_p.*")
            self._quarantine[name] = q.withColumn("record_key", key_expr(name))
        return self._quarantine[name]


def _violations(df: DataFrame, rule: dict, column, observed, units=None) -> DataFrame:
    """Shape any DataFrame of offending rows into the common violation format."""
    return df.select(
        F.lit(rule["id"]).alias("rule_id"), F.lit(rule["table"]).alias("table"),
        key_expr(rule["table"]).alias("record_key") if "record_key" not in df.columns else F.col("record_key"),
        (column if not isinstance(column, str) else F.lit(column)).alias("column"),
        observed.cast("string").alias("observed_value"),
        (units if units is not None else F.lit(1)).cast("long").alias("units"),
    )


# ---------------------------------------------------------------------------
# Check types
# ---------------------------------------------------------------------------

def check_required_value(d: DQData, rule, P):
    """Value is missing (null or blank)."""
    c = rule["params"]["column"]
    df = d.table(rule["table"])
    bad = df.filter(F.col(c).isNull() | (F.trim(F.col(c).cast("string")) == ""))
    return _violations(bad, rule, c, F.lit(None))


def check_foreign_key(d: DQData, rule, P):
    """Non-empty value(s) that do not exist in the parent table's key column."""
    p = rule["params"]
    parent = d.table(p["parent_table"]).select(F.col(p["parent_key"]).alias("_parent")).distinct()
    df = d.table(rule["table"]).withColumn("record_key", key_expr(rule["table"]))
    fails = []
    for c in p["columns"]:
        df = (df.join(F.broadcast(parent.withColumnRenamed("_parent", f"_ok_{c}")),
                      F.col(c) == F.col(f"_ok_{c}"), "left"))
        fails.append(F.when(F.col(c).isNotNull() & F.col(f"_ok_{c}").isNull(), F.lit(c)))
    bad_cols = F.concat_ws(",", *fails)
    bad = df.withColumn("_bad", bad_cols).filter(F.col("_bad") != "")
    observed = F.concat_ws(",", *[F.when(F.col(f"_ok_{c}").isNull(), F.col(c)) for c in p["columns"]])
    return _violations(bad, rule, F.col("_bad"), observed)


def check_duplicate_key(d: DQData, rule, P):
    """Primary key appears more than once. units = extra copies; observed says if copies differ."""
    t = rule["table"]
    cols = [c for c in d.table(t).columns if c != "_source_file"]
    df = d.table(t).withColumn("record_key", key_expr(t)).withColumn("_row", F.xxhash64(*cols))
    g = df.groupBy("record_key").agg(F.count("*").alias("n"), F.countDistinct("_row").alias("versions"))
    bad = g.filter(F.col("n") > 1)
    observed = F.when(F.col("versions") > 1, F.lit("conflicting_copies")).otherwise(F.lit("identical_copies"))
    return _violations(bad, rule, ",".join(primary_key(t)), F.concat(F.col("n").cast("string"), F.lit(" rows, "), observed),
                       F.col("n") - 1)


def check_non_negative(d: DQData, rule, P):
    """Any of the listed numeric columns is below zero."""
    cols = rule["params"]["columns"]
    df = d.table(rule["table"])
    bad_cols = F.concat_ws(",", *[F.when(F.col(c) < 0, F.lit(c)) for c in cols])
    observed = F.concat_ws(",", *[F.when(F.col(c) < 0, F.col(c).cast("string")) for c in cols])
    bad = df.withColumn("_bad", bad_cols).withColumn("_obs", observed).filter(F.col("_bad") != "")
    return _violations(bad, rule, F.col("_bad"), F.col("_obs"))


def check_unparseable(d: DQData, rule, P):
    """Rows quarantined at ingestion because one of the listed columns could not be parsed."""
    cols = rule["params"]["columns"]
    q = d.quarantine(rule["table"])
    hit = F.concat_ws(",", *[F.when(F.array_contains(F.split("failed_columns", ","), c), F.lit(c)) for c in cols])
    bad = q.withColumn("_bad", hit).filter(F.col("_bad") != "")
    observed = F.concat_ws(",", *[F.when(F.array_contains(F.split("failed_columns", ","), c), F.col(c)) for c in cols])
    return _violations(bad, rule, F.col("_bad"), observed)


def check_time_gap(d: DQData, rule, P):
    """|column - reference| larger than impossible_time_gap_hours."""
    p = rule["params"]
    gap = F.abs(F.unix_timestamp(p["column"]) - F.unix_timestamp(p["reference"])) / 3600.0
    bad = d.table(rule["table"]).filter(gap > P["impossible_time_gap_hours"])
    return _violations(bad, rule, p["column"],
                       F.concat(F.col(p["column"]).cast("string"), F.lit(" vs "), F.col(p["reference"]).cast("string")))


def check_time_order(d: DQData, rule, P):
    """`later` timestamp is before `earlier`."""
    p = rule["params"]
    bad = d.table(rule["table"]).filter(F.col(p["later"]) < F.col(p["earlier"]))
    return _violations(bad, rule, p["later"],
                       F.concat(F.col(p["earlier"]).cast("string"), F.lit(" -> "), F.col(p["later"]).cast("string")))


def check_capacity(d: DQData, rule, P):
    """Load above capacity_violation_factor x the vehicle's capacity_total (unknown vehicles are skipped)."""
    p = rule["params"]
    veh = d.table("vehicles").select(F.col("vehicle_id").alias("_vid"), F.col("capacity_total").alias("_cap"))
    df = d.table(rule["table"]).join(F.broadcast(veh), F.col(p["vehicle_column"]) == F.col("_vid"), "inner")
    bad = df.filter(F.col(p["load_column"]) > P["capacity_violation_factor"] * F.col("_cap"))
    return _violations(bad, rule, p["load_column"],
                       F.concat(F.col(p["load_column"]).cast("string"), F.lit(" / capacity "), F.col("_cap").cast("string")))


def check_value_range(d: DQData, rule, P):
    """Value outside [min, max] (min exclusive if configured); optionally also unparseable values."""
    p = rule["params"]
    c, lo, hi = p["column"], P[p["min_param"]], P[p["max_param"]]
    low_bad = (F.col(c) <= lo) if p.get("min_exclusive") else (F.col(c) < lo)
    bad = d.table(rule["table"]).filter(low_bad | (F.col(c) > hi))
    out = _violations(bad, rule, c, F.col(c))
    if p.get("include_unparseable"):
        q = d.quarantine(rule["table"]).filter(F.array_contains(F.split("failed_columns", ","), c))
        out = out.unionByName(_violations(q, rule, c, F.col(c)))
    return out


def check_sequence_integrity(d: DQData, rule, P):
    """Per group, the sequence numbers must be exactly 1..n. record_key = group values joined with '|'."""
    p = rule["params"]
    g = (d.table(rule["table"]).groupBy(*p["group_by"])
         .agg(F.array_sort(F.collect_list(F.col(p["sequence_column"]).cast("int"))).alias("seq")))
    g = g.withColumn("expected", F.sequence(F.lit(1), F.size("seq")))
    bad = g.filter(F.col("seq") != F.col("expected")).withColumn(
        "record_key", F.concat_ws("|", *[F.col(c).cast("string") for c in p["group_by"]]))
    return _violations(bad, rule, p["sequence_column"], F.array_join("seq", ","))


def check_missing_parent(d: DQData, rule, P):
    """Distinct IDs used by child tables (and their ingestion-quarantined rows) that are absent from the parent."""
    p = rule["params"]
    parent = d.table(rule["table"]).select(F.col(p["parent_key"]).alias("_id")).distinct()
    refs = None
    for child in p["child_tables"]:
        ids = d.table(child).select(F.col(p["child_column"]).alias("_id"))
        if FORMATS[child] in ("csv", "jsonl"):
            ids = ids.unionByName(d.quarantine(child).select(F.col(p["child_column"]).alias("_id")))
        ids = ids.filter(F.col("_id").isNotNull()).distinct().withColumn("_child", F.lit(child))
        refs = ids if refs is None else refs.unionByName(ids)
    missing = (refs.join(parent, "_id", "left_anti").groupBy("_id")
               .agg(F.concat_ws(",", F.sort_array(F.collect_set("_child"))).alias("_children")))
    return _violations(missing.withColumn("record_key", F.col("_id")), rule, p["parent_key"], F.col("_children"))


def check_timestamp_date_window(d: DQData, rule, P):
    """Timestamp outside [service_date + lo days, service_date + hi days)."""
    p = rule["params"]
    lo, hi = P["timestamp_date_window_days"]
    ts = F.col(p["column"])
    start = F.date_add(F.col(p["date_column"]), lo).cast("timestamp")     # e.g. service_date - 1 day
    end = F.date_add(F.col(p["date_column"]), hi).cast("timestamp")       # e.g. service_date + 2 days
    bad = d.table(rule["table"]).filter(ts.isNotNull() & ((ts < start) | (ts >= end)))
    return _violations(bad, rule, p["column"],
                       F.concat(ts.cast("string"), F.lit(" for "), F.col(p["date_column"]).cast("string")))


def check_geo_bounds(d: DQData, rule, P):
    """Coordinates outside the configured operating area."""
    p, b = rule["params"], P["geo_bounds"]
    lat, lon = F.col(p["lat"]), F.col(p["lon"])
    bad = d.table(rule["table"]).filter(~lat.between(b["lat_min"], b["lat_max"]) | ~lon.between(b["lon_min"], b["lon_max"]))
    return _violations(bad, rule, f"{p['lat']},{p['lon']}", F.concat(lat.cast("string"), F.lit(","), lon.cast("string")))


def check_count_vs_children(d: DQData, rule, P):
    """A count column larger than the number of distinct child records for the same join key."""
    p = rule["params"]
    child = d.table(p["child_table"]).select(p["join_column"], p["child_key"])
    if FORMATS[p["child_table"]] in ("csv", "jsonl"):     # rows quarantined at ingestion still exist as records
        child = child.unionByName(d.quarantine(p["child_table"]).select(p["join_column"], p["child_key"]))
    n_child = child.distinct().groupBy(p["join_column"]).agg(F.count("*").alias("_children"))
    df = (d.table(rule["table"]).join(n_child, p["join_column"], "left")
          .withColumn("_children", F.coalesce("_children", F.lit(0)))
          .withColumn("_missing", F.col(p["count_column"]) - F.col("_children")))
    bad = df.filter(F.col("_missing") > 0)
    return _violations(bad, rule, p["count_column"],
                       F.concat(F.col(p["count_column"]).cast("string"), F.lit(" counted vs "),
                                F.col("_children").cast("string"), F.lit(" records")), F.col("_missing"))


def check_overlapping_intervals(d: DQData, rule, P):
    """Within one group (e.g. one smart card), an interval that starts before an earlier one has ended.

    Rows are ordered by start time, then primary key. The LATER row is reported; observed_value is
    the overlap in seconds against the latest end time of all earlier rows in the group (so a long
    earlier journey still counts, not only the immediately previous one).
    """
    p, t = rule["params"], rule["table"]
    w = (Window.partitionBy(p["group_by"]).orderBy(p["start"], *primary_key(t))
         .rowsBetween(Window.unboundedPreceding, -1))
    df = (d.table(t).filter(F.col(p["group_by"]).isNotNull() & F.col(p["start"]).isNotNull())
          .withColumn("_prev_end", F.max(p["end"]).over(w)))
    overlap = F.unix_timestamp("_prev_end") - F.unix_timestamp(p["start"])
    bad = df.filter(overlap > P.get("overlap_tolerance_seconds", 0))
    return _violations(bad, rule, p["start"], overlap)


CHECKS = {
    "required_value": check_required_value, "foreign_key": check_foreign_key, "duplicate_key": check_duplicate_key,
    "non_negative": check_non_negative, "unparseable": check_unparseable, "time_gap": check_time_gap,
    "time_order": check_time_order, "capacity": check_capacity, "value_range": check_value_range,
    "sequence_integrity": check_sequence_integrity, "missing_parent": check_missing_parent,
    "timestamp_date_window": check_timestamp_date_window, "geo_bounds": check_geo_bounds,
    "count_vs_children": check_count_vs_children, "overlapping_intervals": check_overlapping_intervals,
}


def run_rule(d: DQData, rule: dict, P: dict) -> DataFrame:
    """Run one configured rule and return its violations."""
    if rule["check"] not in CHECKS:
        raise ValueError(f"{rule['id']}: unknown check type {rule['check']!r}")
    return CHECKS[rule["check"]](d, rule, P)
