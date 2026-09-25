"""Run ONE configured data-quality rule, without re-running the whole Phase 3 pipeline.

Use it when a rule is added or changed and you only need its findings. `--source clean`
checks the existing Phase 3 clean tables (/urbantransit/clean); `--source parquet` checks the
Phase 2 Parquet exactly like data_quality.py does. The clean data itself is NOT modified; the
next full Phase 3 run (run_phase3.sh) applies the rule's action through clean_data.py.

Writes:  HDFS /<base>/dq/rule_checks/<source>/rule_id=<id>   (one row per violation)
         reports/dq_rule_<id>_<mode>.json                    (counts, overlap stats, samples)

Laravel analogy: like running one validation rule class against existing rows in tinker,
instead of re-running the whole import.

Usage: python spark_jobs/run_dq_rule.py --rule DQ22 [--mode full] [--source clean]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyspark.sql import functions as F  # noqa: E402

from spark_jobs.common import PROJECT_ROOT, get_logger, get_spark, hdfs_uri  # noqa: E402
from spark_jobs.dq_rules import DQData, load_dq_config, run_rule  # noqa: E402


class CleanData(DQData):
    """Same interface as DQData, but tables come from the Phase 3 clean output."""

    def table(self, name):
        if name not in self._tables:
            self._tables[name] = self.spark.read.parquet(hdfs_uri(self.mode, "clean", name))
        return self._tables[name]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule", required=True)
    ap.add_argument("--mode", default="full")
    ap.add_argument("--source", choices=["clean", "parquet"], default="clean")
    args = ap.parse_args()
    cfg = load_dq_config()
    rule = next((r for r in cfg["rules"] if r["id"] == args.rule), None)
    if rule is None:
        raise SystemExit(f"rule {args.rule} not found in config/data_quality.yaml")
    log, _ = get_logger(f"dq_rule_{args.rule}_{args.mode}")
    spark = get_spark(f"dq-rule-{args.rule}")
    d = (CleanData if args.source == "clean" else DQData)(spark, args.mode)

    out = hdfs_uri(args.mode, "dq", "rule_checks", args.source, f"rule_id={args.rule}")
    run_rule(d, rule, cfg["params"]).drop("rule_id").coalesce(1).write.mode("overwrite").parquet(out)
    viol = spark.read.parquet(out)
    rows = viol.count()
    table_rows = d.table(rule["table"]).count()
    result = {"rule": rule["id"], "defect_type": rule["defect_type"], "table": rule["table"], "action": rule["action"],
              "source": args.source, "mode": args.mode, "hdfs_violations": out, "table_rows": table_rows,
              "affected_rows": rows, "affected_pct": round(rows / table_rows * 100, 4) if table_rows else None,
              "affected_units": int(viol.agg(F.sum("units")).first()[0] or 0)}
    # numeric observed values (e.g. overlap seconds) get a distribution summary
    num = viol.select(F.col("observed_value").cast("double").alias("v")).filter("v IS NOT NULL")
    if rows and num.count() == rows:
        q = num.agg(F.expr("percentile_approx(v, array(0.1, 0.5, 0.9, 0.99))").alias("q"), F.max("v").alias("mx")).first()
        result["observed_value_percentiles"] = dict(zip(["p10", "p50", "p90", "p99"], q["q"])) | {"max": q["mx"]}
    result["samples"] = [r.asDict() for r in viol.orderBy("record_key").limit(cfg["params"]["sample_rows"]).collect()]
    path = PROJECT_ROOT / "reports" / f"dq_rule_{args.rule}_{args.mode}.json"
    path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    log.info("%s on %s/%s: %d of %d rows (%.4f%%) -> %s", rule["id"], args.source, rule["table"], rows, table_rows,
             result["affected_pct"] or 0, out)
    print(json.dumps({k: v for k, v in result.items() if k != "samples"}, indent=1, default=str))
    spark.stop()


if __name__ == "__main__":
    main()
