"""Central project settings, loaded from the .env file at the repository root."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _env(key: str, default: str | None = None) -> str | None:
    return os.getenv(key, default)


# ---- Local paths ----
RAW_DATA_DIR = PROJECT_ROOT / "raw_data"
PROCESSED_DATA_DIR = PROJECT_ROOT / "processed_data"
PARQUET_DATA_DIR = PROJECT_ROOT / "parquet_data"
SAMPLE_DATA_DIR = PROJECT_ROOT / "sample_data"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"
THRESHOLDS_FILE = PROJECT_ROOT / "config" / "thresholds.yaml"

# ---- HDFS ----
HDFS_URI = _env("HDFS_URI", "hdfs://localhost:9000")
HDFS_BASE_DIR = _env("HDFS_BASE_DIR", "/urbantransit")

# ---- Spark ----
SPARK_MASTER = _env("SPARK_MASTER", "local[*]")
SPARK_APP_NAME = _env("SPARK_APP_NAME", "UrbanTransitIQ")
# Scratch space inside the WSL disk, not /tmp (wiped when WSL cold-boots the distro)
SPARK_LOCAL_DIR = os.path.expanduser(_env("SPARK_LOCAL_DIR", "~/spark_tmp"))
SPARK_CONF = {
    "spark.local.dir": SPARK_LOCAL_DIR,
    "spark.driver.memory": _env("SPARK_DRIVER_MEMORY", "2g"),
    "spark.sql.shuffle.partitions": _env("SPARK_SHUFFLE_PARTITIONS", "8"),
    # Timestamps in the raw files are local transit time without a zone; keeping the session
    # in UTC means Spark never shifts them.
    "spark.sql.session.timeZone": "UTC",
    "spark.hadoop.fs.defaultFS": HDFS_URI,
    # Strict date/time parsing: an impossible value like 2025-13-45 becomes a parse failure
    # (-> quarantine) instead of being silently rolled over by the legacy parser.
    "spark.sql.legacy.timeParserPolicy": "CORRECTED",
    "spark.sql.parquet.compression.codec": "snappy",
    "spark.sql.adaptive.enabled": "true",               # merge small shuffle partitions automatically
    "spark.sql.adaptive.coalescePartitions.enabled": "true",
    "spark.ui.showConsoleProgress": "false",            # keep job logs readable
}

# ---- MySQL ----
MYSQL_HOST = _env("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(_env("MYSQL_PORT", "3306"))
MYSQL_DATABASE = _env("MYSQL_DATABASE", "urbantransit_iq")
MYSQL_USER = _env("MYSQL_USER")
MYSQL_PASSWORD = _env("MYSQL_PASSWORD")
MYSQL_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
)

# ---- Flask ----
FLASK_HOST = _env("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(_env("FLASK_PORT", "5000"))
SECRET_KEY = _env("SECRET_KEY")
JWT_SECRET_KEY = _env("JWT_SECRET_KEY")


def hdfs_path(*parts: str) -> str:
    """Build a fully qualified HDFS URI under the project base directory."""
    return "/".join([HDFS_URI.rstrip("/"), HDFS_BASE_DIR.strip("/"), *parts])


def load_thresholds() -> dict:
    with open(THRESHOLDS_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)
