"""Build the transit network: stops, routes, route_stops and vehicles.

How it works (short version)
----------------------------
1. A fixed list of real Lahore landmarks ("hubs") becomes the first stops.
2. Each route is drawn as a polyline between two points (often via a hub),
   depending on its type (BRT crosses the city, feeders run from the edge to
   a hub, ...). Stop points are placed every ~0.5-1 km along the line.
3. A stop point that falls within `stop_merge_radius_km` of an existing stop
   reuses that stop, so routes naturally share stops at hubs and corridors.
4. The busiest shared stops become "bottleneck junctions" (used later by the
   delay model - they are not a column in the output).
5. The fleet is sized per route from its peak headway and running time.

Everything is driven by `network_seed`, so `full` and `hidden_like` share the
same base city and `hidden_like` only adds extension routes on top.
"""

import datetime as dt
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .utils import haversine_km, make_rng

# Landmarks used as hubs (approximate real coordinates in Lahore).
HUBS = [
    ("Railway Station", 31.5770, 74.3360), ("Data Darbar", 31.5795, 74.3050),
    ("Minar-e-Pakistan", 31.5925, 74.3095), ("Anarkali", 31.5680, 74.3100),
    ("Mall Road GPO", 31.5655, 74.3170), ("Liberty Market", 31.5100, 74.3450),
    ("Gaddafi Stadium", 31.5135, 74.3330), ("Kalma Chowk", 31.5040, 74.3290),
    ("Model Town", 31.4830, 74.3260), ("Johar Town", 31.4690, 74.2720),
    ("Thokar Niaz Baig", 31.4710, 74.2410), ("Township", 31.4520, 74.3070),
    ("Expo Centre", 31.4640, 74.2640), ("DHA Phase 5", 31.4630, 74.4080),
    ("Airport", 31.5210, 74.4030), ("Cantt", 31.5250, 74.3900),
    ("Shahdara", 31.6200, 74.2850), ("Punjab University", 31.4970, 74.2980),
    ("Wapda Town", 31.4350, 74.2650), ("Kot Lakhpat", 31.4560, 74.3350),
    ("Walton", 31.4990, 74.3600), ("Harbanspura", 31.5710, 74.4220),
    ("Shalimar Gardens", 31.5860, 74.3820), ("Samanabad", 31.5380, 74.2980),
    ("Gulberg Main Boulevard", 31.5200, 74.3500), ("Garden Town", 31.5010, 74.3180),
    ("Iqbal Town", 31.5130, 74.2860), ("Badami Bagh", 31.5930, 74.3240),
]
STOP_SUFFIXES = ["Chowk", "Market", "Stop", "Mor", "Road", "Park", "Hospital", "School",
                 "Colony", "Bazaar", "Plaza", "Gate", "Bridge", "Masjid", "Adda", "Block"]
DEPOTS = [("Gulberg Depot", 31.515, 74.345), ("Thokar Depot", 31.470, 74.245),
          ("Shahdara Depot", 31.618, 74.288), ("Township Depot", 31.452, 74.310),
          ("Airport Depot", 31.522, 74.400)]

# Per route type: length range (km), stop spacing (km), vehicle type and fare rules.
ROUTE_TYPE_SPEC = {
    "brt":    {"length": (18, 27), "spacing": 1.00, "vehicle": "articulated", "base_fare": 30.0, "per_km": 2.0, "prefix": "BRT"},
    "trunk":  {"length": (11, 22), "spacing": 0.75, "vehicle": "standard", "base_fare": 25.0, "per_km": 1.8, "prefix": "T"},
    "local":  {"length": (6, 14), "spacing": 0.60, "vehicle": "standard", "base_fare": 20.0, "per_km": 1.5, "prefix": "L"},
    "feeder": {"length": (3.5, 8), "spacing": 0.55, "vehicle": "minibus", "base_fare": 15.0, "per_km": 1.2, "prefix": "F"},
}
VEHICLE_SPEC = {"articulated": (48, 150), "standard": (36, 70), "minibus": (22, 30)}  # seated, total

# Planned speeds (km/h) per route type and time period -> planned running times.
SPEED_KMH = {
    "brt":    {"early": 26, "am_peak": 20, "midday": 23, "pm_peak": 19, "evening": 24},
    "trunk":  {"early": 22, "am_peak": 14, "midday": 17, "pm_peak": 13.5, "evening": 19},
    "local":  {"early": 21, "am_peak": 14.5, "midday": 17, "pm_peak": 14, "evening": 19},
    "feeder": {"early": 23, "am_peak": 17, "midday": 19, "pm_peak": 16.5, "evening": 21},
}
ROAD_CIRCUITY = 1.2          # road distance / straight-line distance
FLEET_REFERENCE_HEADWAY = {"brt": 8, "trunk": 16, "local": 30, "feeder": 45}  # tightest peak headway in any timetable
# Fixed (not mode-dependent) so every mode that shares the city gets an identical base fleet.
NEW_ROUTE_CUTOFF = dt.date(2025, 6, 1)


