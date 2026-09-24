"""Simulate first, derive second.

For every month we:
1. expand the timetable into planned trips (plus extra trips for special events),
2. compute each trip's passenger arrival rate (peak hours, weekday/weekend,
   season, holidays, weather, events) and its "static" delay drivers
   (traffic, bottleneck junctions, fog/rain, road works, events, breakdowns),
3. run the trips of each route-day in time order through a small operations
   model: vehicles are taken from the route's pool, a late vehicle starts its
   next trip late (propagation), the gap since the previous bus decides how many
   people are waiting (so a late bus gets fuller and slower, the one behind it
   emptier and faster -> irregular headways and bunching), full buses leave
   people behind, heavy boarding adds dwell time,
4. derive the output tables from that single simulated state:
   trips, passenger_counts (APC), tickets (card taps), delays (stop level) and
   gps_events (positions), so all tables agree with each other.

Laravel analogy: this is the "factory" layer, but instead of each factory
inventing its own random rows, one simulation produces the facts and every
table is a projection of those facts.
"""

import datetime as dt
import heapq
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .calendar_schedules import PERIODS, active_service, departures_for
from .passengers import FARE_DISCOUNT, TICKET_TYPES, PassengerSampler
from .utils import date_range, make_rng, minutes_to_timestamps

# --------------------------------------------------------------------------
# Demand shape
# --------------------------------------------------------------------------
# Hourly demand multipliers (index = hour 0..23).
P_WK_IN = np.array([0, 0, 0, 0, 0, 0.3, 0.9, 2.2, 2.6, 1.8, 1.0, 0.9, 0.95, 1.0, 1.0, 1.1, 1.2, 1.3, 1.1, 0.8, 0.6, 0.45, 0.3, 0.2])
P_WK_OUT = np.array([0, 0, 0, 0, 0, 0.2, 0.5, 0.9, 1.0, 0.9, 0.9, 0.9, 1.0, 1.1, 1.3, 1.6, 2.2, 2.6, 2.2, 1.4, 0.9, 0.6, 0.4, 0.2])
P_SAT = np.array([0, 0, 0, 0, 0, 0.2, 0.4, 0.7, 0.9, 1.0, 1.2, 1.3, 1.3, 1.3, 1.3, 1.3, 1.4, 1.4, 1.3, 1.2, 1.0, 0.8, 0.5, 0.3])
P_SUN = np.array([0, 0, 0, 0, 0, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.2, 1.2, 1.2, 1.3, 1.4, 1.5, 1.5, 1.4, 1.2, 0.9, 0.6, 0.3])
P_RAM_IN = np.array([0, 0, 0, 0, 0, 0.2, 0.4, 0.8, 1.6, 2.3, 1.8, 1.0, 0.9, 1.0, 1.4, 1.6, 1.4, 0.8, 0.2, 0.4, 0.9, 1.1, 0.9, 0.4])
P_RAM_OUT = np.array([0, 0, 0, 0, 0, 0.1, 0.3, 0.5, 0.8, 0.9, 0.9, 0.9, 1.0, 1.3, 2.0, 2.5, 2.3, 1.3, 0.2, 0.4, 0.9, 1.2, 1.0, 0.5])
MONTH_FACTOR = {9: 1.00, 10: 1.05, 11: 1.06, 12: 0.97, 1: 0.92, 2: 1.00, 3: 0.93, 4: 1.02, 5: 0.95, 6: 0.80, 7: 0.76, 8: 0.84}
DOW_FACTOR = np.array([1.06, 1.02, 1.00, 1.00, 0.93, 0.78, 0.58])
HOLIDAY_FACTOR, EID_FACTOR = 0.45, 0.30
DAY_TYPE_CODE = {"weekday": 0, "saturday": 1, "sunday": 2, "holiday": 3, "ramadan_weekday": 4}

# Mean (actual / planned running time) per period, weekday vs weekend.
CONG_MU_WEEKDAY = np.array([0.93, 1.02, 0.97, 1.03, 0.95])
CONG_MU_WEEKEND = np.array([0.90, 0.95, 0.97, 1.00, 0.94])

DELAY_REASONS = ["late_vehicle", "traffic_congestion", "junction_bottleneck", "passenger_boarding",
                 "weather_fog", "weather_rain", "special_event", "road_works", "vehicle_breakdown", "disruption"]


# --------------------------------------------------------------------------
# Context shared by all months
# --------------------------------------------------------------------------

@dataclass
class Scenario:
    """Dated disruptions and events for the whole period (drawn once from the seed)."""
    fog: set
    rain: set
    heat: set
    shortage: set
    protest: dict          # date -> boolean mask of affected routes
    spike: set
    roadworks: dict        # route idx -> (start, end)
    events: list           # dicts: date, start, end, mult, name, routes (bool mask)
    holidays: set
    eid: set


def _pick_dates(rng, candidates, k):
    candidates = sorted(candidates)
    if not candidates or k <= 0:
        return set()
    k = min(k, len(candidates))
    return {candidates[i] for i in sorted(rng.choice(len(candidates), k, replace=False))}


