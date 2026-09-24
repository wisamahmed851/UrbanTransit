"""Command-line entry point for the UrbanTransit IQ dataset generator.

Usage (inside WSL, from the repository root, venv active):
    python -m data_generator.generate --mode full
    python -m data_generator.generate --mode sample --publish-sample
    python -m data_generator.generate --mode hidden_like

Laravel analogy: this is `php artisan db:seed --class=...` - one command that
runs the seeders (network, calendar, passengers, monthly simulation) in order.

Flow:
  1. build the city (stops, routes, route_stops, fleet), calendars, schedules, passengers
  2. inject reference-table defects, write reference tables
  3. for each month: simulate -> inject defects -> write monthly files -> free memory
  4. write the injection manifest and a run summary to data_generator/manifests/<mode>/
Memory stays low because only one month of events is held at a time.
"""

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

import pandas as pd

from .calendar_schedules import build_schedules, build_service_calendar
from .config import MODES, load_config
from .defects import DefectInjector
from .network import build_network, build_vehicles
from .passengers import build_passengers
from .simulation import build_context, simulate_month
from .utils import get_logger, month_range
from .writers import write_csv, write_json, write_jsonl

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _dir_summary(root: Path) -> dict:
    """Per-file size and SHA-256 (used for the determinism check)."""
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            files[str(p.relative_to(root)).replace("\\", "/")] = {
                "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
    return files


def generate(mode: str, out_dir: Path, manifest_dir: Path, seed: int | None = None) -> dict:
    log = get_logger()
    t0 = time.time()
    cfg = load_config(mode)
    if seed is not None:
        cfg["seed"] = seed
    log.info(f"mode={mode} seed={cfg['seed']} network_seed={cfg['network_seed']} "
             f"dates={cfg['start_date']}..{cfg['end_date']} out={out_dir}")
    if out_dir.exists():
        shutil.rmtree(out_dir)                  # generated data only: always start from an empty folder
    out_dir.mkdir(parents=True)

    # 1) network, fleet, calendars, schedules, passengers
    net = build_network(cfg)
    build_vehicles(cfg, net)
    calendar = build_service_calendar(cfg)
    schedule_rows, lookup = build_schedules(cfg, net, calendar)
    passengers, habits = build_passengers(cfg, net)
    log.info(f"network: {len(net.stops)} stops, {len(net.routes)} routes, {len(net.vehicles)} vehicles, "
             f"{len(calendar)} service calendars, {len(schedule_rows)} schedules, {len(passengers)} passengers")

    # 2) reference tables (+ reference defects)
    injector = DefectInjector(cfg, net.vehicles)
    stops, routes, route_stops = injector.inject_reference(net.stops, net.routes, net.route_stops)
    counts = {
        "stops": write_csv(stops, out_dir / "stops" / "stops.csv", "stops"),
        "routes": write_csv(routes, out_dir / "routes" / "routes.csv", "routes"),
        "route_stops": write_csv(route_stops, out_dir / "route_stops" / "route_stops.csv", "route_stops"),
        "vehicles": write_csv(net.vehicles, out_dir / "vehicles" / "vehicles.csv", "vehicles"),
        "passengers": write_csv(passengers, out_dir / "passengers" / "passengers.csv", "passengers"),
        "schedules": write_csv(pd.DataFrame(schedule_rows), out_dir / "schedules" / "schedules.csv", "schedules"),
        "service_calendar": write_json(calendar, out_dir / "service_calendar" / "service_calendar.json"),
        "trips": 0, "passenger_counts": 0, "tickets": 0, "delays": 0, "gps_events": 0,
    }

    # 3) month by month: simulate, inject, write
    ctx = build_context(cfg, net, calendar, lookup, habits)
    vehicle_ids = set(net.vehicles["vehicle_id"])
    for year, month in month_range(cfg["start_date"], cfg["end_date"]):
        tm = time.time()
        res = simulate_month(ctx, year, month, log)
        res = injector.inject_month(res, year, month, vehicle_ids)
        tag = f"{year}-{month:02d}"
        counts["trips"] += write_csv(res.trips, out_dir / "trips" / f"trips_{tag}.csv", "trips")
        counts["passenger_counts"] += write_csv(res.passenger_counts, out_dir / "passenger_counts" / f"passenger_counts_{tag}.csv", "passenger_counts")
        counts["tickets"] += write_csv(res.tickets, out_dir / "tickets" / f"tickets_{tag}.csv", "tickets")
        counts["delays"] += write_csv(res.delays, out_dir / "delays" / f"delays_{tag}.csv", "delays")
        for day, g in res.gps.items():
            counts["gps_events"] += write_jsonl(g, out_dir / "gps_events" / f"gps_events_{day}.jsonl", "gps_events")
        log.info(f"{tag}: written with defects in {time.time() - tm:.1f}s "
                 f"(running totals: tickets={counts['tickets']:,} pc={counts['passenger_counts']:,} delays={counts['delays']:,})")
        del res

    # 4) manifest + run summary (outside the dataset folder)
    files = _dir_summary(out_dir)
    manifest = injector.write_manifest(manifest_dir, {"row_counts": counts})
    summary = {
        "mode": mode, "seed": cfg["seed"], "network_seed": cfg["network_seed"],
        "start_date": cfg["start_date"].isoformat(), "end_date": cfg["end_date"].isoformat(),
        "output_dir": str(out_dir.relative_to(PROJECT_ROOT)) if out_dir.is_relative_to(PROJECT_ROOT) else str(out_dir),
        "row_counts": counts, "files": len(files),
        "total_bytes": sum(f["bytes"] for f in files.values()),
        "elapsed_seconds": round(time.time() - t0, 1),
        "defect_types_injected": manifest["defect_types_injected"],
    }
    with open(manifest_dir / "generation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(manifest_dir / "file_checksums.json", "w", encoding="utf-8") as f:
        json.dump(files, f, indent=2)
    log.info(f"done in {summary['elapsed_seconds']}s: {summary['files']} files, "
             f"{summary['total_bytes'] / 1e6:.1f} MB, rows={counts}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the UrbanTransit IQ synthetic dataset")
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--out", type=Path, help="output folder (default raw_data/<mode>)")
    parser.add_argument("--manifest-dir", type=Path, help="default data_generator/manifests/<mode>")
    parser.add_argument("--seed", type=int, help="override the simulation seed")
    parser.add_argument("--publish-sample", action="store_true",
                        help="sample mode: also copy the files to sample_data/ (committed to Git)")
    args = parser.parse_args()

    out = args.out or PROJECT_ROOT / "raw_data" / args.mode
    manifest_dir = args.manifest_dir or PROJECT_ROOT / "data_generator" / "manifests" / args.mode
    generate(args.mode, out.resolve(), manifest_dir.resolve(), args.seed)

    if args.publish_sample:
        if args.mode != "sample":
            raise SystemExit("--publish-sample only works with --mode sample")
        target = PROJECT_ROOT / "sample_data"
        for p in target.iterdir():
            if p.name != ".gitkeep":
                shutil.rmtree(p) if p.is_dir() else p.unlink()
        shutil.copytree(out, target, dirs_exist_ok=True)
        get_logger().info(f"sample published to {target}")


if __name__ == "__main__":
    main()