@dataclass
class Network:
    """In-memory network. DataFrames are the output tables; the rest is used by the simulation."""
    stops: pd.DataFrame
    routes: pd.DataFrame
    route_stops: pd.DataFrame
    vehicles: pd.DataFrame = None
    # simulation-only attributes, indexed by route position (0..n_routes-1)
    route_stop_idx: list = field(default_factory=list)   # stop row indices, direction 0
    route_cum_km: list = field(default_factory=list)     # cumulative road km, direction 0
    route_rate: np.ndarray = None                        # passengers/min per direction at profile 1
    route_inbound_dir: np.ndarray = None                 # which direction heads to the centre (0/1)
    route_bottlenecks: list = field(default_factory=list)  # bool array per route (dir 0 order)
    route_vehicle_pool: list = field(default_factory=list)  # vehicle row indices per route
    bottleneck_stop_ids: set = field(default_factory=set)
    spare_vehicle_idx: np.ndarray = None


# ---------------------------------------------------------------------------
# Geometry helpers: a flat km grid around the city centre is accurate enough for a city
# ---------------------------------------------------------------------------

class _Grid:
    def __init__(self, centre):
        self.lat0, self.lon0 = centre
        self.kx = 111.32 * math.cos(math.radians(self.lat0))
        self.ky = 110.57

    def to_xy(self, lat, lon):
        return (np.asarray(lon) - self.lon0) * self.kx, (np.asarray(lat) - self.lat0) * self.ky

    def to_latlon(self, x, y):
        return self.lat0 + np.asarray(y) / self.ky, self.lon0 + np.asarray(x) / self.kx


def _polyline_points(rng, waypoints, spacing):
    """Stop points every ~spacing km along a polyline, with small sideways noise (roads are not straight)."""
    pts = [waypoints[0]]
    for (x0, y0), (x1, y1) in zip(waypoints[:-1], waypoints[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        if seg < 1e-6:
            continue
        ux, uy = (x1 - x0) / seg, (y1 - y0) / seg
        pos = 0.0
        while True:
            pos += spacing * rng.uniform(0.75, 1.25)
            if pos >= seg - spacing * 0.4:
                break
            off = rng.normal(0, 0.06)
            pts.append((x0 + ux * pos - uy * off, y0 + uy * pos + ux * off))
        pts.append((x1, y1))
    return pts


def _route_waypoints(rng, rtype, hub_xy):
    """Choose origin, optional via-hub and destination for a route of the given type (km grid)."""
    def ring(rmin, rmax, angle=None):
        a = rng.uniform(0, 2 * math.pi) if angle is None else angle
        r = rng.uniform(rmin, rmax)
        return (r * math.cos(a), r * math.sin(a)), a

    def nearest_hub(p, exclude=None, dmin=0.0, dmax=1e9):
        d = np.hypot(hub_xy[:, 0] - p[0], hub_xy[:, 1] - p[1])
        ok = (d >= dmin) & (d <= dmax)
        if exclude is not None:
            ok[exclude] = False
        if not ok.any():
            return None
        idx = np.where(ok)[0]
        return int(idx[np.argmin(d[idx])])

    centre_hub = nearest_hub((0.0, 0.0))
    if rtype == "brt":
        o, a = ring(8, 12)
        d, _ = ring(8, 12, a + math.pi + rng.uniform(-0.5, 0.5))
        return [o, tuple(hub_xy[centre_hub]), d]
    if rtype == "trunk":
        o, a = ring(5, 11)
        dest_hub = int(rng.choice(np.where(np.hypot(hub_xy[:, 0], hub_xy[:, 1]) < 5)[0]))
        d = tuple(hub_xy[dest_hub])
        mid = ((o[0] + d[0]) / 2, (o[1] + d[1]) / 2)
        via = nearest_hub(mid, exclude=[dest_hub], dmax=2.5)
        return [o, tuple(hub_xy[via]), d] if via is not None else [o, d]
    if rtype == "local":
        o, _ = ring(1.5, 8)
        cand = np.where((np.hypot(hub_xy[:, 0] - o[0], hub_xy[:, 1] - o[1]) > 4)
                        & (np.hypot(hub_xy[:, 0] - o[0], hub_xy[:, 1] - o[1]) < 10))[0]
        if len(cand) == 0:
            d, _ = ring(1.5, 8)
            return [o, d]
        return [o, tuple(hub_xy[int(rng.choice(cand))])]
    # feeder: from the edge to the nearest hub a few km away
    o, a = ring(7, 13)
    h = nearest_hub(o, dmin=2.5, dmax=7.5)
    if h is None:
        d, _ = ring(3, 5, a)
        return [o, d]
    return [o, tuple(hub_xy[h])]


def _route_length_km(pts):
    return sum(math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:])) * ROAD_CIRCUITY


