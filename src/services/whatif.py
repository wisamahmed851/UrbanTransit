"""What-if scenarios for one route, direction and departure hour (SRS steps 48-49, CMD-024).

Every result is an **estimate**, and the response says so. It starts from what was observed
in that cell over the recent weeks (`trip_context`), changes one thing, and recomputes:

| measure | how |
|---|---|
| trips per hour | 60 / median scheduled headway |
| peak load per trip | mean of each trip's highest on-board load (passengers) |
| demand per hour | peak load per trip x trips per hour; fixed unless the scenario changes demand |
| occupancy | peak load per trip / vehicle capacity, named with `occupancy_categories` in config/thresholds.yaml |
| waiting time | headway / 2 (passengers arriving at random) |
| capacity per hour | vehicle capacity x trips per hour |
| demand coverage | capacity per hour / demand per hour, capped at 100% |
| crowding risk, delay risk | the saved Phase 7 classifiers, re-run with the changed headway or hour |

The fixed-demand assumption means passengers spread evenly over the trips that run; a
real timetable change can also attract or lose riders, which this does not model.
The same scenario types were prototyped in `recommendation_engine/whatif_simulator.py`;
this service reads its baseline from MySQL instead of the 200 MB trip-feature Parquet.
"""

from dataclasses import asdict, dataclass
from datetime import date

from config import settings
from src.errors import ApiError
from src.services import model_serving as ms

SCENARIOS = {
    "increase_frequency": "Add trips per hour (`trips`, default 1)",
    "decrease_frequency": "Remove trips per hour (`trips`, default 1)",
    "add_vehicle": "One more vehicle in service in this hour, run as one extra trip per hour",
    "change_vehicle_capacity": "Run every trip with vehicles of `capacity` total places",
    "shift_trip_time": "Move the departure by `minutes` (-180..180); the trip is taken to leave at half past the hour",
    "remove_low_demand_trip": "Cancel one trip per hour; its riders move to the remaining trips",
    "increase_demand": "Demand grows by `percent` (-90..300)",
}


@dataclass
class State:
    hour: int
    headway_min: float
    trips_per_hour: float
    capacity_per_trip: float
    capacity_per_hour: float
    peak_load_per_trip: float
    demand_per_hour: float
    occupancy: float
    occupancy_category: str
    waiting_time_min: float
    demand_coverage: float
    crowding_probability: float | None
    delay_risk: float | None     # probability of a Moderate or Severe delay


def occupancy_category(ratio: float) -> str:
    for band in settings.load_thresholds()["occupancy_categories"]:
        if band["max_ratio"] is None or ratio <= band["max_ratio"]:
            return band["name"]
    return "Critical"


def model_risks(ctx, day: date, hour: int, headway: float) -> tuple[float | None, float | None]:
    """Both classifiers on the cell's typical trip, with the scenario's headway and hour."""
    crowd_row = {**ms.feature_row("crowding_flag", ctx, day), "hour": hour, "headway_min": headway}
    delay_row = {**ms.feature_row("delay_severity", ctx, day), "hour": hour, "headway_min": headway}
    crowd = ms.load_classifier("crowding_flag")
    delay = ms.load_classifier("delay_severity")
    p_crowd = float(ms.predict_proba("crowding_flag", [crowd_row])[0][crowd["labels"].index("1.0")])
    p_delay = ms.predict_proba("delay_severity", [delay_row])[0]
    p_late = float(sum(p_delay[delay["labels"].index(c)] for c in ("Moderate", "Severe")))
    return round(p_crowd, 4), round(p_late, 4)


def state(ctx, day: date, hour: int, trips_per_hour: float, capacity: float, demand_per_hour: float,
          risks: tuple[float | None, float | None]) -> State:
    headway = 60.0 / trips_per_hour
    load = demand_per_hour / trips_per_hour
    occ = load / capacity if capacity else 0.0
    cap_hour = capacity * trips_per_hour
    return State(hour=hour, headway_min=round(headway, 1), trips_per_hour=round(trips_per_hour, 2),
                 capacity_per_trip=capacity, capacity_per_hour=round(cap_hour, 1), peak_load_per_trip=round(load, 1),
                 demand_per_hour=round(demand_per_hour, 1), occupancy=round(occ, 3), occupancy_category=occupancy_category(occ),
                 waiting_time_min=round(headway / 2, 1),
                 demand_coverage=round(min(1.0, cap_hour / demand_per_hour), 3) if demand_per_hour else 1.0,
                 crowding_probability=risks[0], delay_risk=risks[1])


