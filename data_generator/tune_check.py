"""Dry-run helper for tuning: simulate a few months in memory (nothing written) and print realism metrics.

Usage: python -m data_generator.tune_check --months 2025-09 2026-07
Metrics: tickets/delays per month, occupancy categories, trip-level end delay by occupancy band
and peak/off-peak, share late > 5 min, headway bunching at the first and last stop.
"""

import argparse

import numpy as np
import pandas as pd

from .calendar_schedules import build_schedules, build_service_calendar
from .config import load_config
from .network import build_network, build_vehicles
from .passengers import build_passengers
from .simulation import build_context, simulate_month
from .utils import get_logger


def metrics(res, vehicles, routes) -> None:
    cap = res.passenger_counts.vehicle_id.map(vehicles.set_index("vehicle_id").capacity_total)
    pc = res.passenger_counts.assign(occ=res.passenger_counts.max_load / cap)
    t = res.trips[res.trips.trip_status == "completed"].copy()
    for c in ("scheduled_departure", "scheduled_arrival", "actual_departure", "actual_arrival"):
        t[c] = pd.to_datetime(t[c])
    t["end_delay"] = (t.actual_arrival - t.scheduled_arrival).dt.total_seconds() / 60
    t["hour"] = t.scheduled_departure.dt.hour
    j = t.merge(pc[["trip_id", "occ"]], on="trip_id")
    bands = pd.cut(j.occ, [0, 0.4, 0.7, 0.9, 1.1, 9], labels=["<0.4", "0.4-0.7", "0.7-0.9", "0.9-1.1", ">1.1"])
    occ_cat = pd.cut(pc.occ, [0, 0.4, 0.7, 0.9, 1.1, 9], labels=["Low", "Mod", "High", "Over", "Crit"],
                     include_lowest=True).value_counts(normalize=True).sort_index() * 100
    peak = j.hour.isin([7, 8, 9, 16, 17, 18])
    rtype = pc.route_id.map(routes.set_index("route_id").route_type)
    print("  occupancy %:", occ_cat.round(1).to_dict(), "| mean by route type:", pc.groupby(rtype).occ.mean().round(2).to_dict())
    print("  end delay mean by occupancy band:", j.groupby(bands, observed=True).end_delay.mean().round(2).to_dict())
    print(f"  end delay mean peak {j[peak].end_delay.mean():.2f} vs off-peak {j[~peak].end_delay.mean():.2f};"
          f" late>5min peak {(j[peak].end_delay > 5).mean() * 100:.1f}% vs off-peak {(j[~peak].end_delay > 5).mean() * 100:.1f}%")
    t = t.sort_values(["route_id", "direction", "service_date", "scheduled_departure"])
    g = t.groupby(["route_id", "direction", "service_date"])
    sch = g.scheduled_departure.diff().dt.total_seconds()
    for col in ("actual_departure", "actual_arrival"):
        r = (g[col].diff().dt.total_seconds() / sch).replace([np.inf, -np.inf], np.nan).dropna()
        print(f"  headway ratio at {col:17s}: CV {r.std() / r.mean():.2f}, bunched<0.5 {(r < 0.5).mean() * 100:.2f}%, gap>1.5 {(r > 1.5).mean() * 100:.2f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="+", default=["2025-09"])
    ap.add_argument("--mode", default="full")
    args = ap.parse_args()
    log = get_logger()
    cfg = load_config(args.mode)
    net = build_network(cfg); build_vehicles(cfg, net)
    cal = build_service_calendar(cfg); _, lookup = build_schedules(cfg, net, cal)
    _, hab = build_passengers(cfg, net)
    ctx = build_context(cfg, net, cal, lookup, hab)
    for ym in args.months:
        y, m = map(int, ym.split("-"))
        res = simulate_month(ctx, y, m, log)
        metrics(res, net.vehicles, net.routes)


if __name__ == "__main__":
    main()
