"""Small shared helpers: deterministic random streams, logging, time formatting."""

import datetime as dt
import logging
import sys

import numpy as np

# Stable integer codes for independent random streams. Using a separate stream per
# purpose (and per month) means that changing one part of the generator does not
# shift the random numbers used by every other part, and a month can be generated
# on its own and still give identical output.
STREAM = {
    "network": 1, "network_ext": 2, "calendar": 3, "vehicles": 4, "passengers": 5,
    "weather": 6, "trips": 7, "tickets": 8, "gps": 9, "defects": 10, "defects_ref": 11,
}


def make_rng(seed: int, stream: str, *extra: int) -> np.random.Generator:
    """Return a NumPy random generator for (seed, stream, extra...).

    Same inputs -> same sequence of random numbers on every run and machine.
    Example: make_rng(42, "trips", 2025, 9) is the stream for September 2025 trips.
    """
    return np.random.default_rng(np.random.SeedSequence([seed, STREAM[stream], *extra]))


def get_logger(name: str = "generator") -> logging.Logger:
    """Logger that prints timestamped progress lines to stdout."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def month_range(start: dt.date, end: dt.date) -> list[tuple[int, int]]:
    """List of (year, month) pairs covering start..end inclusive."""
    months, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def date_range(start: dt.date, end: dt.date) -> list[dt.date]:
    """All dates from start to end inclusive."""
    return [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]


def minutes_to_timestamps(day_ns: np.ndarray, minutes: np.ndarray) -> np.ndarray:
    """Combine day (datetime64[ns] at midnight) + minutes after midnight -> 'YYYY-MM-DD HH:MM:SS' strings.

    Minutes can exceed 1440 (trips that finish after midnight roll into the next day).
    """
    secs = np.round(np.asarray(minutes, dtype="float64") * 60).astype("int64")
    ts = np.asarray(day_ns).astype("datetime64[s]") + secs.astype("timedelta64[s]")
    # datetime_as_string gives 'YYYY-MM-DDTHH:MM:SS'; the dataset uses a space separator
    return np.char.replace(np.datetime_as_string(ts, unit="s"), "T", " ").astype(object)


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km (works on scalars or NumPy arrays)."""
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))
