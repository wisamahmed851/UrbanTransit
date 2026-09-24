"""Registered smart-card passengers and their travel habits.

Each passenger gets (hidden, not published) habits used by the ticket derivation:
* a primary route (commute) and a secondary route, weighted by route demand,
* an activity weight (heavy commuters vs occasional riders, lognormal),
* a preferred ticket type (single / day pass / monthly pass) and payment method.

When a trip has N card taps, N passengers are drawn from the pool of people
who use that route (primary route weighted 1.0, secondary 0.4) and who had
already registered their card - so nobody travels before registering.
"""

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .utils import make_rng

FARE_CATEGORY = {"regular": "standard", "student": "student", "senior": "senior", "disabled": "disabled"}
FARE_DISCOUNT = {"standard": 1.0, "student": 0.5, "senior": 0.5, "disabled": 0.0}
TICKET_TYPES = np.array(["single", "day_pass", "monthly_pass"])
REG_WINDOWS = [  # (start, end, share of passengers) - city registry, independent of the mode
    (dt.date(2019, 1, 1), dt.date(2025, 8, 31), 0.70),
    (dt.date(2025, 9, 1), dt.date(2026, 8, 15), 0.30),
]


@dataclass
class PassengerHabits:
    """Arrays aligned with the passengers table (row i = passenger i)."""
    ids: np.ndarray
    primary_route: np.ndarray
    secondary_route: np.ndarray
    activity: np.ndarray
    ticket_type: np.ndarray        # index into TICKET_TYPES
    pays_qr: np.ndarray
    fare_category: np.ndarray
    reg_date: np.ndarray           # datetime64[D]


def _random_dates(rng, start, end, n):
    days = (end - start).days
    return np.datetime64(start) + rng.integers(0, days + 1, n).astype("timedelta64[D]")


def _make_block(rng, n, id_start, route_choices, route_weights, reg_dates, net):
    """Create `n` passengers with IDs from id_start, choosing routes from route_choices."""
    ptype = rng.choice(["regular", "student", "senior", "disabled"], n, p=[0.70, 0.20, 0.08, 0.02])
    age = np.where(ptype == "student", rng.choice(["under_18", "18_25"], n, p=[0.4, 0.6]),
          np.where(ptype == "senior", "60_plus",
                   rng.choice(["18_25", "26_40", "41_60", "60_plus"], n, p=[0.25, 0.42, 0.28, 0.05])))
    gender = rng.choice(["M", "F", "X"], n, p=[0.58, 0.40, 0.02])
    w = route_weights / route_weights.sum()
    primary = rng.choice(route_choices, n, p=w)
    secondary = rng.choice(route_choices, n, p=w)
    # home stop: a random stop on the primary route
    home = np.array([net.stop_ids_all[net.route_stop_idx[r][int(rng.integers(0, len(net.route_stop_idx[r])))]]
                     for r in primary])
    activity = np.clip(rng.lognormal(0.0, 1.0, n), 0.05, 25.0)
    ttype = np.where(ptype == "student", rng.choice([0, 2], n, p=[0.55, 0.45]),
                     rng.choice([0, 1, 2], n, p=[0.72, 0.08, 0.20]))
    ids = np.array([f"P{i:06d}" for i in range(id_start, id_start + n)])
    df = pd.DataFrame({
        "passenger_id": ids,
        "card_number": [f"UTC-{int(a):04d}-{i:07d}" for a, i in zip(rng.integers(1000, 9999, n), range(id_start, id_start + n))],
        "passenger_type": ptype, "age_group": age, "gender": gender, "home_stop_id": home,
        "registration_date": np.datetime_as_string(reg_dates, unit="D"),
        "card_status": rng.choice(["active", "expired", "blocked"], n, p=[0.95, 0.03, 0.02]),
    })
    habits = PassengerHabits(ids=ids, primary_route=primary, secondary_route=secondary, activity=activity,
                             ticket_type=ttype, pays_qr=rng.random(n) < 0.15,
                             fare_category=np.vectorize(FARE_CATEGORY.get)(ptype), reg_date=reg_dates)
    return df, habits


def build_passengers(cfg: dict, net) -> tuple[pd.DataFrame, PassengerHabits]:
    """Passengers table + habits. The base registry depends only on network_seed (same in full and hidden_like)."""
    rng = make_rng(cfg["network_seed"], "passengers")
    n = cfg["n_passengers"]
    base_routes = np.arange(net.n_full_routes)
    shares = [w[2] for w in REG_WINDOWS]
    counts = [int(round(n * s)) for s in shares[:-1]]
    counts.append(n - sum(counts))
    reg = np.concatenate([_random_dates(rng, s, e, c) for (s, e, _), c in zip(REG_WINDOWS, counts)])
    reg = reg[rng.permutation(n)]
    df, hab = _make_block(rng, n, 1, base_routes, net.route_rate[:net.n_full_routes], reg, net)

    extra = cfg.get("extra_passengers", 0)
    if extra:
        # hidden_like: people who registered after the full period, some using the new routes
        rng2 = make_rng(cfg["seed"], "passengers", 2)
        all_routes = np.arange(len(net.routes))
        weights = net.route_rate.copy()
        weights[net.n_full_routes:] *= 3.0          # new routes attract new card holders
        reg2 = _random_dates(rng2, cfg["start_date"] - dt.timedelta(days=10), cfg["end_date"] - dt.timedelta(days=5), extra)
        df2, hab2 = _make_block(rng2, extra, n + 1, all_routes, weights, reg2, net)
        df = pd.concat([df, df2], ignore_index=True)
        hab = PassengerHabits(*[np.concatenate([getattr(hab, f), getattr(hab2, f)])
                                for f in PassengerHabits.__dataclass_fields__])
    return df, hab


class PassengerSampler:
    """Draws the passengers behind N card taps on a route, among people registered by `as_of`."""

    def __init__(self, habits: PassengerHabits, n_routes: int):
        self.h = habits
        self.n_routes = n_routes

    def pools_for(self, as_of: np.datetime64):
        """Per-route (indices, probabilities) for passengers registered on or before `as_of`."""
        ok = self.h.reg_date <= as_of
        idx_all = np.where(ok)[0]
        global_p = self.h.activity[idx_all] / self.h.activity[idx_all].sum()
        pools = []
        for r in range(self.n_routes):
            prim = idx_all[self.h.primary_route[idx_all] == r]
            sec = idx_all[self.h.secondary_route[idx_all] == r]
            idx = np.concatenate([prim, sec])
            if len(idx) == 0:
                pools.append((idx_all, global_p))       # brand-new route: anyone may try it
                continue
            w = np.concatenate([self.h.activity[prim], 0.4 * self.h.activity[sec]])
            pools.append((idx, w / w.sum()))
        return pools