def build_scenario(cfg: dict, net) -> Scenario:
    """Draw weather days, disruptions, road works and resolve special events to routes."""
    rng = make_rng(cfg["seed"], "weather")
    days = date_range(cfg["start_date"], cfg["end_date"])

    def window(m1, d1, m2, d2):
        out = []
        for d in days:
            key = (d.month, d.day)
            if (m1, d1) <= (m2, d2):
                ok = (m1, d1) <= key <= (m2, d2)
            else:                                   # window across new year (Dec -> Feb)
                ok = key >= (m1, d1) or key <= (m2, d2)
            if ok:
                out.append(d)
        return out

    w, dcfg = cfg["weather"], cfg["disruptions"]
    fog = _pick_dates(rng, window(12, 10, 2, 10), w["fog_days"])
    rain = _pick_dates(rng, window(7, 1, 8, 31), w["rain_days"])
    heat = _pick_dates(rng, window(5, 20, 6, 20), w["heat_days"])
    shortage = _pick_dates(rng, days, dcfg["driver_shortage_days"])
    n_routes = len(net.routes)
    protest = {d: rng.random(n_routes) < 0.3
               for d in sorted(_pick_dates(rng, [d for d in days if d.weekday() < 5], dcfg["protest_days"]))}
    spike = _pick_dates(rng, [d for d in days if d.weekday() < 5], cfg.get("delay_spike_days", 0))
    roadworks = {}
    for r in sorted(rng.choice(n_routes, min(dcfg["road_works"], n_routes), replace=False)):
        start = days[int(rng.integers(0, max(1, len(days) - 20)))]
        roadworks[int(r)] = (start, start + dt.timedelta(days=int(rng.integers(28, 57))))

    # events: routes with a stop within 1 km of the venue hub
    from .network import HUBS
    events = []
    for ev in cfg["events"]:
        d = dt.date.fromisoformat(str(ev["date"]))
        if not (cfg["start_date"] <= d <= cfg["end_date"]):
            continue
        venue = next(h for h in HUBS if h[0] == ev["venue"])
        mask = np.zeros(n_routes, dtype=bool)
        for r, sl in enumerate(net.route_stop_idx):
            dist = np.hypot((net.stop_lat_all[sl] - venue[1]) * 110.57,
                            (net.stop_lon_all[sl] - venue[2]) * 111.32 * math.cos(math.radians(venue[1])))
            mask[r] = dist.min() < 1.0
        hh, mm = map(int, ev["start"].split(":")); start = hh * 60 + mm
        hh, mm = map(int, ev["end"].split(":")); end = hh * 60 + mm
        events.append({"date": d, "start": start, "end": end, "mult": float(ev["multiplier"]),
                       "name": ev["name"], "routes": mask})
    holidays = {dt.date.fromisoformat(str(h[0])) for h in cfg["calendar"]["holidays"]}
    eid = {dt.date.fromisoformat(str(x)) for x in cfg["calendar"]["eid_days"]}
    return Scenario(fog, rain, heat, shortage, protest, spike, roadworks, events, holidays, eid)


class StopGeometry:
    """Flat arrays describing every (route, direction) stop list, for vectorised stop-level times.

    key = 2 * route_idx + direction. For stop k of a key:
      frac  = share of the route distance travelled (planned time is proportional)
      cumw  = share of the *excess* delay accumulated by stop k. Segments ending at a
              bottleneck junction weigh 6x, so delay builds up at those junctions.
    """

    def __init__(self, net):
        stop_ids, frac, cumw, dist, lat, lon, off, nst, kmax, bott = [], [], [], [], [], [], [], [], [], []
        pos = 0
        for r, sl in enumerate(net.route_stop_idx):
            cum = net.route_cum_km[r]
            for direction in (0, 1):
                order = sl if direction == 0 else sl[::-1]
                d = cum if direction == 0 else cum[-1] - cum[::-1]
                b = net.route_bottlenecks[r] if direction == 0 else net.route_bottlenecks[r][::-1]
                seg = np.diff(d)
                w = seg * np.where(b[1:], 6.0, 1.0)
                cw = np.concatenate([[0.0], np.cumsum(w) / w.sum()])
                off.append(pos); nst.append(len(order)); kmax.append(int(np.argmax(w)) + 1)
                stop_ids.append(net.stop_ids_all[order]); frac.append(d / d[-1]); cumw.append(cw)
                dist.append(d); lat.append(net.stop_lat_all[order]); lon.append(net.stop_lon_all[order])
                bott.append(int(b.sum()))
                pos += len(order)
        self.stop_id = np.concatenate(stop_ids)
        self.frac, self.cumw, self.dist = np.concatenate(frac), np.concatenate(cumw), np.concatenate(dist)
        self.lat, self.lon = np.concatenate(lat), np.concatenate(lon)
        self.off, self.nst, self.kmax = np.array(off), np.array(nst), np.array(kmax)
        self.n_bottleneck = np.array(bott)


@dataclass
class Context:
    cfg: dict
    net: object
    calendar: list
    lookup: dict
    scenario: Scenario
    geo: StopGeometry
    habits: object
    sampler: PassengerSampler
    veh_cap: np.ndarray
    veh_apc: np.ndarray
    veh_ids: np.ndarray
    route_cong: np.ndarray


def build_context(cfg, net, calendar, lookup, habits) -> Context:
    rng = make_rng(cfg["seed"], "trips", 0)
    return Context(cfg=cfg, net=net, calendar=calendar, lookup=lookup, scenario=build_scenario(cfg, net),
                   geo=StopGeometry(net), habits=habits, sampler=PassengerSampler(habits, len(net.routes)),
                   veh_cap=net.vehicles["capacity_total"].to_numpy(), veh_apc=net.vehicles["has_apc"].to_numpy(),
                   veh_ids=net.vehicles["vehicle_id"].to_numpy(),
                   route_cong=rng.normal(0.0, 0.03, len(net.routes)))


