"""Validate a generated dataset against the SRS minimums, its schemas and its injection manifest.

Usage (inside WSL, repo root, venv active):
    python -m data_generator.validate_dataset --mode full

What is checked
---------------
1. Files and row counts match the generator's run summary.
2. Volume minimums (full mode): tickets, passenger counts, delays, routes, stops, vehicles, passengers.
3. Date coverage: >= 12 months (full mode), several service calendars and timetable periods,
   and every service_date resolves to exactly the service_id written on the trip.
4. Primary keys unique - except the duplicates the manifest says were injected.
5. Foreign keys resolve - except the orphans/invalid references the manifest says were injected.
6. Every injected defect type is re-detected from the files with an independent rule and the
   count equals the manifest count exactly.

The validator only reads the CSV/JSON files (never the generator's memory), so it is the same
kind of check Phase 3 will run - here used to prove the manifest is accurate.
Memory: large tables are read one monthly file at a time, keeping only the columns needed.
"""

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from .calendar_schedules import active_service
from .schema_registry import load_schemas

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TS_FORMAT = "%Y-%m-%d %H:%M:%S"
FULL_MINIMUMS = {  # SRS volume requirements
    "tickets_rows": 2_400_000, "tickets_distinct_ids": 2_000_000, "passenger_counts": 600_000,
    "delays": 300_000, "routes": 110, "stops": 550, "vehicles": 270, "passengers": 55_000,
}
CITY_BOX = {"lat": (31.2, 31.8), "lon": (74.0, 74.6)}


class Report:
    """Collects PASS/FAIL lines and prints them as they happen."""

    def __init__(self):
        self.results = []

    def check(self, name: str, ok: bool, detail: str):
        self.results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)

    @property
    def ok(self) -> bool:
        return all(r["status"] == "PASS" for r in self.results)


