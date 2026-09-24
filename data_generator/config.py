"""Load generator_config.yaml and merge the `common` block with one mode.

Laravel analogy: like `config('generator.full')` where the mode-specific values
override the defaults - a recursive merge of two nested dictionaries.
"""

import copy
import datetime as dt
from pathlib import Path

import yaml

CONFIG_FILE = Path(__file__).resolve().parent / "generator_config.yaml"
MODES = ("full", "sample", "hidden_like")


def _deep_merge(base: dict, override: dict) -> dict:
    """Return a copy of `base` with `override` merged in (nested dicts are merged, not replaced)."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _to_date(value) -> dt.date:
    """YAML already turns 2025-09-01 into a date; accept strings too."""
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))


def load_config(mode: str) -> dict:
    """Return the effective configuration for `mode` (full | sample | hidden_like)."""
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}; choose one of {MODES}")
    with open(CONFIG_FILE, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    cfg = _deep_merge(raw["common"], raw["modes"][mode])
    cfg["mode"] = mode
    cfg["start_date"] = _to_date(cfg["start_date"])
    cfg["end_date"] = _to_date(cfg["end_date"])
    cfg["gps_window_start"] = _to_date(cfg["gps_window_start"])
    cfg["gps_window_days"] = cfg.get("gps_window_days", cfg["gps"]["window_days"])
    cfg.setdefault("network_extension", None)
    cfg.setdefault("extra_passengers", 0)
    cfg.setdefault("delay_spike_days", 0)
    return cfg