# ---------------------------------------------------------------------------
# Network builder
# ---------------------------------------------------------------------------

class _StopRegistry:
    """Grows the stop list; reuses a stop when a new point is within the merge radius."""

    def __init__(self, grid, merge_radius, rng):
        self.grid, self.merge_radius, self.rng = grid, merge_radius, rng
        self.x, self.y, self.names, self.types, self.opened = [], [], [], [], []
        self.used_names = set()
        self.hub_xy = None

    def add_hubs(self):
        for name, lat, lon in HUBS:
            x, y = self.grid.to_xy(lat, lon)
            self._append(float(x), float(y), name, "hub", dt.date(2005, 1, 1))
        self.hub_xy = np.column_stack([self.x, self.y])

    def _append(self, x, y, name, stype, opened):
        self.x.append(x); self.y.append(y); self.names.append(name)
        self.types.append(stype); self.opened.append(opened)
        self.used_names.add(name)
        return len(self.x) - 1

    def _new_name(self, x, y):
        d = np.hypot(self.hub_xy[:, 0] - x, self.hub_xy[:, 1] - y)
        area = HUBS[int(np.argmin(d))][0].split(" ")[0] if d.min() > 1.2 else HUBS[int(np.argmin(d))][0]
        for _ in range(40):
            name = f"{area} {self.rng.choice(STOP_SUFFIXES)}"
            if name not in self.used_names:
                return name
        k = 2
        while f"{name} {k}" in self.used_names:
            k += 1
        return f"{name} {k}"

    def get_or_create(self, x, y, opened):
        if self.x:
            d = np.hypot(np.asarray(self.x) - x, np.asarray(self.y) - y)
            i = int(np.argmin(d))
            if d[i] < self.merge_radius:
                return i
        return self._append(x, y, self._new_name(x, y), "regular", opened)


def _make_route(rng, reg, rtype, opened_for_new_stops):
    """Draw one route and return its list of stop indices (direction 0)."""
    spec = ROUTE_TYPE_SPEC[rtype]
    for _ in range(200):
        wps = _route_waypoints(rng, rtype, reg.hub_xy)
        if spec["length"][0] <= _route_length_km(wps) <= spec["length"][1] * 1.15:
            break
    pts = _polyline_points(rng, wps, spec["spacing"])
    idx = []
    for x, y in pts:
        s = reg.get_or_create(x, y, opened_for_new_stops)
        if s not in idx:                  # no loops: a stop appears once per route
            idx.append(s)
    return idx


