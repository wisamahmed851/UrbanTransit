"""Controlled dirty-data injection + manifest.

Rules that make the manifest trustworthy:
* Every defect type is injected into its own, *disjoint* set of rows (a row gets
  at most one defect), chosen with a seeded random generator.
* Duplicates are copies of clean rows only.
* Clean simulated data never violates the detection rules below, so a check in
  Phase 3 that applies the same rule must find exactly the manifest count.
* The manifest is written OUTSIDE raw_data/ (data_generator/manifests/<mode>/),
  so the dataset itself carries no hint of what is wrong with it.

DETECTION_RULES below states, per defect, the rule that finds it; the same text
is written into the manifest and validate_dataset.py implements each rule.
"""

import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from .utils import make_rng

INVALID_TIMESTAMPS = ["2025-13-45 25:61:00", "31/02/2026 10:00", "0000-00-00 00:00:00",
                     "N/A", "2025-09-31 08:00:00", "1700000000"]
INVALID_DELAY_NUMBERS = [-999.0, 9999.0, 1440.5, -720.0]
INVALID_DELAY_TEXT = ["unknown", "n/a", "#VALUE!"]

DETECTION_RULES = {
    "missing_ticket_records": "passenger_counts.card_taps minus the number of distinct ticket_ids for that trip_id (summed over APC trips, only positive differences)",
    "missing_route_ids": "route_id is empty",
    "invalid_stop_ids": "stop id not present in stops.stop_id (tickets: entry_stop_id or exit_stop_id; delays: stop_id)",
    "duplicate_tickets": "rows minus distinct ticket_id",
    "duplicate_trips": "rows minus distinct trip_id",
    "negative_passenger_counts": "boardings < 0 or alightings < 0 or max_load < 0",
    "invalid_timestamps": "tickets.entry_time does not parse as YYYY-MM-DD HH:MM:SS",
    "impossible_arrival_times": "|delays.actual_arrival - scheduled_arrival| > 12 hours",
    "departure_before_arrival": "delays.actual_departure < actual_arrival",
    "vehicle_capacity_violations": "passenger_counts.max_load > 1.5 x vehicles.capacity_total (natural crush load is capped at 1.4x)",
    "invalid_delay_values": "delays.delay_minutes not numeric, or outside [-60, 600]",
    "missing_vehicle_assignments": "trips.vehicle_id is empty",
    "broken_stop_sequences": "a (route_id, direction) whose stop_sequence values are not exactly 1..n (gap or repeated number)",
    "invalid_route_distances": "routes.distance_km <= 0 or > 300",
    "unknown_passengers": "tickets.passenger_id not present in passengers.passenger_id",
    "missing_trip_records": "distinct trip_id referenced by passenger_counts/tickets/delays/gps_events but absent from trips",
    "unknown_vehicle_ids": "trips.vehicle_id not empty and not present in vehicles.vehicle_id",
    "future_timestamps": "tickets.entry_time parses but is after the dataset end date",
    "out_of_bounds_coordinates": "stop latitude/longitude outside the city box (lat 31.2-31.8, lon 74.0-74.6)",
    "negative_fares": "tickets.fare_amount < 0",
}


