"""Shared helpers for the Spark jobs: SparkSession, logging to reports/processing_logs, timers, HDFS sizes.

NestJS analogy: this is the shared module the jobs import (like a ConfigService + Logger
provider), so every job gets the same Spark settings and log format.
"""

import logging
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyspark.sql import SparkSession  # noqa: E402

from config import settings  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "reports" / "processing_logs"


def base_dir(mode: str) -> str:
    """HDFS base folder for a dataset mode: /urbantransit for full, /urbantransit_<mode> otherwise."""
    return settings.HDFS_BASE_DIR if mode == "full" else f"{settings.HDFS_BASE_DIR}_{mode}"


def hdfs_uri(mode: str, *parts: str) -> str:
    """Fully qualified HDFS URI, e.g. hdfs://localhost:9000/urbantransit/raw/tickets."""
    return settings.HDFS_URI.rstrip("/") + "/".join([base_dir(mode), *parts]).replace("//", "/")


def get_logger(job: str) -> tuple[logging.Logger, Path]:
    """Logger writing to stdout and to reports/processing_logs/<job>_<timestamp>.log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{job}_{datetime.now():%Y%m%d_%H%M%S}.log"
    log = logging.getLogger(job)
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(path, encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)
    return log, path


def get_spark(app: str) -> SparkSession:
    """SparkSession configured from config/settings.py (.env), tuned for local mode in 8 GB WSL."""
    os.makedirs(settings.SPARK_LOCAL_DIR, exist_ok=True)
    builder = SparkSession.builder.appName(f"{settings.SPARK_APP_NAME}-{app}").master(settings.SPARK_MASTER)
    for key, value in settings.SPARK_CONF.items():
        builder = builder.config(key, value)
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


@contextmanager
def timed(log: logging.Logger, label: str, sink: dict | None = None, key: str | None = None):
    """Log how long a block takes; optionally store the seconds in sink[key or label]."""
    t0 = time.perf_counter()
    yield
    dt = time.perf_counter() - t0
    if sink is not None:
        sink[key or label] = round(dt, 2)
    log.info(f"{label}: {dt:.2f} s")


def hdfs_du_bytes(path: str) -> int:
    """Size in bytes of an HDFS path (hdfs dfs -du -s)."""
    out = subprocess.run(["hdfs", "dfs", "-du", "-s", path], capture_output=True, text=True, check=True).stdout
    return int(out.split()[0])


def hdfs_file_count(path: str) -> int:
    """Number of files under an HDFS path, excluding _SUCCESS markers."""
    out = subprocess.run(["hdfs", "dfs", "-ls", "-R", path], capture_output=True, text=True, check=True).stdout
    return sum(1 for line in out.splitlines() if line.startswith("-") and not line.rstrip().endswith("_SUCCESS"))