def build_network(cfg: dict) -> Network:
    """Generate stops, routes and route_stops for the configured city (plus extension routes if any)."""
    ncfg = cfg["network"]
    grid = _Grid(cfg["city_centre"])
    rng = make_rng(cfg["network_seed"], "network")
    reg = _StopRegistry(grid, ncfg["stop_merge_radius_km"], rng)
    reg.add_hubs()

    # 1) base routes (running before the data period) then routes launched mid-period
    plan = []
    for rtype, n in ncfg["route_mix"].items():
        plan += [(rtype, None)] * n
    plan += [(t, dt.date.fromisoformat(str(d))) for t, d in ncfg["new_routes"]]
    ext = cfg.get("network_extension") or {}
    ext_plan = [(t, dt.date.fromisoformat(str(d))) for t, d in ext.get("new_routes", [])]

    route_types, launch_dates, stop_lists = [], [], []

    def add_routes(route_plan, r):
        for rtype, launch in route_plan:
            base_open = dt.date(2008, 1, 1) + dt.timedelta(days=int(r.integers(0, 6200)))
            opened = launch if launch is not None else base_open
            stop_lists.append(_make_route(r, reg, rtype, opened))
            route_types.append(rtype)
            launch_dates.append(launch if launch is not None
                                else dt.date(2012, 1, 1) + dt.timedelta(days=int(r.integers(0, 4700))))

    add_routes(plan, rng)
    n_full_routes = len(stop_lists)
    if ext_plan:
        # extension routes use their own stream so the base city is identical to `full`
        reg.rng = make_rng(cfg["network_seed"], "network_ext")
        add_routes(ext_plan, reg.rng)

    # 2) stops table
    lat, lon = grid.to_latlon(np.asarray(reg.x), np.asarray(reg.y))
    n_stops = len(reg.x)
    stop_ids = np.array([f"S{i + 1:04d}" for i in range(n_stops)])
    dist_centre = np.hypot(np.asarray(reg.x), np.asarray(reg.y))
    stype = np.asarray(reg.types, dtype=object)
    for sl in stop_lists:                         # route ends that are not hubs are terminals
        for s in (sl[0], sl[-1]):
            if stype[s] == "regular":
                stype[s] = "terminal"
    shelter_rng = make_rng(cfg["network_seed"], "network", 99)
    stops_all = pd.DataFrame({
        "stop_id": stop_ids,
        "stop_name": reg.names,
        "latitude": np.round(lat, 6),
        "longitude": np.round(lon, 6),
        "zone": np.where(dist_centre < 5, "A", np.where(dist_centre < 12, "B", "C")),
        "stop_type": stype,
        "has_shelter": (stype != "regular") | (shelter_rng.random(n_stops) < 0.45),
        "opened_date": [d.isoformat() for d in reg.opened],
    })
    # Only stops served by at least one route are published. IDs are kept as generated
    # (gaps are allowed), so the same physical stop has the same ID in every mode.
    served = np.zeros(n_stops, dtype=bool)
    for sl in stop_lists:
        served[sl] = True
    stops = stops_all[served].reset_index(drop=True)

    # 3) routes + route_stops
    route_rows, rs_rows, cum_list = [], [], []
    counters = {t: 0 for t in ROUTE_TYPE_SPEC}
    for r, (rtype, sl) in enumerate(zip(route_types, stop_lists)):
        spec = ROUTE_TYPE_SPEC[rtype]
        counters[rtype] += 1
        seg = haversine_km(lat[sl[:-1]], lon[sl[:-1]], lat[sl[1:]], lon[sl[1:]]) * ROAD_CIRCUITY
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        cum_list.append(cum)
        total = float(cum[-1])
        route_id = f"R{r + 1:03d}"
        route_rows.append({
            "route_id": route_id,
            "route_code": f"{spec['prefix']}{counters[rtype]:02d}" if rtype != "brt" else f"BRT{counters[rtype]}",
            "route_name": f"{reg.names[sl[0]]} - {reg.names[sl[-1]]}",
            "route_type": rtype,
            "origin_stop_id": stop_ids[sl[0]],
            "destination_stop_id": stop_ids[sl[-1]],
            "distance_km": round(total, 2),
            "base_fare": spec["base_fare"],
            "fare_per_km": spec["per_km"],
            "launch_date": launch_dates[r].isoformat(),
            "status": "active",
        })
        midday_speed = SPEED_KMH[rtype]["midday"]
        for direction in (0, 1):
            order = sl if direction == 0 else sl[::-1]
            dist = cum if direction == 0 else total - cum[::-1]
            n = len(order)
            for k, s in enumerate(order):
                timing = k in (0, n - 1) or stype[s] == "hub" or k % 5 == 0
                rs_rows.append({
                    "route_id": route_id, "direction": direction, "stop_sequence": k + 1,
                    "stop_id": stop_ids[s], "distance_from_start_km": round(float(dist[k]), 3),
                    "scheduled_offset_min": round(float(dist[k]) / midday_speed * 60, 1),
                    "is_timing_point": bool(timing),
                })
    routes = pd.DataFrame(route_rows)
    route_stops = pd.DataFrame(rs_rows)

    # 4) bottleneck junctions: the most shared stops (highest number of routes)
    degree = np.zeros(n_stops, dtype=int)
    for sl in stop_lists:
        degree[sl] += 1
    n_bott = max(1, int(round(ncfg["bottleneck_share"] * n_stops)))
    tie = make_rng(cfg["network_seed"], "network", 7).random(n_stops)
    bott_idx = np.lexsort((tie, -degree))[:n_bott]
    bott_mask = np.zeros(n_stops, dtype=bool)
    bott_mask[bott_idx] = True

    # 5) simulation attributes: demand rate per route, inbound direction
    dem = cfg["demand"]
    rate_rng = make_rng(cfg["network_seed"], "network", 11)
    rate = np.array([dem["base_rate"][t] for t in route_types]) \
        * rate_rng.lognormal(0.0, dem["route_rate_sigma"], len(route_types))
    d_origin = np.array([dist_centre[sl[0]] for sl in stop_lists])
    d_dest = np.array([dist_centre[sl[-1]] for sl in stop_lists])
    inbound_dir = np.where(d_dest < d_origin, 0, 1)

    net = Network(stops=stops, routes=routes, route_stops=route_stops)
    # arrays indexed by the internal stop index (used with route_stop_idx)
    net.stop_ids_all = stop_ids
    net.stop_lat_all = np.asarray(lat)
    net.stop_lon_all = np.asarray(lon)
    net.route_stop_idx = [np.asarray(sl) for sl in stop_lists]
    net.route_cum_km = cum_list
    net.route_rate = rate
    net.route_inbound_dir = inbound_dir
    net.route_bottlenecks = [bott_mask[np.asarray(sl)] for sl in stop_lists]
    net.bottleneck_stop_ids = set(stop_ids[bott_idx])
    net.n_full_routes = n_full_routes
    return net