# --------------------------------------------------------------------------
# Step 1: planned trips for a month
# --------------------------------------------------------------------------

def _period_of(minute: float) -> int:
    """Time-of-day period index; times before the first period count as 'early', after the last as 'evening'."""
    if minute < PERIODS[0][1]:
        return 0
    for p, (_, s, e) in enumerate(PERIODS):
        if s <= minute < e:
            return p
    return len(PERIODS) - 1


def plan_trips(ctx: Context, dates: list) -> pd.DataFrame:
    """Expand schedules (and event extras) into one row per planned trip."""
    rows = []
    net = ctx.net
    for d in dates:
        svc = active_service(ctx.calendar, d)
        day_code = DAY_TYPE_CODE[svc["day_type"]]
        routes_today = ctx.lookup[svc["service_id"]]
        for r, dirs in routes_today.items():
            for direction in (0, 1):
                for dep, p, hw, runtime, sid in departures_for(dirs[direction], r, direction, d):
                    rows.append((d, r, direction, dep, p, hw, runtime, sid, svc["service_id"], day_code, 0))
        # special events: extra departures before the start and after the end
        for ev in ctx.scenario.events:
            if ev["date"] != d:
                continue
            for r in np.where(ev["routes"])[0]:
                if int(r) not in routes_today:
                    continue
                for direction in (0, 1):
                    for dep in [ev["start"] - 60, ev["start"] - 40, ev["start"] - 20,
                                ev["end"] - 10, ev["end"] + 5, ev["end"] + 20, ev["end"] + 35]:
                        p = _period_of(dep)
                        _, _, _, _, runtime, sid, vfrom, vto = routes_today[int(r)][direction][p]
                        if not (vfrom <= d <= vto):
                            continue          # route not launched yet
                        rows.append((d, int(r), direction, float(dep), p, 15, runtime, sid, svc["service_id"], day_code, 1))
    cols = ["date", "route", "dir", "sched_dep", "period", "headway", "runtime", "schedule_id", "service_id", "day_code", "is_extra"]
    return pd.DataFrame(rows, columns=cols)


# --------------------------------------------------------------------------
# Step 2: demand and static delay drivers (vectorised)
# --------------------------------------------------------------------------