class DefectInjector:
    """Injects defects month by month and accumulates the manifest."""

    def __init__(self, cfg: dict, vehicles: pd.DataFrame):
        self.cfg = cfg
        self.rates = cfg["defects"]
        self.capacity = dict(zip(vehicles["vehicle_id"], vehicles["capacity_total"]))
        self.counts = defaultdict(int)            # (defect, table) -> rows affected
        self.orphans = defaultdict(int)           # child table -> rows pointing at removed trips
        self.details = defaultdict(dict)
        self.keys = []                            # (defect, table, key) for Phase 3 precision checks

    # ---------------------------------------------------------------- helpers
    def _n(self, name: str, pool_size: int) -> int:
        rate = self.rates.get(name, 0)
        if not rate or pool_size == 0:
            return 0
        return min(pool_size, max(1, int(round(rate * pool_size))))

    @staticmethod
    def _take(rng, candidates: np.ndarray, n: int, used: np.ndarray) -> np.ndarray:
        """Pick n row positions from candidates that are not used yet, and mark them used."""
        free = candidates[~used[candidates]]
        if n <= 0 or len(free) == 0:
            return np.array([], dtype=int)
        pick = np.sort(rng.choice(free, min(n, len(free)), replace=False))
        used[pick] = True
        return pick

    def _record(self, defect, table, keys):
        keys = list(keys)
        self.counts[(defect, table)] += len(keys)
        self.keys += [(defect, table, str(k)) for k in keys]

    # ---------------------------------------------------------------- reference tables (once)
    def inject_reference(self, stops: pd.DataFrame, routes: pd.DataFrame, route_stops: pd.DataFrame):
        rng = make_rng(self.cfg["seed"], "defects_ref")
        routes, route_stops, stops = routes.copy(), route_stops.copy(), stops.copy()

        # invalid route distances (absolute count of routes)
        n = min(int(self.rates.get("invalid_route_distances", 0)), len(routes))
        if n:
            idx = np.sort(rng.choice(len(routes), n, replace=False))
            variants = [lambda d: -d, lambda d: 0.0, lambda d: 9999.0]
            for j, i in enumerate(idx):
                routes.at[i, "distance_km"] = variants[j % 3](routes.at[i, "distance_km"])
            self._record("invalid_route_distances", "routes", routes.loc[idx, "route_id"])

        # broken stop sequences: a gap (row removed) or a repeated sequence number
        groups = route_stops[["route_id", "direction"]].drop_duplicates().to_numpy()
        n = self._n("broken_stop_sequences", len(groups))
        drop_rows, gap, dup = [], 0, 0
        if n:
            for j, g in enumerate(groups[np.sort(rng.choice(len(groups), n, replace=False))]):
                rows = route_stops.index[(route_stops.route_id == g[0]) & (route_stops.direction == g[1])].to_numpy()
                k = int(rng.integers(1, len(rows) - 1))          # a middle stop
                if j % 2 == 0:
                    drop_rows.append(rows[k]); gap += 1
                else:
                    route_stops.at[rows[k], "stop_sequence"] = route_stops.at[rows[k - 1], "stop_sequence"]; dup += 1
                self._record("broken_stop_sequences", "route_stops", [f"{g[0]}|{g[1]}"])
            route_stops = route_stops.drop(index=drop_rows).reset_index(drop=True)
        self.details["broken_stop_sequences"] = {"groups_with_gap": gap, "groups_with_repeated_sequence": dup,
                                                 "rows_removed": gap, "duplicate_pk_rows": dup}

        # hidden_like only: stops with impossible coordinates
        n = min(int(self.rates.get("out_of_bounds_coordinates", 0)), len(stops))
        if n:
            idx = np.sort(rng.choice(len(stops), n, replace=False))
            for j, i in enumerate(idx):
                if j % 2 == 0:
                    stops.at[i, "latitude"], stops.at[i, "longitude"] = 0.0, 0.0
                else:
                    stops.at[i, "latitude"], stops.at[i, "longitude"] = stops.at[i, "longitude"], stops.at[i, "latitude"]
            self._record("out_of_bounds_coordinates", "stops", stops.loc[idx, "stop_id"])
        return stops, routes, route_stops

    # ---------------------------------------------------------------- monthly event tables
    def inject_month(self, res, year: int, month: int, vehicle_ids: set):
        rng = make_rng(self.cfg["seed"], "defects", year, month)
        trips, pc, tickets, delays = res.trips.copy(), res.passenger_counts.copy(), res.tickets.copy(), res.delays.copy()
        apc = set(res.apc_trip_ids)

        # --- trips
        used_t = np.zeros(len(trips), dtype=bool)
        on_apc = trips["trip_id"].isin(apc).to_numpy() & (trips["trip_status"].to_numpy() == "completed")
        removed = self._take(rng, np.where(on_apc)[0], self._n("missing_trip_records", len(trips)), used_t)
        removed_ids = set(trips["trip_id"].to_numpy()[removed])
        all_t = np.arange(len(trips))
        i = self._take(rng, all_t, self._n("missing_route_ids_trips", len(trips)), used_t)
        trips.loc[i, "route_id"] = ""
        self._record("missing_route_ids", "trips", trips.loc[i, "trip_id"])
        no_swap = np.where(trips["original_vehicle_id"].to_numpy() == "")[0]
        i = self._take(rng, no_swap, self._n("missing_vehicle_assignments", len(trips)), used_t)
        trips.loc[i, "vehicle_id"] = ""
        self._record("missing_vehicle_assignments", "trips", trips.loc[i, "trip_id"])
        i = self._take(rng, all_t, self._n("unknown_vehicle_ids", len(trips)), used_t)
        if len(i):
            fake = [f"V9{int(x):03d}" for x in rng.integers(0, 1000, len(i))]
            assert not set(fake) & vehicle_ids
            trips.loc[i, "vehicle_id"] = fake
            self._record("unknown_vehicle_ids", "trips", trips.loc[i, "trip_id"])
        dup = self._take(rng, all_t, self._n("duplicate_trips", len(trips)), used_t)
        self._record("duplicate_trips", "trips", trips.loc[dup, "trip_id"])
        trips = self._with_duplicates(trips, dup)
        self._record("missing_trip_records", "trips", sorted(removed_ids))
        trips = trips[~trips["trip_id"].isin(removed_ids)].reset_index(drop=True)

        # --- passenger_counts
        used_p = pc["trip_id"].isin(removed_ids).to_numpy()          # keep orphans otherwise clean
        all_p = np.arange(len(pc))
        i = self._take(rng, all_p, self._n("negative_passenger_counts", len(pc)), used_p)
        which = rng.integers(0, 3, len(i))
        for col, w in (("boardings", 0), ("alightings", 1), ("max_load", 2)):
            sel = i[which == w]
            pc.loc[sel, col] = -rng.integers(1, 40, len(sel))
        self._record("negative_passenger_counts", "passenger_counts", pc.loc[i, "count_id"])
        i = self._take(rng, all_p, self._n("vehicle_capacity_violations", len(pc)), used_p)
        if len(i):
            cap = pc.loc[i, "vehicle_id"].map(self.capacity).to_numpy()
            pc.loc[i, "max_load"] = np.round(cap * rng.uniform(2.0, 3.5, len(i))).astype(int)
            self._record("vehicle_capacity_violations", "passenger_counts", pc.loc[i, "count_id"])

        # --- tickets: remove some (missing records), then field defects, then duplicates
        on_apc_t = tickets["trip_id"].isin(apc).to_numpy() & ~tickets["trip_id"].isin(removed_ids).to_numpy()
        used_k = np.zeros(len(tickets), dtype=bool)
        gone = self._take(rng, np.where(on_apc_t)[0], self._n("missing_ticket_records", len(tickets)), used_k)
        self._record("missing_ticket_records", "tickets", tickets.loc[gone, "ticket_id"])
        tickets = tickets.drop(index=gone).reset_index(drop=True)
        used_k = tickets["trip_id"].isin(removed_ids).to_numpy()
        all_k = np.arange(len(tickets))
        i = self._take(rng, all_k, self._n("missing_route_ids_tickets", len(tickets)), used_k)
        tickets.loc[i, "route_id"] = ""
        self._record("missing_route_ids", "tickets", tickets.loc[i, "ticket_id"])
        i = self._take(rng, all_k, self._n("invalid_stop_ids_tickets", len(tickets)), used_k)
        col = np.where(rng.random(len(i)) < 0.5, "entry_stop_id", "exit_stop_id")
        for c in ("entry_stop_id", "exit_stop_id"):
            sel = i[col == c]
            tickets.loc[sel, c] = [f"S9{int(x):03d}" for x in rng.integers(0, 1000, len(sel))]
        self._record("invalid_stop_ids", "tickets", tickets.loc[i, "ticket_id"])
        i = self._take(rng, all_k, self._n("invalid_timestamps", len(tickets)), used_k)
        tickets.loc[i, "entry_time"] = rng.choice(INVALID_TIMESTAMPS, len(i))
        self._record("invalid_timestamps", "tickets", tickets.loc[i, "ticket_id"])
        i = self._take(rng, all_k, self._n("unknown_passengers", len(tickets)), used_k)
        tickets.loc[i, "passenger_id"] = [f"P9{int(x):05d}" for x in rng.integers(0, 100000, len(i))]
        self._record("unknown_passengers", "tickets", tickets.loc[i, "ticket_id"])
        i = self._take(rng, all_k, self._n("future_timestamps", len(tickets)), used_k)
        if len(i):
            for c in ("entry_time", "exit_time"):
                tickets.loc[i, c] = [f"{int(s[:4]) + 1}{s[4:]}" for s in tickets.loc[i, c]]
            self._record("future_timestamps", "tickets", tickets.loc[i, "ticket_id"])
        i = self._take(rng, all_k, self._n("negative_fares", len(tickets)), used_k)
        if len(i):
            tickets.loc[i, "fare_amount"] = -(tickets.loc[i, "fare_amount"].abs() + 5.0)
            self._record("negative_fares", "tickets", tickets.loc[i, "ticket_id"])
        dup = self._take(rng, all_k, self._n("duplicate_tickets", len(tickets)), used_k)
        self._record("duplicate_tickets", "tickets", tickets.loc[dup, "ticket_id"])
        tickets = self._with_duplicates(tickets, dup)

        # --- delays
        delays["delay_minutes"] = delays["delay_minutes"].astype(object)
        used_d = delays["trip_id"].isin(removed_ids).to_numpy()
        all_d = np.arange(len(delays))
        i = self._take(rng, all_d, self._n("invalid_stop_ids_delays", len(delays)), used_d)
        delays.loc[i, "stop_id"] = [f"S9{int(x):03d}" for x in rng.integers(0, 1000, len(i))]
        self._record("invalid_stop_ids", "delays", delays.loc[i, "delay_id"])
        i = self._take(rng, all_d, self._n("impossible_arrival_times", len(delays)), used_d)
        if len(i):
            shift = np.array([pd.Timedelta(days=2), pd.Timedelta(days=-1), pd.Timedelta(days=36500)], dtype=object)[np.arange(len(i)) % 3]
            for c in ("actual_arrival", "actual_departure"):
                ts = pd.to_datetime(delays.loc[i, c], format="%Y-%m-%d %H:%M:%S")
                delays.loc[i, c] = [(t + s).strftime("%Y-%m-%d %H:%M:%S") for t, s in zip(ts, shift)]
            self._record("impossible_arrival_times", "delays", delays.loc[i, "delay_id"])
        i = self._take(rng, all_d, self._n("departure_before_arrival", len(delays)), used_d)
        if len(i):
            arr = pd.to_datetime(delays.loc[i, "actual_arrival"], format="%Y-%m-%d %H:%M:%S")
            back = pd.to_timedelta(rng.integers(60, 600, len(i)), unit="s")
            delays.loc[i, "actual_departure"] = (arr - back).dt.strftime("%Y-%m-%d %H:%M:%S").to_numpy()
            self._record("departure_before_arrival", "delays", delays.loc[i, "delay_id"])
        i = self._take(rng, all_d, self._n("invalid_delay_values", len(delays)), used_d)
        if len(i):
            # every third value is text (fails numeric parsing), the rest are out-of-range numbers
            vals = [INVALID_DELAY_TEXT[(j // 3) % 3] if j % 3 == 0 else INVALID_DELAY_NUMBERS[j % 4] for j in range(len(i))]
            delays.loc[i, "delay_minutes"] = vals
            self._record("invalid_delay_values", "delays", delays.loc[i, "delay_id"])

        # --- orphans created by removing trips (so Phase 3 FK checks know what to expect)
        self.orphans["passenger_counts"] += int(pc["trip_id"].isin(removed_ids).sum())
        self.orphans["tickets"] += int(tickets["trip_id"].isin(removed_ids).sum())
        self.orphans["delays"] += int(delays["trip_id"].isin(removed_ids).sum())
        gps = {}
        for day, g in res.gps.items():
            self.orphans["gps_events"] += int(g["trip_id"].isin(removed_ids).sum())
            gps[day] = g
        res.trips, res.passenger_counts, res.tickets, res.delays, res.gps = trips, pc, tickets, delays, gps
        return res

    @staticmethod
    def _with_duplicates(df: pd.DataFrame, rows: np.ndarray) -> pd.DataFrame:
        """Append exact copies of `rows` right after their originals (as a double-submitted record would)."""
        if len(rows) == 0:
            return df
        pos = np.concatenate([np.arange(len(df)), rows]).astype(float)
        pos[len(df):] += 0.5
        out = pd.concat([df, df.iloc[rows]], ignore_index=True)
        return out.iloc[np.argsort(pos, kind="stable")].reset_index(drop=True)

    # ---------------------------------------------------------------- manifest
    def write_manifest(self, out_dir: Path, extra: dict):
        out_dir.mkdir(parents=True, exist_ok=True)
        defects = []
        for (defect, table), rows in sorted(self.counts.items()):
            defects.append({"defect": defect, "table": table, "rows": rows,
                            "detection_rule": DETECTION_RULES[defect]})
        manifest = {
            "mode": self.cfg["mode"], "seed": self.cfg["seed"], "network_seed": self.cfg["network_seed"],
            "configured_rates": self.rates,
            "defects": defects,
            "defect_types_injected": sorted({d for d, _ in self.counts}),
            "missing_trip_records_orphans": dict(sorted(self.orphans.items())),
            "details": dict(self.details),
            **extra,
        }
        with open(out_dir / "injection_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        with gzip.open(out_dir / "injection_keys.jsonl.gz", "wt", encoding="utf-8") as f:
            for defect, table, key in self.keys:
                f.write(json.dumps({"defect": defect, "table": table, "key": key}) + "\n")
        return manifest