def build_vehicles(cfg: dict, net: Network) -> None:
    """Create the fleet: a vehicle pool per route sized for its tightest peak headway, plus depot spares.

    Pool size = ceil(round-trip time / peak headway) + 1 spare. The reference
    headway is fixed per route type (not per timetable), so the base fleet is
    identical in every mode that shares the city.
    """
    rng = make_rng(cfg["network_seed"], "vehicles")
    ncfg = cfg["network"]
    rows, pools = [], []
    depot_xy = np.array([(la, lo) for _, la, lo in DEPOTS])
    letters = "ABCDEFGHJKLMNPRSTUVWXYZ"

    def add_vehicle(vtype, depot, commission, status):
        seated, total = VEHICLE_SPEC[vtype]
        if vtype == "articulated":
            fuel = rng.choice(["hybrid", "diesel"], p=[0.6, 0.4])
        elif vtype == "standard":
            fuel = rng.choice(["cng", "diesel", "electric"], p=[0.5, 0.35, 0.15])
        else:
            fuel = rng.choice(["cng", "diesel"], p=[0.7, 0.3])
        vid = len(rows)
        rows.append({
            "vehicle_id": f"V{vid + 1:04d}",
            "registration_no": f"LE{letters[int(rng.integers(0, len(letters)))]}-{int(rng.integers(1000, 9999))}",
            "vehicle_type": vtype, "capacity_seated": seated, "capacity_total": total,
            "depot": depot, "fuel_type": str(fuel), "commission_date": commission.isoformat(),
            "has_apc": bool(rng.random() < ncfg["apc_share"]), "status": status,
        })
        return vid

    routes = net.routes
    n_full = net.n_full_routes

    def fleet_for(r):
        rtype = routes.at[r, "route_type"]
        runtime = routes.at[r, "distance_km"] / SPEED_KMH[rtype]["pm_peak"] * 60
        pool = math.ceil(2 * (runtime + cfg["operations"]["layover_min"]) / FLEET_REFERENCE_HEADWAY[rtype]) + 1
        o = net.stops.loc[net.stops.stop_id == routes.at[r, "origin_stop_id"]].iloc[0]
        depot = DEPOTS[int(np.argmin(np.hypot(depot_xy[:, 0] - o.latitude, depot_xy[:, 1] - o.longitude)))][0]
        launch = dt.date.fromisoformat(routes.at[r, "launch_date"])
        ids = []
        for _ in range(pool):
            if launch >= NEW_ROUTE_CUTOFF:            # recently launched route -> new buses
                commission = launch - dt.timedelta(days=int(rng.integers(5, 40)))
            else:
                commission = dt.date(2012, 1, 1) + dt.timedelta(days=int(rng.integers(0, 4700)))
            ids.append(add_vehicle(ROUTE_TYPE_SPEC[rtype]["vehicle"], depot, commission, "active"))
        return ids

    for r in range(n_full):
        pools.append(fleet_for(r))
    spares = [add_vehicle(str(rng.choice(["standard", "minibus", "articulated"], p=[0.7, 0.2, 0.1])),
                          DEPOTS[int(rng.integers(0, len(DEPOTS)))][0],
                          dt.date(2014, 1, 1) + dt.timedelta(days=int(rng.integers(0, 3600))), "spare")
              for _ in range(ncfg["spare_vehicles"])]
    for r in range(n_full, len(routes)):          # extension routes (hidden_like) get new buses after the spares
        pools.append(fleet_for(r))

    net.vehicles = pd.DataFrame(rows)
    net.route_vehicle_pool = [np.asarray(p) for p in pools]
    net.spare_vehicle_idx = np.asarray(spares)