def demand_rates(ctx: Context, t: pd.DataFrame, rng) -> np.ndarray:
    """Passengers arriving per minute for each planned trip's route/direction/time."""
    net, sc, dem = ctx.net, ctx.scenario, ctx.cfg["demand"]
    route, direction = t["route"].to_numpy(), t["dir"].to_numpy()
    hour = (t["sched_dep"].to_numpy() // 60).astype(int) % 24
    code = t["day_code"].to_numpy()
    dates = t["date"].to_numpy()
    inbound = direction == net.route_inbound_dir[route]

    prof = np.select(
        [code == 0, code == 1, (code == 2) | (code == 3), code == 4],
        [np.where(inbound, P_WK_IN[hour], P_WK_OUT[hour]), P_SAT[hour], P_SUN[hour],
         np.where(inbound, P_RAM_IN[hour], P_RAM_OUT[hour])])
    boost = dem["peak_direction_boost"]
    weekday = code == 0
    prof = prof * np.where(weekday & inbound & (hour >= 6) & (hour <= 9), boost, 1.0)
    prof = prof * np.where(weekday & ~inbound & (hour >= 15) & (hour <= 18), boost, 1.0)

    dow = np.array([d.weekday() for d in dates])
    prof = prof * np.where((dow == 4) & ((hour == 12) | (hour == 13)), 0.6, 1.0)     # Friday prayers
    month = np.array([d.month for d in dates])
    day_factor = DOW_FACTOR[dow]
    is_hol = np.array([d in sc.holidays for d in dates])
    is_eid = np.array([d in sc.eid for d in dates])
    day_factor = np.where(is_eid, EID_FACTOR, np.where(is_hol, HOLIDAY_FACTOR, day_factor))
    weather = np.ones(len(t))
    weather *= np.where(np.array([d in sc.rain for d in dates]), 0.85, 1.0)
    weather *= np.where(np.array([d in sc.heat for d in dates]) & (hour >= 11) & (hour <= 15), 0.7, 1.0)
    weather *= np.where(np.array([d in sc.fog for d in dates]) & (hour >= 6) & (hour <= 10), 0.9, 1.0)

    event = np.ones(len(t))
    dep = t["sched_dep"].to_numpy()
    for ev in sc.events:
        m = (dates == ev["date"]) & ev["routes"][route] & (dep >= ev["start"] - 120) & (dep <= ev["end"] + 60)
        event = np.where(m, ev["mult"], event)

    # new routes ramp up over their first 60 days
    launch = pd.to_datetime(net.routes["launch_date"]).dt.date.to_numpy()[route]
    age_days = np.array([(d - l).days for d, l in zip(dates, launch)])
    ramp = np.clip(0.5 + 0.5 * age_days / 60.0, 0.5, 1.0)

    # route-day noise: some days are simply busier than others
    day_idx = np.array([(d - ctx.cfg["start_date"]).days for d in dates])
    noise_table = rng.lognormal(0.0, 0.08, (len(net.routes), int(day_idx.max()) + 1))
    noise = noise_table[route, day_idx]

    rate = (net.route_rate[route] * prof * np.vectorize(MONTH_FACTOR.get)(month) * day_factor
            * weather * event * ramp * noise * dem["scale"])
    return rate


def static_delay_components(ctx: Context, t: pd.DataFrame, rng) -> dict:
    """Delay drivers that do not depend on other buses (minutes of extra running time)."""
    sc = ctx.scenario
    n = len(t)
    route = t["route"].to_numpy()
    period = t["period"].to_numpy()
    code = t["day_code"].to_numpy()
    dates = t["date"].to_numpy()
    runtime = t["runtime"].to_numpy()
    hour = (t["sched_dep"].to_numpy() // 60).astype(int) % 24
    dep = t["sched_dep"].to_numpy()
    weekend = (code == 1) | (code == 2) | (code == 3)
    peak = (period == 1) | (period == 3)

    mu = np.where(weekend, CONG_MU_WEEKEND[period], CONG_MU_WEEKDAY[period])
    mu = np.where((code == 4) & (period == 3), 1.18, mu)            # Ramadan pre-iftar rush
    ratio = mu + ctx.route_cong[route] + rng.normal(0, 0.05, n)
    comp = {}
    comp["traffic_congestion"] = runtime * (ratio - 1.0) + rng.normal(0, 1.2, n)

    nb = ctx.geo.n_bottleneck[2 * route + t["dir"].to_numpy()]
    comp["junction_bottleneck"] = nb * rng.uniform(0.2, 0.8, n) * np.where(peak & ~weekend, 1.6, 0.6)

    fog_day = np.array([d in sc.fog for d in dates])
    comp["weather_fog"] = np.where(fog_day & (hour >= 6) & (hour <= 10), rng.uniform(4, 15, n), 0.0)
    rain_day = np.array([d in sc.rain for d in dates])
    comp["weather_rain"] = np.where(rain_day & (rng.random(n) < 0.5), rng.uniform(2, 10, n), 0.0)

    ev_delay = np.zeros(n)
    for ev in sc.events:
        m = (dates == ev["date"]) & ev["routes"][route] & (dep >= ev["start"] - 120) & (dep <= ev["end"] + 60)
        ev_delay = np.where(m, rng.uniform(3, 12, n), ev_delay)
    comp["special_event"] = ev_delay

    rw = np.zeros(n)
    for r, (s, e) in sc.roadworks.items():
        m = (route == r) & np.array([s <= d <= e for d in dates])
        rw = np.where(m, rng.uniform(3, 9, n), rw)
    comp["road_works"] = rw

    disr = np.zeros(n)
    for d, mask in sc.protest.items():
        m = (dates == d) & mask[route] & (hour >= 10) & (hour <= 18)
        disr = np.where(m, rng.uniform(10, 40, n), disr)
    for d in sc.spike:
        m = (dates == d) & peak
        disr = np.where(m, disr + rng.uniform(5, 25, n), disr)
    comp["disruption"] = disr

    breakdown = rng.random(n) < ctx.cfg["operations"]["breakdown_rate"]
    comp["vehicle_breakdown"] = np.where(breakdown, rng.uniform(10, 45, n), 0.0)

    # cancellations (probability rises with fog, driver shortages and protests)
    shortage = np.array([d in sc.shortage for d in dates])
    protest_hit = np.zeros(n, dtype=bool)
    for d, mask in sc.protest.items():
        protest_hit |= (dates == d) & mask[route] & (hour >= 10) & (hour <= 18)
    p_cancel = (ctx.cfg["operations"]["cancel_rate"] + 0.01 * (fog_day & (hour <= 10))
                + 0.05 * shortage + 0.08 * protest_hit)
    cancelled = rng.random(n) < p_cancel
    reason = np.where(protest_hit, "road_closure",
             np.where(shortage, "driver_shortage",
             np.where(fog_day & (hour <= 10), "weather",
                      rng.choice(["driver_shortage", "vehicle_unavailable"], n, p=[0.55, 0.45]))))
    comp["_cancelled"] = cancelled & (t["is_extra"].to_numpy() == 0)
    comp["_cancel_reason"] = reason
    comp["_breakdown"] = breakdown
    return comp


# --------------------------------------------------------------------------
# Step 3: sequential operations model per route-day
# --------------------------------------------------------------------------

def run_operations(ctx: Context, t: pd.DataFrame, rate: np.ndarray, comp: dict, rng) -> dict:
    """Walk each route-day in time order: vehicle assignment, headway-driven loads, running times."""
    n = len(t)
    route = t["route"].to_numpy(); direction = t["dir"].to_numpy()
    sched = t["sched_dep"].to_numpy(); runtime = t["runtime"].to_numpy(); headway = t["headway"].to_numpy()
    day = np.array([(d - ctx.cfg["start_date"]).days for d in t["date"]])
    layover = ctx.cfg["operations"]["layover_min"]

    static = (comp["traffic_congestion"] + comp["junction_bottleneck"] + comp["weather_fog"] + comp["weather_rain"]
              + comp["special_event"] + comp["road_works"] + comp["disruption"] + comp["vehicle_breakdown"])
    cancelled = comp["_cancelled"]; breakdown = comp["_breakdown"]

    # random draws made up front (vectorised) and consumed in the loop
    ops_cfg = ctx.cfg["operations"]
    # departure deviation at the first stop: mostly small, sometimes a clearly late start
    dep_noise = np.where(rng.random(n) < 0.75, np.clip(rng.normal(0.3, 0.8, n), -2.0, 3.0), rng.uniform(1, 6, n))
    gmult = rng.gamma(10.0, 0.1, n)                    # over-dispersion of demand
    z = rng.normal(0, 1, n)
    rtype = ctx.net.routes["route_type"].to_numpy()[route]
    rho = np.where(rtype == "feeder", rng.uniform(0.75, 0.9, n), rng.uniform(0.55, 0.75, n))  # share on board at the peak point

    out_vehicle = np.full(n, -1); out_orig = np.full(n, -1)
    out_dep = np.full(n, np.nan); out_arr = np.full(n, np.nan)
    out_b = np.zeros(n, dtype=np.int64); out_load = np.zeros(n); out_denied = np.zeros(n, dtype=np.int64)
    out_dwell = np.zeros(n); out_late = np.zeros(n); out_depdev = np.zeros(n); out_E = np.zeros(n)

    veh_cap = ctx.veh_cap
    spares = ctx.net.spare_vehicle_idx
    spare_ptr = 0
    order = np.lexsort((direction, sched, day, route))    # route, day, time
    i0 = 0
    while i0 < n:
        # one route-day group
        r, dd = route[order[i0]], day[order[i0]]
        i1 = i0
        while i1 < n and route[order[i1]] == r and day[order[i1]] == dd:
            i1 += 1
        heap = [(-1e9, int(v)) for v in ctx.net.route_vehicle_pool[r]]
        heapq.heapify(heap)
        last_dep = [None, None]
        for j in range(i0, i1):
            i = order[j]
            if not heap:                                   # every bus broke down: borrow a spare
                heapq.heappush(heap, (-1e9, int(spares[spare_ptr % len(spares)]))); spare_ptr += 1
            if cancelled[i]:
                out_vehicle[i] = heap[0][1]                # planned vehicle; it stays available
                continue
            avail, v = heapq.heappop(heap)
            ready = avail + layover
            late = max(0.0, ready - sched[i])
            dep_dev = max(dep_noise[i], late)
            a_dep = sched[i] + dep_dev
            d_ = direction[i]
            gap = headway[i] if last_dep[d_] is None else a_dep - last_dep[d_]
            gap = min(max(gap, 0.5), 3.0 * headway[i])
            lam = rate[i] * gap * gmult[i]
            b = max(0, int(round(lam + math.sqrt(lam) * z[i])))
            # The vehicle that finishes the trip is the one whose APC reports the counts:
            # after a breakdown that is the depot spare, so its capacity limits the load.
            sp = -1
            if breakdown[i]:
                sp = int(spares[spare_ptr % len(spares)]); spare_ptr += 1
            cap = veh_cap[sp if sp >= 0 else v]
            load = b * rho[i]
            crush = cap * ops_cfg["crush_load_factor"]
            denied = 0
            if load > crush:
                denied = int(round((load - crush) / rho[i]))
                b -= denied
                load = crush
            expected = rate[i] * headway[i]
            # boarding-driven delay: extra dwell for every passenger above normal ...
            dwell = ops_cfg["dwell_per_boarding_min"] * (b - expected)
            # ... and the bunching feedback: a bus running after a long gap also meets more
            # passengers at every later stop and keeps losing time, while the bus behind it
            # finds empty stops and catches up (headway instability).
            dwell += runtime[i] * ops_cfg["bunching_sensitivity"] * (min(max(gap / headway[i], 0.2), 3.0) - 1.0)
            if load / cap > 0.85:
                dwell += (load / cap - 0.85) * ops_cfg["crowding_penalty_min"]   # crowded: slow boarding/alighting
            E = static[i] + dwell
            E = max(E, -0.18 * runtime[i])                 # early running is limited
            a_arr = a_dep + runtime[i] + E
            if sp >= 0:
                out_orig[i] = v
                out_vehicle[i] = sp                        # broken bus leaves the route for the day
            else:
                out_vehicle[i] = v
                heapq.heappush(heap, (a_arr, v))
            last_dep[d_] = a_dep
            out_dep[i], out_arr[i] = a_dep, a_arr
            out_b[i], out_load[i], out_denied[i] = b, load, denied
            out_dwell[i], out_late[i], out_depdev[i], out_E[i] = dwell, late, dep_dev, E
        i0 = i1

    return {"vehicle": out_vehicle, "orig_vehicle": out_orig, "act_dep": out_dep, "act_arr": out_arr,
            "boardings": out_b, "load": out_load, "denied": out_denied, "dwell": out_dwell,
            "late_vehicle": out_late, "dep_dev": out_depdev, "E": out_E}


# --------------------------------------------------------------------------
# Step 4: derive output tables
# --------------------------------------------------------------------------

def _stop_times(geo, key, k, sched_dep, runtime, act_dep, E, boardings):
    """Scheduled/actual arrival and departure minutes at stop k of each trip (vectorised)."""
    idx = geo.off[key] + k
    f, cw = geo.frac[idx], geo.cumw[idx]
    first = k == 0
    s_arr = np.where(first, sched_dep - 0.5, sched_dep + runtime * f)
    a_arr = np.where(first, act_dep - 0.5, act_dep + runtime * f + E * cw)
    s_dep = s_arr + 0.5
    dwell = np.where(first, 0.5, 0.3 + np.minimum(3.0, 0.02 * boardings))
    a_dep = a_arr + dwell
    return s_arr, a_arr, s_dep, a_dep


@dataclass
class MonthResult:
    trips: pd.DataFrame
    passenger_counts: pd.DataFrame
    tickets: pd.DataFrame
    delays: pd.DataFrame
    gps: dict                    # date string -> DataFrame
    apc_trip_ids: np.ndarray     # trips that have a passenger_counts row


def simulate_month(ctx: Context, year: int, month: int, log) -> MonthResult:
    cfg, net, geo = ctx.cfg, ctx.net, ctx.geo
    first = dt.date(year, month, 1)
    last = (dt.date(year + (month == 12), month % 12 + 1, 1) - dt.timedelta(days=1))
    dates = date_range(max(first, cfg["start_date"]), min(last, cfg["end_date"]))
    rng = make_rng(cfg["seed"], "trips", year, month)

    t = plan_trips(ctx, dates)
    rate = demand_rates(ctx, t, rng)
    comp = static_delay_components(ctx, t, rng)
    ops = run_operations(ctx, t, rate, comp, rng)

    # ---- output order and IDs: by date, departure time, route, direction
    date64 = np.array(t["date"].to_numpy(), dtype="datetime64[D]")
    order = np.lexsort((t["dir"].to_numpy(), t["route"].to_numpy(), t["sched_dep"].to_numpy(), date64))
    t = t.iloc[order].reset_index(drop=True)
    date64 = date64[order]
    rate = rate[order]
    comp = {k: v[order] for k, v in comp.items()}
    ops = {k: v[order] for k, v in ops.items()}
    n = len(t)
    yymm = f"{year % 100:02d}{month:02d}"
    trip_ids = np.array([f"T{yymm}{i:06d}" for i in range(1, n + 1)])

    route = t["route"].to_numpy(); direction = t["dir"].to_numpy()
    key = 2 * route + direction
    sched_dep = t["sched_dep"].to_numpy(); runtime = t["runtime"].to_numpy()
    cancelled = comp["_cancelled"]
    operated = ~cancelled
    route_ids = net.routes["route_id"].to_numpy()[route]
    day_ns = date64.astype("datetime64[ns]")
    veh_ids = ctx.veh_ids

    # ---- trips
    trips = pd.DataFrame({
        "trip_id": trip_ids, "route_id": route_ids, "direction": direction,
        "service_date": np.datetime_as_string(date64, unit="D"),
        "service_id": t["service_id"].to_numpy(), "schedule_id": t["schedule_id"].to_numpy(),
        "vehicle_id": veh_ids[ops["vehicle"]],
        "original_vehicle_id": np.where(ops["orig_vehicle"] >= 0, veh_ids[np.maximum(ops["orig_vehicle"], 0)], ""),
        "scheduled_departure": minutes_to_timestamps(day_ns, sched_dep),
        "scheduled_arrival": minutes_to_timestamps(day_ns, sched_dep + runtime),
        "actual_departure": np.where(operated, minutes_to_timestamps(day_ns, np.nan_to_num(ops["act_dep"])), ""),
        "actual_arrival": np.where(operated, minutes_to_timestamps(day_ns, np.nan_to_num(ops["act_arr"])), ""),
        "trip_status": np.where(operated, "completed", "cancelled"),
        "trip_type": np.where(t["is_extra"].to_numpy() == 1, "event_extra", "regular"),
        "cancellation_reason": np.where(cancelled, comp["_cancel_reason"], ""),
    })

    # ---- card taps (registered smart-card boardings), share grows over the period
    span = max(1, (cfg["end_date"] - cfg["start_date"]).days)
    progress = np.array([(d - cfg["start_date"]).days for d in t["date"]]) / span
    dem = cfg["demand"]
    share = dem["card_share_start"] + (dem["card_share_end"] - dem["card_share_start"]) * progress
    period = t["period"].to_numpy(); code = t["day_code"].to_numpy()
    share = share * np.where((period == 1) | (period == 3), 1.25, 1.0) * np.where((code >= 1) & (code <= 3), 0.8, 1.0)
    share = share * np.where(net.routes["route_type"].to_numpy()[route] == "brt", 1.3, 1.0)
    trng = make_rng(cfg["seed"], "tickets", year, month)
    boardings = ops["boardings"]
    taps = np.where(operated, trng.binomial(boardings, np.clip(share, 0, 0.5)), 0)

    # ---- passenger_counts: operated trips on APC-equipped vehicles
    has_apc = operated & ctx.veh_apc[np.maximum(ops["vehicle"], 0)]
    pi = np.where(has_apc)[0]
    nst = geo.nst[key[pi]]
    inbound = direction[pi] == net.route_inbound_dir[route[pi]]
    peak_frac = np.where(inbound, trng.beta(6, 3, len(pi)), trng.beta(3, 4, len(pi)))
    kpeak = np.clip(np.round(peak_frac * (nst - 1)).astype(int), 1, nst - 1)
    pc = pd.DataFrame({
        "count_id": np.char.add("PC", np.char.lstrip(trip_ids[pi].astype(str), "T")),
        "trip_id": trip_ids[pi], "route_id": route_ids[pi], "service_date": trips["service_date"].to_numpy()[pi],
        "vehicle_id": veh_ids[ops["vehicle"][pi]],
        "boardings": boardings[pi],
        "alightings": np.maximum(0, boardings[pi] + np.round(trng.normal(0, 1.2, len(pi))).astype(int)),
        "max_load": np.round(ops["load"][pi]).astype(int),
        "max_load_stop_id": geo.stop_id[geo.off[key[pi]] + kpeak],
        "denied_boardings": ops["denied"][pi],
        "card_taps": taps[pi],
    })

    # ---- tickets: one row per card tap
    ti = np.repeat(np.arange(n), taps)
    m_t = len(ti)
    nst_t = geo.nst[key[ti]]
    e = np.floor(trng.random(m_t) ** 1.25 * (nst_t - 1)).astype(int)            # board earlier on the route more often
    x = e + 1 + np.floor(trng.random(m_t) * (nst_t - 1 - e)).astype(int)
    x = np.minimum(x, nst_t - 1)
    _, a_arr_e, _, a_dep_e = _stop_times(geo, key[ti], e, sched_dep[ti], runtime[ti], ops["act_dep"][ti], ops["E"][ti], boardings[ti])
    _, a_arr_x, _, _ = _stop_times(geo, key[ti], x, sched_dep[ti], runtime[ti], ops["act_dep"][ti], ops["E"][ti], boardings[ti])
    entry_min = a_arr_e + trng.random(m_t) * (a_dep_e - a_arr_e)
    exit_min = a_arr_x + trng.random(m_t) * 0.3
    # passengers: sample per route from people registered by the start of the month
    pools = ctx.sampler.pools_for(np.datetime64(first))
    pax = np.empty(m_t, dtype=np.int64)
    for r in np.unique(route[ti]):
        sel = np.where(route[ti] == r)[0]
        idx, p = pools[r]
        pax[sel] = trng.choice(idx, len(sel), p=p)
    hab = ctx.habits
    ttype = TICKET_TYPES[hab.ticket_type[pax]]
    fare_cat = hab.fare_category[pax]
    dist_km = geo.dist[geo.off[key[ti]] + x] - geo.dist[geo.off[key[ti]] + e]
    routes_df = net.routes
    raw_fare = (routes_df["base_fare"].to_numpy()[route[ti]] + routes_df["fare_per_km"].to_numpy()[route[ti]] * dist_km)
    discount = np.vectorize(FARE_DISCOUNT.get)(fare_cat)
    fare = np.where(ttype == "single", np.round(raw_fare * discount / 5.0) * 5.0, 0.0)
    tickets = pd.DataFrame({
        "ticket_id": np.array([f"TK{yymm}{i:08d}" for i in range(1, m_t + 1)]),
        "passenger_id": hab.ids[pax], "trip_id": trip_ids[ti], "route_id": route_ids[ti],
        "service_date": trips["service_date"].to_numpy()[ti],
        "entry_stop_id": geo.stop_id[geo.off[key[ti]] + e], "exit_stop_id": geo.stop_id[geo.off[key[ti]] + x],
        "entry_time": minutes_to_timestamps(day_ns[ti], entry_min),
        "exit_time": minutes_to_timestamps(day_ns[ti], exit_min),
        "ticket_type": ttype, "fare_category": fare_cat, "fare_amount": fare,
        "payment_method": np.where(hab.pays_qr[pax], "mobile_qr", "smart_card"),
    })

    delays = _derive_delays(ctx, t, trips, ops, comp, key, day_ns, yymm, trng)
    gps = _derive_gps(ctx, t, trips, ops, key, day_ns, make_rng(cfg["seed"], "gps", year, month))

    log.info(f"{year}-{month:02d}: trips={n:,} cancelled={int(cancelled.sum()):,} pc={len(pc):,} "
             f"tickets={len(tickets):,} delays={len(delays):,} gps={sum(len(g) for g in gps.values()):,}")
    return MonthResult(trips=trips, passenger_counts=pc, tickets=tickets, delays=delays, gps=gps,
                       apc_trip_ids=trip_ids[pi])


def _derive_delays(ctx, t, trips, ops, comp, key, day_ns, yymm, rng) -> pd.DataFrame:
    """Stop-level delay records with a reason taken from the largest delay driver."""
    geo = ctx.geo
    operated = ~comp["_cancelled"]
    dep_dev, E = ops["dep_dev"], ops["E"]
    d_end = dep_dev + E
    # reason = the biggest positive contributor
    contrib = np.vstack([
        ops["late_vehicle"], comp["traffic_congestion"], comp["junction_bottleneck"], ops["dwell"],
        comp["weather_fog"], comp["weather_rain"], comp["special_event"], comp["road_works"],
        comp["vehicle_breakdown"], comp["disruption"]])
    reason_idx = np.argmax(contrib, axis=0)
    reason = np.array(DELAY_REASONS)[reason_idx]
    nst = geo.nst[key]
    late_vehicle = reason == "late_vehicle"
    early = operated & (d_end <= -2.0)
    # stop where the deviation is logged
    k = np.where(late_vehicle, 0, geo.kmax[key])
    k = np.where(early, nst - 1, k)
    k = np.where(comp["vehicle_breakdown"] > 0, np.maximum(1, (nst - 1) // 2), k)
    sched_dep, runtime, boardings = t["sched_dep"].to_numpy(), t["runtime"].to_numpy(), ops["boardings"]
    act_dep = np.nan_to_num(ops["act_dep"])

    s_arr_all, a_arr_all, _, _ = _stop_times(geo, key, k, sched_dep, runtime, act_dep, E, boardings)
    delay_at_k = a_arr_all - s_arr_all
    primary = operated & (((delay_at_k >= 5.0) & ~early) | early | (comp["vehicle_breakdown"] > 0))
    rsn = np.where(early, "early_running", reason)
    # big delays are logged again at the last stop (a second timing point)
    second = operated & ~early & (d_end >= 10.0) & (k != nst - 1)

    parts = []
    for part_no, (mask, kk) in enumerate(((primary, k), (second, nst - 1))):
        idx = np.where(mask)[0]
        s_arr, a_arr, s_dep, a_dep = _stop_times(geo, key[idx], kk[idx], sched_dep[idx], runtime[idx],
                                                 act_dep[idx], E[idx], boardings[idx])
        s_arr_ts = minutes_to_timestamps(day_ns[idx], s_arr)
        a_arr_ts = minutes_to_timestamps(day_ns[idx], a_arr)
        # delay in minutes computed from the rounded (second-precision) timestamps, so it matches them exactly
        delay_min = np.round((np.round(a_arr * 60) - np.round(s_arr * 60)) / 60.0, 2)
        src = np.where(rsn[idx] == "vehicle_breakdown", "controller",
                       np.where((delay_min > 15) & (rng.random(len(idx)) < 0.3), "driver_report", "avl"))
        parts.append(pd.DataFrame({
            "_order": idx * 2 + part_no,
            "trip_id": trips["trip_id"].to_numpy()[idx], "route_id": trips["route_id"].to_numpy()[idx],
            "stop_id": geo.stop_id[geo.off[key[idx]] + kk[idx]],
            "service_date": trips["service_date"].to_numpy()[idx],
            "scheduled_arrival": s_arr_ts, "actual_arrival": a_arr_ts,
            "scheduled_departure": minutes_to_timestamps(day_ns[idx], s_dep),
            "actual_departure": minutes_to_timestamps(day_ns[idx], a_dep),
            "delay_minutes": delay_min, "delay_reason": rsn[idx], "record_source": src,
        }))
    delays = pd.concat(parts, ignore_index=True).sort_values("_order", kind="stable").drop(columns="_order")
    delays.insert(0, "delay_id", [f"D{yymm}{i:07d}" for i in range(1, len(delays) + 1)])
    return delays.reset_index(drop=True)


def _derive_gps(ctx, t, trips, ops, key, day_ns, rng) -> dict:
    """AVL pings for trips inside the GPS sample window: departure, mid-segment and stop arrivals."""
    cfg, geo = ctx.cfg, ctx.geo
    w_start = cfg["gps_window_start"]
    w_end = w_start + dt.timedelta(days=cfg["gps_window_days"] - 1)
    dates = t["date"].to_numpy()
    in_win = np.array([w_start <= d <= w_end for d in dates]) & (trips["trip_status"].to_numpy() == "completed")
    idx = np.where(in_win)[0]
    if len(idx) == 0:
        return {}
    nst = geo.nst[key[idx]]
    # expand trip x stop
    ti = np.repeat(idx, nst)
    k = np.concatenate([np.arange(m) for m in nst])
    sched_dep, runtime, E = t["sched_dep"].to_numpy(), t["runtime"].to_numpy(), ops["E"]
    act_dep, b = np.nan_to_num(ops["act_dep"]), ops["boardings"]
    s_arr, a_arr, s_dep, a_dep = _stop_times(geo, key[ti], k, sched_dep[ti], runtime[ti], act_dep[ti], E[ti], b[ti])
    g = geo.off[key[ti]] + k
    lat, lon, dist = geo.lat[g], geo.lon[g], geo.dist[g]
    noise = lambda m: rng.normal(0, 0.00012, m)          # ~13 m GPS noise
    m = len(ti)
    veh = ctx.veh_ids[ops["vehicle"][ti]]

    # stop events: departure at the first stop, arrival at every other stop
    ev_stop = pd.DataFrame({
        "_trip": ti, "_k": k * 2, "vehicle_id": veh, "trip_id": trips["trip_id"].to_numpy()[ti],
        "route_id": trips["route_id"].to_numpy()[ti], "stop_id": geo.stop_id[g],
        "_min": np.where(k == 0, a_dep, a_arr),
        "event_type": np.where(k == 0, "stop_departure", "stop_arrival"),
        "latitude": np.round(lat + noise(m), 6), "longitude": np.round(lon + noise(m), 6), "speed_kmh": 0.0,
    })
    # in-transit pings halfway between consecutive stops
    mid = k > 0
    prev = np.where(mid)[0] - 1
    seg_time = a_arr[mid] - a_dep[prev]
    seg_km = dist[mid] - dist[prev]
    speed = np.clip(seg_km / np.maximum(seg_time, 0.2) * 60 * rng.uniform(0.85, 1.15, mid.sum()), 3, 70)
    ev_mid = pd.DataFrame({
        "_trip": ti[mid], "_k": k[mid] * 2 - 1, "vehicle_id": veh[mid], "trip_id": ev_stop["trip_id"].to_numpy()[mid],
        "route_id": ev_stop["route_id"].to_numpy()[mid], "stop_id": None,
        "_min": (a_dep[prev] + a_arr[mid]) / 2, "event_type": "in_transit",
        "latitude": np.round((lat[prev] + lat[mid]) / 2 + noise(mid.sum()) * 1.5, 6),
        "longitude": np.round((lon[prev] + lon[mid]) / 2 + noise(mid.sum()) * 1.5, 6),
        "speed_kmh": np.round(speed, 1),
    })
    ev = pd.concat([ev_stop, ev_mid], ignore_index=True)
    ev["event_time"] = minutes_to_timestamps(day_ns[ev["_trip"].to_numpy()], ev["_min"].to_numpy())
    ev["_date"] = np.datetime_as_string(day_ns[ev["_trip"].to_numpy()].astype("datetime64[D]"), unit="D")
    ev = ev.sort_values(["_date", "event_time", "_trip", "_k"], kind="stable")
    out = {}
    for d, grp in ev.groupby("_date", sort=True):
        g2 = grp.reset_index(drop=True)
        g2.insert(0, "event_id", [f"G{d[2:4]}{d[5:7]}{d[8:10]}{i:07d}" for i in range(1, len(g2) + 1)])
        out[d] = g2.drop(columns=["_trip", "_k", "_min", "_date"])
    return out
