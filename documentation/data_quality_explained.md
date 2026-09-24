# How Data Quality and Cleaning Work (explainer)

Phase 3 turns the Phase 2 Parquet into trusted, clean Parquet. Results:
[reports/data_quality_report.md](../reports/data_quality_report.md),
[reports/cleaning_report.md](../reports/cleaning_report.md),
[reports/dq_evaluation_full.md](../reports/dq_evaluation_full.md),
[reports/hidden_readiness_report.md](../reports/hidden_readiness_report.md).
Rules and reasons: [cleaning_rules.md](cleaning_rules.md).

## The pieces, in Laravel / NestJS terms

| Piece | What it does | Analogy |
|---|---|---|
| `config/data_quality.yaml` | Lists every rule: check type, table/columns, thresholds, severity, cleaning action, rationale | The `rules()` array of a Form Request |
| `spark_jobs/dq_rules.py` | Implements each *check type* once (required value, foreign key, duplicate key, range, time order, ...) | Reusable validation rule classes (`Rule::exists`, `Rule::unique`, `min`, `max`) |
| `spark_jobs/profile_data.py` | Counts, nulls, distinct values, min/max, quartiles, top values per column | `SELECT COUNT(*), COUNT(DISTINCT x), MIN(x) ...` for every column |
| `spark_jobs/data_quality.py` | Runs every rule, stores one row per violation in HDFS, writes the report | A validation pipe that collects all errors instead of stopping at the first |
| `spark_jobs/clean_data.py` | Applies each rule's action: correct / flag / remove / quarantine; writes clean Parquet, quarantine and the cleaning log | Model mutators + a `failed_jobs` table + an audit log |
| `spark_jobs/dq_evaluate.py` | Grades detection against the generator's answer key (manifest) | The test suite - kept separate from the code it tests |
| `spark_jobs/no_manifest_guard.py` | Blocks any attempt of a pipeline job to open the manifest | A NestJS guard in front of the jobs |

## Why rules are generic

Hidden evaluation data will contain new stops, unknown vehicles, new schedules and new kinds of
errors. So no rule mentions a specific ID or value: a rule says *"entry_stop_id must exist in
stops"*, not *"S9xxx is invalid"*. Thresholds (valid delay range, capacity factor, operating
area, time windows) live in the YAML. The same code ran on `hidden_like` with only `--mode`
changed.

## The flow

```
Phase 2 Parquet + ingestion quarantine (HDFS)
   |-- profile_data.py  -> reports/data_profile.md (+ JSON, HDFS dq/profile.json)
   |-- data_quality.py  -> HDFS dq/violations/rule_id=*/  (rule_id, table, record_key, column, observed_value, units)
   |                       reports/data_quality_report.md (+ JSON, HDFS dq/summary.json)
   '-- clean_data.py    -> HDFS clean/<table>/            (clean rows + dq_flags array)
                           HDFS clean_quarantine/<table>/ (rows that cannot be trusted + original record)
                           HDFS cleaning_log/             (key, issue, rule, original, corrected, action, final status)
check per table: rows in = clean + removed + quarantined
```

## Choosing an action

1. **Can the right value be *derived* from other fields with certainty?** -> **correct**
   (e.g. `delay_minutes` = actual - scheduled arrival; a trip's route from its schedule row;
   stop order from distance along the route). If the derivation fails, the rule's fallback applies.
2. **Is the row still useful with the problem noted?** -> **flag** (e.g. an unknown passenger
   still counts for route demand; a delay at an unknown stop still counts for the route).
3. **Is it an exact duplicate?** -> **remove** the extra copies (conflicting copies are quarantined).
4. **Otherwise** (the true value is unknown and the row would mislead) -> **quarantine**.

## Two lessons from running it

* **Big single plans stalled Spark local mode.** Unioning 25 rule results (many broadcast
  joins) into one write, and later all cleaning-log parts into one write, left Spark waiting
  with idle CPUs. Running each rule / log part as its own small job fixed it and made timing
  per rule visible.
* **Rows quarantined at ingestion are not lost.** Delay rows with text in `delay_minutes`
  were quarantined in Phase 2; Phase 3 re-parses them, recomputes the value from the timestamps
  and recovers them into the clean data (logged as corrected).
