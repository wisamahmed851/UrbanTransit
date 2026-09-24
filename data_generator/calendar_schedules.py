"""Service calendars (which timetable runs on which day) and schedules (headways + running times).

Service calendar design
-----------------------
* Each timetable period (autumn_2025, winter_spring_2026, summer_2026, autumn_2026)
  has three calendars: weekday (Mon-Fri), Saturday and Sunday. A new period means
  new service IDs and new schedule rows - this is how "new schedules appear mid-year".
* HOL runs on public holidays (Sunday-like timetable). Holidays are *removed* from
  the normal calendars and *added* to HOL through the `exceptions` list, exactly
  like GTFS calendar_dates.
* RAM_WKDY_26 replaces the weekday timetable during Ramadan.

`active_service()` resolves a date to exactly one service using only the
published calendar data, so the files are self-consistent.
"""

import datetime as dt

from .network import SPEED_KMH

PERIODS = [  # time-of-day periods: name, start minute, end minute
    ("early", 5 * 60 + 30, 7 * 60),
    ("am_peak", 7 * 60, 10 * 60),
    ("midday", 10 * 60, 16 * 60),
    ("pm_peak", 16 * 60, 19 * 60 + 30),
    ("evening", 19 * 60 + 30, 22 * 60 + 30),
]
# Weekday headways (minutes) per route type for [early, am_peak, midday, pm_peak, evening]
BASE_HEADWAY = {
    "brt":    [15, 10, 15, 10, 20],
    "trunk":  [30, 20, 30, 20, 45],
    "local":  [45, 30, 60, 30, 60],
    "feeder": [60, 45, 90, 45, 90],
}
DAY_TYPE_HEADWAY_FACTOR = {"weekday": 1.0, "saturday": 1.25, "sunday": 1.5, "holiday": 1.5, "ramadan_weekday": 1.1}
DAY_TYPE_SPEED_FACTOR = {"weekday": 1.0, "saturday": 1.1, "sunday": 1.15, "holiday": 1.15, "ramadan_weekday": 1.0}
PERIOD_TAG = {"autumn_2025": "AUT25", "winter_spring_2026": "WSP26", "summer_2026": "SUM26", "autumn_2026": "AUT26"}
DOW = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _period_headway_factor(timetable_period: str, rtype: str, period: str) -> float:
    """Timetable changes between periods (the 'new schedules')."""
    peak = period in ("am_peak", "pm_peak")
    if timetable_period == "winter_spring_2026" and rtype in ("brt", "trunk") and peak:
        return 0.8                       # January timetable: more frequent peak service on busy corridors
    if timetable_period == "summer_2026" and period in ("midday", "evening"):
        return 1.5                       # summer holidays: off-peak service cut
    if timetable_period == "autumn_2026" and peak:
        return 0.8 if rtype in ("brt", "trunk") else 0.9
    return 1.0


def _d(value) -> dt.date:
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))


def build_service_calendar(cfg: dict) -> list[dict]:
    """Return the service calendar as a list of dicts (written as JSON)."""
    ccfg = cfg["calendar"]
    start, end = cfg["start_date"], cfg["end_date"]
    holidays = {_d(d): name for d, name in ccfg["holidays"] if start <= _d(d) <= end}
    ram_start, ram_end = (_d(x) for x in ccfg["ramadan"])
    has_ramadan = ram_start <= end and ram_end >= start

    def is_ramadan_weekday(d):
        return has_ramadan and ram_start <= d <= ram_end and d.weekday() < 5

    services = []
    for name, p_start, p_end in ccfg["timetable_periods"]:
        p_start, p_end = _d(p_start), _d(p_end)
        if p_end < start or p_start > end:
            continue                      # period not used by this mode
        tag = PERIOD_TAG[name]
        for day_type, sid, days in (("weekday", f"WKDY_{tag}", DOW[:5]),
                                    ("saturday", f"SAT_{tag}", ["sat"]),
                                    ("sunday", f"SUN_{tag}", ["sun"])):
            exceptions = []
            d = max(p_start, start)
            while d <= min(p_end, end):
                if DOW[d.weekday()] in days:
                    if d in holidays:
                        exceptions.append({"date": d.isoformat(), "exception_type": "removed", "reason": holidays[d]})
                    elif day_type == "weekday" and is_ramadan_weekday(d):
                        exceptions.append({"date": d.isoformat(), "exception_type": "removed", "reason": "Ramadan timetable"})
                d += dt.timedelta(days=1)
            services.append({"service_id": sid, "service_name": f"{day_type.title()} {name.replace('_', ' ')}",
                             "day_type": day_type, "timetable_period": name, "days_of_week": days,
                             "start_date": p_start.isoformat(), "end_date": p_end.isoformat(),
                             "exceptions": exceptions})
    if has_ramadan:
        exc = [{"date": d.isoformat(), "exception_type": "removed", "reason": n}
               for d, n in sorted(holidays.items()) if ram_start <= d <= ram_end and d.weekday() < 5]
        services.append({"service_id": "RAM_WKDY_26", "service_name": "Ramadan weekday 2026", "day_type": "ramadan_weekday",
                         "timetable_period": "ramadan_2026", "days_of_week": DOW[:5],
                         "start_date": ram_start.isoformat(), "end_date": ram_end.isoformat(), "exceptions": exc})
    services.append({"service_id": "HOL", "service_name": "Public holiday service", "day_type": "holiday",
                     "timetable_period": "all_year", "days_of_week": [],
                     "start_date": start.isoformat(), "end_date": end.isoformat(),
                     "exceptions": [{"date": d.isoformat(), "exception_type": "added", "reason": n}
                                    for d, n in sorted(holidays.items())]})
    return services