def read_csv(path: Path, usecols=None) -> pd.DataFrame:
    """Read everything as text (empty stays ''), exactly as written - no type guessing."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, usecols=usecols)


def files(data: Path, table: str) -> list[Path]:
    return sorted((data / table).glob("*.csv")) + sorted((data / table).glob("*.jsonl"))


def parse_ts(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format=TS_FORMAT, errors="coerce")


def validate(mode: str, data: Path, manifest_path: Path, summary_path: Path) -> Report:
    rep = Report()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    schemas = load_schemas()
    expected = Counter()
    for d in manifest["defects"]:
        expected[(d["defect"], d["table"])] += d["rows"]
    orphans = manifest["missing_trip_records_orphans"]
    end_date = dt.date.fromisoformat(summary["end_date"])
    found = Counter()                              # (defect, table) -> rows detected

    # ------------------------------------------------------------------ reference tables
    stops = read_csv(data / "stops" / "stops.csv")
    routes = read_csv(data / "routes" / "routes.csv")
    route_stops = read_csv(data / "route_stops" / "route_stops.csv")
    vehicles = read_csv(data / "vehicles" / "vehicles.csv")
    passengers = read_csv(data / "passengers" / "passengers.csv")
    schedules = read_csv(data / "schedules" / "schedules.csv")
    calendar = json.loads((data / "service_calendar" / "service_calendar.json").read_text(encoding="utf-8"))
    stop_ids, route_ids = set(stops.stop_id), set(routes.route_id)
    vehicle_ids, passenger_ids = set(vehicles.vehicle_id), set(passengers.passenger_id)
    schedule_ids, service_ids = set(schedules.schedule_id), {s["service_id"] for s in calendar}
    capacity = dict(zip(vehicles.vehicle_id, vehicles.capacity_total.astype(int)))

    dist = pd.to_numeric(routes.distance_km)
    found[("invalid_route_distances", "routes")] = int(((dist <= 0) | (dist > 300)).sum())
    lat, lon = pd.to_numeric(stops.latitude), pd.to_numeric(stops.longitude)
    oob = ~lat.between(*CITY_BOX["lat"]) | ~lon.between(*CITY_BOX["lon"])
    found[("out_of_bounds_coordinates", "stops")] = int(oob.sum())
    broken = 0
    for _, g in route_stops.groupby(["route_id", "direction"]):
        seq = sorted(g.stop_sequence.astype(int))
        broken += seq != list(range(1, len(seq) + 1))
    found[("broken_stop_sequences", "route_stops")] = broken

    # ------------------------------------------------------------------ trips
    trip_ids_all, trip_rows = [], 0
    trip_service = []
    for f in files(data, "trips"):
        t = read_csv(f, ["trip_id", "route_id", "vehicle_id", "original_vehicle_id", "schedule_id", "service_id", "service_date"])
        trip_rows += len(t)
        trip_ids_all.append(t.trip_id.to_numpy())
        found[("missing_route_ids", "trips")] += int((t.route_id == "").sum())
        found[("missing_vehicle_assignments", "trips")] += int((t.vehicle_id == "").sum())
        found[("unknown_vehicle_ids", "trips")] += int(((t.vehicle_id != "") & ~t.vehicle_id.isin(vehicle_ids)).sum())
        fk_bad = int(((t.route_id != "") & ~t.route_id.isin(route_ids)).sum()
                     + (~t.schedule_id.isin(schedule_ids)).sum() + (~t.service_id.isin(service_ids)).sum()
                     + ((t.original_vehicle_id != "") & ~t.original_vehicle_id.isin(vehicle_ids)).sum())
        found[("_fk_other", "trips")] += fk_bad
        trip_service.append(t[["service_date", "service_id"]].drop_duplicates())
    trip_ids = np.concatenate(trip_ids_all)
    found[("duplicate_trips", "trips")] = trip_rows - len(np.unique(trip_ids))
    trip_set = set(trip_ids)

    # ------------------------------------------------------------------ passenger counts
    pc_rows, pc_ids, card_taps = 0, [], []
    for f in files(data, "passenger_counts"):
        p = read_csv(f, ["count_id", "trip_id", "route_id", "vehicle_id", "boardings", "alightings",
                         "max_load", "max_load_stop_id", "card_taps"])
        pc_rows += len(p)
        pc_ids.append(p.count_id.to_numpy())
        b, a, m = (p[c].astype(int) for c in ("boardings", "alightings", "max_load"))
        found[("negative_passenger_counts", "passenger_counts")] += int(((b < 0) | (a < 0) | (m < 0)).sum())
        cap = p.vehicle_id.map(capacity)
        found[("vehicle_capacity_violations", "passenger_counts")] += int((m > 1.5 * cap).sum())
        found[("_orphans", "passenger_counts")] += int((~p.trip_id.isin(trip_set)).sum())
        found[("_fk_other", "passenger_counts")] += int((~p.route_id.isin(route_ids)).sum()
                                                        + (~p.vehicle_id.isin(vehicle_ids)).sum()
                                                        + (~p.max_load_stop_id.isin(stop_ids)).sum())
        card_taps.append(p[["trip_id", "card_taps"]])
    card_taps = pd.concat(card_taps)
    card_taps["card_taps"] = card_taps.card_taps.astype(int)
    pc_ids = np.concatenate(pc_ids)

    # ------------------------------------------------------------------ tickets
    tk_rows, tk_ids, per_trip = 0, [], []
    for f in files(data, "tickets"):
        k = read_csv(f, ["ticket_id", "passenger_id", "trip_id", "route_id", "entry_stop_id", "exit_stop_id",
                         "entry_time", "fare_amount"])
        tk_rows += len(k)
        tk_ids.append(k.ticket_id.to_numpy())
        found[("missing_route_ids", "tickets")] += int((k.route_id == "").sum())
        found[("_fk_other", "tickets")] += int(((k.route_id != "") & ~k.route_id.isin(route_ids)).sum())
        bad_stop = ~k.entry_stop_id.isin(stop_ids) | ~k.exit_stop_id.isin(stop_ids)
        found[("invalid_stop_ids", "tickets")] += int(bad_stop.sum())
        ts = parse_ts(k.entry_time)
        found[("invalid_timestamps", "tickets")] += int(ts.isna().sum())
        found[("future_timestamps", "tickets")] += int((ts > pd.Timestamp(end_date + dt.timedelta(days=2))).sum())
        found[("unknown_passengers", "tickets")] += int((~k.passenger_id.isin(passenger_ids)).sum())
        found[("negative_fares", "tickets")] += int((pd.to_numeric(k.fare_amount) < 0).sum())
        found[("_orphans", "tickets")] += int((~k.trip_id.isin(trip_set)).sum())
        per_trip.append(k.drop_duplicates("ticket_id").groupby("trip_id").size())
    tk_ids = np.concatenate(tk_ids)
    n_distinct_tickets = len(np.unique(tk_ids))
    found[("duplicate_tickets", "tickets")] = tk_rows - n_distinct_tickets
    per_trip = pd.concat(per_trip).groupby(level=0).sum()
    taps = card_taps.drop_duplicates("trip_id").set_index("trip_id").card_taps
    diff = taps - per_trip.reindex(taps.index, fill_value=0)
    found[("missing_ticket_records", "tickets")] = int(diff.clip(lower=0).sum())

    # ------------------------------------------------------------------ delays
    dl_rows, dl_ids = 0, []
    for f in files(data, "delays"):
        d = read_csv(f, ["delay_id", "trip_id", "route_id", "stop_id", "scheduled_arrival", "actual_arrival",
                         "actual_departure", "delay_minutes"])
        dl_rows += len(d)
        dl_ids.append(d.delay_id.to_numpy())
        found[("invalid_stop_ids", "delays")] += int((~d.stop_id.isin(stop_ids)).sum())
        s_arr, a_arr, a_dep = parse_ts(d.scheduled_arrival), parse_ts(d.actual_arrival), parse_ts(d.actual_departure)
        gap_hours = (a_arr - s_arr).dt.total_seconds().abs() / 3600
        found[("impossible_arrival_times", "delays")] += int((gap_hours > 12).sum())
        found[("departure_before_arrival", "delays")] += int((a_dep < a_arr).sum())
        val = pd.to_numeric(d.delay_minutes, errors="coerce")
        found[("invalid_delay_values", "delays")] += int((val.isna() | (val < -60) | (val > 600)).sum())
        found[("_orphans", "delays")] += int((~d.trip_id.isin(trip_set)).sum())
        found[("_fk_other", "delays")] += int((~d.route_id.isin(route_ids)).sum())
    dl_ids = np.concatenate(dl_ids)

    # ------------------------------------------------------------------ gps events
    gps_rows, gps_ids, gps_trip_refs = 0, [], set()
    for f in files(data, "gps_events"):
        g = pd.read_json(f, lines=True, dtype=False)
        gps_rows += len(g)
        gps_ids.append(g.event_id.to_numpy())
        found[("_orphans", "gps_events")] += int((~g.trip_id.isin(trip_set)).sum())
        found[("_fk_other", "gps_events")] += int((~g.vehicle_id.isin(vehicle_ids)).sum() + (~g.route_id.isin(route_ids)).sum()
                                                  + (g.stop_id.notna() & ~g.stop_id.isin(stop_ids)).sum())
        gps_trip_refs |= set(g.trip_id[~g.trip_id.isin(trip_set)])

    # distinct trips referenced by children but missing from trips
    child_trips = set(card_taps.trip_id[~card_taps.trip_id.isin(trip_set)]) | gps_trip_refs
    for f in files(data, "tickets"):
        k = read_csv(f, ["trip_id"]); child_trips |= set(k.trip_id[~k.trip_id.isin(trip_set)])
    for f in files(data, "delays"):
        d = read_csv(f, ["trip_id"]); child_trips |= set(d.trip_id[~d.trip_id.isin(trip_set)])
    found[("missing_trip_records", "trips")] = len(child_trips)

    # ================================================================== checks
    counts = {"stops": len(stops), "routes": len(routes), "route_stops": len(route_stops), "vehicles": len(vehicles),
              "passengers": len(passengers), "schedules": len(schedules), "service_calendar": len(calendar),
              "trips": trip_rows, "passenger_counts": pc_rows, "tickets": tk_rows, "delays": dl_rows, "gps_events": gps_rows}
    rep.check("row counts match generation summary", counts == summary["row_counts"],
              f"files={counts}")

    # volumes
    if mode == "full":
        actual = {"tickets_rows": tk_rows, "tickets_distinct_ids": n_distinct_tickets, "passenger_counts": pc_rows,
                  "delays": dl_rows, "routes": len(routes), "stops": len(stops), "vehicles": len(vehicles),
                  "passengers": len(passengers)}
        for key, minimum in FULL_MINIMUMS.items():
            rep.check(f"volume {key} >= {minimum:,}", actual[key] >= minimum, f"actual {actual[key]:,}")
    else:
        rep.check("volumes (reported only outside full mode)", True,
                  f"tickets={tk_rows:,} distinct={n_distinct_tickets:,} pc={pc_rows:,} delays={dl_rows:,}")

    # dates and calendars
    ts = pd.concat(trip_service).drop_duplicates()
    dates = pd.to_datetime(ts.service_date)
    span_days = (dates.max() - dates.min()).days + 1
    months = dates.dt.to_period("M").nunique()
    if mode == "full":
        rep.check("date coverage >= 12 months", span_days >= 365 and months >= 12,
                  f"{dates.min().date()}..{dates.max().date()} = {span_days} days, {months} calendar months")
    else:
        rep.check("date coverage (reported)", True, f"{dates.min().date()}..{dates.max().date()} = {span_days} days")
    periods = {s["timetable_period"] for s in calendar}
    rep.check("multiple service calendars and timetable periods", len(calendar) >= 2 and schedules.valid_from.nunique() >= 2,
              f"{len(calendar)} service calendars, periods={sorted(periods)}, {len(schedules):,} schedule rows")
    mismatch = sum(active_service(calendar, d.date())["service_id"] != sid
                   for d, sid in zip(pd.to_datetime(ts.service_date), ts.service_id))
    rep.check("each service_date resolves to the trip's service_id", mismatch == 0,
              f"{ts.service_date.nunique()} dates checked, {mismatch} mismatches")

    # primary keys
    dup_expected = {"trips": expected[("duplicate_trips", "trips")], "tickets": expected[("duplicate_tickets", "tickets")],
                    "route_stops": manifest["details"].get("broken_stop_sequences", {}).get("duplicate_pk_rows", 0)}
    pk_found = {
        "stops": len(stops) - stops.stop_id.nunique(), "routes": len(routes) - routes.route_id.nunique(),
        "route_stops": int(route_stops.duplicated(["route_id", "direction", "stop_sequence"]).sum()),
        "vehicles": len(vehicles) - vehicles.vehicle_id.nunique(),
        "passengers": len(passengers) - passengers.passenger_id.nunique(),
        "schedules": len(schedules) - schedules.schedule_id.nunique(),
        "service_calendar": len(calendar) - len(service_ids),
        "trips": found[("duplicate_trips", "trips")], "passenger_counts": len(pc_ids) - len(np.unique(pc_ids)),
        "tickets": found[("duplicate_tickets", "tickets")], "delays": len(dl_ids) - len(np.unique(dl_ids)),
        "gps_events": gps_rows - len(np.unique(np.concatenate(gps_ids))) if gps_ids else 0,
    }
    for table in schemas:
        exp = dup_expected.get(table, 0)
        rep.check(f"PK unique: {table} ({', '.join(schemas[table]['primary_key'])})", pk_found[table] == exp,
                  f"duplicate rows found={pk_found[table]:,}, injected={exp:,}")

    # foreign keys
    fk_checks = [
        ("tickets -> trips (trip_id)", found[("_orphans", "tickets")], orphans.get("tickets", 0)),
        ("passenger_counts -> trips (trip_id)", found[("_orphans", "passenger_counts")], orphans.get("passenger_counts", 0)),
        ("delays -> trips (trip_id)", found[("_orphans", "delays")], orphans.get("delays", 0)),
        ("gps_events -> trips (trip_id)", found[("_orphans", "gps_events")], orphans.get("gps_events", 0)),
        ("tickets -> passengers (passenger_id)", found[("unknown_passengers", "tickets")], expected[("unknown_passengers", "tickets")]),
        ("tickets -> stops (entry/exit_stop_id)", found[("invalid_stop_ids", "tickets")], expected[("invalid_stop_ids", "tickets")]),
        ("delays -> stops (stop_id)", found[("invalid_stop_ids", "delays")], expected[("invalid_stop_ids", "delays")]),
        ("trips -> vehicles (vehicle_id)", found[("unknown_vehicle_ids", "trips")], expected[("unknown_vehicle_ids", "trips")]),
        ("trips other FKs (route, schedule, service, original_vehicle)", found[("_fk_other", "trips")], 0),
        ("passenger_counts other FKs (route, vehicle, max_load_stop)", found[("_fk_other", "passenger_counts")], 0),
        ("tickets -> routes (non-empty route_id)", found[("_fk_other", "tickets")], 0),
        ("delays -> routes", found[("_fk_other", "delays")], 0),
        ("gps_events other FKs (vehicle, route, stop)", found[("_fk_other", "gps_events")], 0),
        ("route_stops -> routes/stops", int((~route_stops.route_id.isin(route_ids)).sum() + (~route_stops.stop_id.isin(stop_ids)).sum()), 0),
        ("routes -> stops (origin/destination)", int((~routes.origin_stop_id.isin(stop_ids)).sum() + (~routes.destination_stop_id.isin(stop_ids)).sum()), 0),
        ("schedules -> routes/service_calendar", int((~schedules.route_id.isin(route_ids)).sum() + (~schedules.service_id.isin(service_ids)).sum()), 0),
        ("passengers -> stops (home_stop_id)", int((~passengers.home_stop_id.isin(stop_ids)).sum()), 0),
    ]
    for name, got, exp in fk_checks:
        rep.check(f"FK {name}", got == exp, f"violations found={got:,}, expected from manifest={exp:,}")

    # defects: every manifest entry re-detected with the same count, and nothing unexpected
    for (defect, table), exp in sorted(expected.items()):
        got = found[(defect, table)]
        rep.check(f"defect {defect} [{table}]", got == exp, f"detected={got:,}, manifest={exp:,}")
    for (defect, table), got in sorted(found.items()):
        if not defect.startswith("_") and (defect, table) not in expected and got:
            rep.check(f"no unexpected {defect} [{table}]", False, f"detected {got:,} but none injected")
    return rep


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a generated UrbanTransit IQ dataset")
    parser.add_argument("--mode", required=True, choices=["full", "sample", "hidden_like"])
    parser.add_argument("--data", type=Path)
    args = parser.parse_args()
    data = args.data or PROJECT_ROOT / "raw_data" / args.mode
    mdir = PROJECT_ROOT / "data_generator" / "manifests" / args.mode
    print(f"Validating {data} against {mdir / 'injection_manifest.json'}")
    rep = validate(args.mode, data, mdir / "injection_manifest.json", mdir / "generation_summary.json")
    n_fail = sum(r["status"] == "FAIL" for r in rep.results)
    print(f"\nRESULT: {'PASS' if rep.ok else 'FAIL'} ({len(rep.results) - n_fail} passed, {n_fail} failed)")
    (mdir / "validation_report.json").write_text(json.dumps(
        {"mode": args.mode, "result": "PASS" if rep.ok else "FAIL", "checks": rep.results}, indent=2), encoding="utf-8")
    sys.exit(0 if rep.ok else 1)


if __name__ == "__main__":
    main()
