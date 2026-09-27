"""Small, explicit job-state recorder for Spark and loader commands.

The web API only reads job state.  A shell runner starts a row before launching
Spark and marks it success/failed afterwards, so a terminal closing never causes
the dashboard to invent a successful run.

Examples (from the project root):

    python database/job_monitor.py start --name phase5_analytics --log reports/processing_logs/phase5.log
    python database/job_monitor.py finish --id 12 --status success
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.app import create_app  # noqa: E402
from src.extensions import db  # noqa: E402
from src.models.ops import JobRun  # noqa: E402
from src.models.rbac import utcnow  # noqa: E402


def start(name: str, log_path: str | None) -> int:
    app = create_app()
    with app.app_context():
        row = JobRun(job_name=name, status="running", log_path=log_path)
        db.session.add(row)
        db.session.commit()
        return int(row.id)


def finish(job_id: int, status: str) -> None:
    app = create_app()
    with app.app_context():
        row = db.session.get(JobRun, job_id)
        if row is None:
            raise SystemExit(f"Job run {job_id} does not exist.")
        row.status = status
        row.finished_at = utcnow()
        db.session.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a Spark or loader job for the dashboard.")
    commands = parser.add_subparsers(dest="command", required=True)
    begin = commands.add_parser("start", help="create a running job record")
    begin.add_argument("--name", required=True)
    begin.add_argument("--log", default=None)
    end = commands.add_parser("finish", help="finish an existing job record")
    end.add_argument("--id", required=True, type=int)
    end.add_argument("--status", required=True, choices=("success", "failed"))
    args = parser.parse_args()
    if args.command == "start":
        print(start(args.name, args.log))
    else:
        finish(args.id, args.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
