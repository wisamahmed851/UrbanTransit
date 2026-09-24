"""Idempotency check for the cleaning job: run it twice and compare the outputs.

clean_data.py writes, per table, a fingerprint of the clean Parquet and of the quarantine
(sum of 64-bit hashes of every row, plus row counts) and a fingerprint of the whole cleaning log.
This script compares the metrics of two runs; identical fingerprints and counts mean the second
run produced exactly the same data.

Usage (see run_phase3.sh):
    cp reports/cleaning_metrics_full.json reports/cleaning_metrics_full_run1.json
    python spark_jobs/clean_data.py --mode full
    python spark_jobs/check_idempotency.py --mode full
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="full")
    args = ap.parse_args()
    rep = PROJECT_ROOT / "reports"
    a = json.loads((rep / f"cleaning_metrics_{args.mode}_run1.json").read_text())
    b = json.loads((rep / f"cleaning_metrics_{args.mode}.json").read_text())
    comps = []
    tb = {t["table"]: t for t in b["tables"]}
    for t in a["tables"]:
        u = tb[t["table"]]
        for key in ("rows_clean", "rows_removed", "rows_quarantined", "fingerprint_clean", "fingerprint_quarantine"):
            comps.append({"output": f"{t['table']}.{key}", "run1": str(t[key]), "run2": str(u[key]), "same": t[key] == u[key]})
    comps.append({"output": "cleaning_log.rows", "run1": str(a["cleaning_log_rows"]), "run2": str(b["cleaning_log_rows"]),
                  "same": a["cleaning_log_rows"] == b["cleaning_log_rows"]})
    comps.append({"output": "cleaning_log.fingerprint", "run1": a["cleaning_log_fingerprint"], "run2": b["cleaning_log_fingerprint"],
                  "same": a["cleaning_log_fingerprint"] == b["cleaning_log_fingerprint"]})
    ok = all(c["same"] for c in comps)
    (rep / f"cleaning_idempotency_{args.mode}.json").write_text(
        json.dumps({"mode": args.mode, "result": "PASS" if ok else "FAIL", "comparisons": comps}, indent=2), encoding="utf-8")
    print(f"IDEMPOTENCY {'PASS' if ok else 'FAIL'}: {sum(c['same'] for c in comps)}/{len(comps)} outputs identical")
    for c in comps:
        if not c["same"]:
            print("  differs:", c)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