def _number(params: dict, name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(params.get(name, default))
    except (TypeError, ValueError):
        raise ApiError(400, "invalid_parameter", f"'{name}' must be a number.") from None
    if not low <= value <= high:
        raise ApiError(400, "invalid_parameter", f"'{name}' must be between {low:g} and {high:g}.")
    return value


def simulate(scenario: str, route_id: str, direction: int, day: date, hour: int, params: dict) -> dict:
    if scenario not in SCENARIOS:
        raise ApiError(400, "unsupported_scenario", f"Unknown scenario '{scenario}'.", {"supported": SCENARIOS})
    ctx = ms.find_context(route_id, direction, day, hour)
    if not ctx.headway_min or not ctx.capacity_total or ctx.mean_max_load is None:
        raise ApiError(422, "incomplete_baseline", "This cell lacks a headway, capacity or load observation.")

    trips = 60.0 / ctx.headway_min
    capacity = float(ctx.capacity_total)
    demand = float(ctx.mean_max_load) * trips
    before = state(ctx, day, hour, trips, capacity, demand, model_risks(ctx, day, hour, ctx.headway_min))

    new_hour, new_trips, new_capacity, new_demand, notes = hour, trips, capacity, demand, []
    if scenario == "increase_frequency":
        new_trips = trips + _number(params, "trips", 1, 1, 30)
    elif scenario == "add_vehicle":
        new_trips = trips + 1
        notes.append("Assumes the extra vehicle adds one trip in this hour.")
    elif scenario in ("decrease_frequency", "remove_low_demand_trip"):
        removed = 1 if scenario == "remove_low_demand_trip" else _number(params, "trips", 1, 1, 30)
        if trips - removed < 1:
            raise ApiError(422, "invalid_parameter", f"Only {trips:.1f} trips run per hour; at least one must remain.")
        new_trips = trips - removed
        if scenario == "remove_low_demand_trip":
            low = next(b["max_ratio"] for b in settings.load_thresholds()["occupancy_categories"] if b["name"] == "Low")
            notes.append(f"{ctx.mean_boardings or 0:.0f} passengers board the cancelled trip on average and must take another.")
            if before.occupancy > low:
                notes.append(f"Not a low-demand trip: occupancy {before.occupancy:.0%} is above the Low band ({low:.0%}).")
    elif scenario == "change_vehicle_capacity":
        new_capacity = _number(params, "capacity", capacity, 10, 300)
        notes.append("The crowding model has no capacity input, so its risk is unchanged; occupancy shows the effect.")
    elif scenario == "shift_trip_time":
        minutes = _number(params, "minutes", 30, -180, 180)
        new_hour = int((hour * 60 + 30 + minutes) // 60)
        if new_hour == hour:
            notes.append("The shift stays inside the same hour; the models see no difference.")
        else:
            target = ms.find_context(route_id, direction, day, new_hour)
            demand = float(target.mean_max_load or 0) * trips   # the passengers of the new hour
            notes.append(f"The trip now leaves in the {new_hour:02d}:00 hour and meets that hour's demand "
                         f"({target.mean_max_load or 0:.0f} peak-load passengers per trip observed).")
            new_demand = demand
    elif scenario == "increase_demand":
        new_demand = demand * (1 + _number(params, "percent", 10, -90, 300) / 100)
        notes.append("The models take no demand input, so crowding and delay risk are unchanged; occupancy shows the effect.")

    # A shifted trip takes the new hour's own history (the delay model uses route-hour inputs).
    after_ctx = ms.find_context(route_id, direction, day, new_hour) if new_hour != hour else ctx
    risks = model_risks(after_ctx, day, new_hour, 60.0 / new_trips)
    after = state(ctx, day, new_hour, new_trips, new_capacity, new_demand, risks)
    if (after.occupancy - before.occupancy) * (after.crowding_probability - before.crowding_probability) < 0:
        notes.append("The crowding model and the occupancy estimate move in opposite directions. The model learned "
                     "from differences between routes and hours (quieter routes tend to run less often), not from "
                     "timetable changes, so trust the occupancy estimate for this scenario.")
    b, a = asdict(before), asdict(after)
    changes = [{"measure": k, "before": b[k], "after": a[k],
                "change": round(a[k] - b[k], 4) if isinstance(b[k], (int, float)) and isinstance(a[k], (int, float)) else None}
               for k in b if b[k] != a[k]]
    return {
        "estimate": True, "label": "Simulated estimate, not observed data",
        "scenario": {"type": scenario, "description": SCENARIOS[scenario], "route_id": route_id, "direction": direction,
                     "service_date": day.isoformat(), "day_type": ms.day_type_of(day), "hour": hour, "params": params},
        "baseline": b, "result": a, "changes": changes, "notes": notes,
        "observed_window": f"{ctx.window_start}..{ctx.window_end}, {ctx.trips_observed} trips",
        "assumptions": ["Demand stays the same unless the scenario changes it; passengers spread evenly over the trips.",
                        "Waiting time = half the headway.",
                        "Crowding and delay risk come from the saved Phase 7 models (delay model below the SRS target)."],
    }