def active_service(calendar: list[dict], date: dt.date) -> dict:
    """Return the one service that runs on `date` (GTFS rules: days_of_week +/- exceptions)."""
    iso, dow = date.isoformat(), DOW[date.weekday()]
    hits = []
    for s in calendar:
        exc = {e["date"]: e["exception_type"] for e in s["exceptions"]}
        runs = s["start_date"] <= iso <= s["end_date"] and dow in s["days_of_week"] and exc.get(iso) != "removed"
        if runs or exc.get(iso) == "added":
            hits.append(s)
    if len(hits) != 1:
        raise ValueError(f"{date}: expected exactly one active service, found {[h['service_id'] for h in hits]}")
    return hits[0]


def build_schedules(cfg: dict, net, calendar: list[dict]):
    """Create schedule rows and a lookup used to expand trips.

    Returns (rows, lookup) where lookup[service_id][route_idx][direction] is a list of
    (period_idx, start_min, end_min, headway, runtime, schedule_id, valid_from, valid_to).
    """
    routes = net.routes
    rows, lookup, n = [], {}, 0
    for s in calendar:
        tp = s["timetable_period"]
        day_type = s["day_type"]
        s_start, s_end = _d(s["start_date"]), _d(s["end_date"])
        lookup[s["service_id"]] = {}
        for r in range(len(routes)):
            launch = _d(routes.at[r, "launch_date"])
            if launch > s_end:
                continue                  # route does not exist yet in this timetable
            rtype = routes.at[r, "route_type"]
            dist = float(routes.at[r, "distance_km"])
            valid_from = max(s_start, launch)
            lookup[s["service_id"]][r] = {0: [], 1: []}
            for direction in (0, 1):
                for p, (pname, p_start, p_end) in enumerate(PERIODS):
                    hw = BASE_HEADWAY[rtype][p] * DAY_TYPE_HEADWAY_FACTOR[day_type]
                    if tp in PERIOD_TAG:
                        hw *= _period_headway_factor(tp, rtype, pname)
                    hw = max(5, int(round(hw)))
                    speed = SPEED_KMH[rtype][pname] * DAY_TYPE_SPEED_FACTOR[day_type]
                    runtime = round(dist / speed * 60, 1)
                    n += 1
                    sid = f"SCH{n:06d}"
                    rows.append({"schedule_id": sid, "route_id": routes.at[r, "route_id"], "service_id": s["service_id"],
                                 "direction": direction, "period": pname,
                                 "start_time": f"{p_start // 60:02d}:{p_start % 60:02d}",
                                 "end_time": f"{p_end // 60:02d}:{p_end % 60:02d}",
                                 "headway_min": hw, "planned_runtime_min": runtime,
                                 "valid_from": valid_from.isoformat(), "valid_to": s_end.isoformat()})
                    lookup[s["service_id"]][r][direction].append(
                        (p, p_start, p_end, hw, runtime, sid, valid_from, s_end))
    return rows, lookup


def departures_for(period_rows, route_idx: int, direction: int, date: dt.date):
    """Scheduled departure minutes for one route/direction/date from its schedule rows.

    A small route-specific phase offset stops every route departing on the hour.
    Returns list of (dep_min, period_idx, headway, runtime, schedule_id).
    """
    out = []
    phase = (route_idx * 7 + direction * 11) % 60
    for p, p_start, p_end, hw, runtime, sid, vfrom, vto in period_rows:
        if not (vfrom <= date <= vto):
            continue
        first = p_start + (phase % hw)
        for m in range(first, p_end, hw):
            out.append((float(m), p, hw, runtime, sid))
    return out
