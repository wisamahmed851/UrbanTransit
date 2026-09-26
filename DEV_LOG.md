# Development Log — UrbanTransit IQ

Dated record of work completed, problems, fixes, Spark failures, dataset changes and
model errors. Newest entries at the bottom. Command-level detail lives in
[documentation/COMMAND_LOG.md](documentation/COMMAND_LOG.md).

---

## 2026-09-24 — Phase 0: setup and repository (CMD-001)

### Environment detected
| Item | Found |
|---|---|
| OS | Windows 11 Pro, build 10.0.22000 (21H2) |
| RAM / free disk | 14.9 GB / C: 18.2 GB, D: 195.5 GB |
| Python | 3.13.7 |
| Git | 2.45.1.windows.1 |
| Java | 1.8.0_401 JRE only, `JAVA_HOME` not set (Spark needs JDK 11/17) |
| Docker | not installed |
| WSL | feature available, no Linux distribution installed |
| MySQL | 8.4.3 present via Laragon (`D:\laragon`), not running |
| Shell | not elevated (no admin rights in the assistant's session) |

### Work completed
- Initialised Git repository (`main`), created folder layout with `.gitkeep` files, `.gitignore`, `.gitattributes` (LF for `.sh`/`.py` so scripts run in Linux).
- Created README, AI_USAGE, DEV_LOG, LICENSE (MIT), `documentation/COMMAND_LOG.md`.

### Problems and fixes
- Git warned it would convert `.gitignore` to CRLF on Windows. Added `.gitattributes` forcing LF for shell/Python/YAML files so HDFS scripts do not break under bash.

### Pending (Phase 0)
- Decision on Hadoop/HDFS host: WSL2 vs Docker (awaiting user OK).
- Java JDK 17, Spark/PySpark, Hadoop, MySQL database/user, config, verification scripts.

## 2026-09-24 — Phase 0 decisions (CMD-002, CMD-003)
- GitHub origin set to `https://github.com/wisamahmed851/UrbanTransit.git`; first push succeeded via Git Credential Manager.
- **Hadoop/HDFS host: WSL2 Ubuntu 24.04** (approved; Docker rejected). Distro will be moved to `D:\WSL\Ubuntu-24.04` via export/unregister/import because C: has ~18 GB free.
- **MySQL** will run inside WSL; Laragon MySQL left untouched.
- venv, JDK 17, Hadoop, Spark, HDFS data and MySQL data will live inside the WSL ext4 disk (on D:), not on `/mnt/d` (slow cross-filesystem I/O).
- `.wslconfig`: memory 8 GB, 4 CPUs, 4 GB swap on D:.
- pip cache → `D:\DevCache\pip`, npm cache → `D:\DevCache\npm`.
- Correction: CMD-001 log said "26 folders"; the actual count is 25 (matches the SRS). Text error only.

## 2026-09-24 — Phase 0: WSL service hang (CMD-004)
- **Problem:** after the user's WSL install, every `wsl -d Ubuntu -e <cmd>` from the assistant hangs (even `whoami`), and `wsl --shutdown` also hangs; `vmmemWSL` stays running. `wsl --status` / `wsl -l -v` still answer (`Ubuntu Running 2`).
- **Tried:** closing stdin, PowerShell `Start-Process` with redirected output, killing stale `wsl.exe` processes, repeated `wsl --shutdown`. None worked.
- **Needed:** restart of `WSLService` from an elevated PowerShell (or a reboot). The assistant has no admin rights.
- Meanwhile: old pip/npm caches on C: purged (+0.7 GB); pinned requirements, config and verification scripts written but **not yet run**.

## 2026-09-24 — Phase 0: WSL rebuilt on D:, stack installed (CMD-005)
- **Dataset/env change:** the distro the user installed was "Ubuntu" = **26.04.1 LTS** (Python 3.14.4) with **no user created** (first-run setup never finished; likely tied to the earlier hang). It was replaced by **Ubuntu-24.04** (24.04.5, Python 3.12.3) installed directly at `D:\WSL\Ubuntu-24.04` with `wsl --install --location`; the empty 26.04 distro was unregistered.
- Default user `wisam` (sudo) set in `/etc/wsl.conf`; systemd enabled; `appendWindowsPath=false`.
- **Problem:** systemd user session failed ("Failed to connect to bus"). **Fix:** `loginctl enable-linger wisam`. A cold-start race can still slow the very first WSL call after the VM boots.
- **Problem:** sshd check via `pgrep` wrongly failed because Ubuntu 24.04 socket-activates sshd. **Fix:** test `ssh localhost true`.
- `.wslconfig`: user commented out `swapFile=` while fixing the WSL hang; swap now uses the default location.

| Component | Version | Location |
|---|---|---|
| Ubuntu (WSL2) | 24.04.5 LTS, kernel 6.18.33.2 (WSL 2.7.14) | `D:\WSL\Ubuntu-24.04\ext4.vhdx` |
| Java | OpenJDK 17.0.20.1 | `/usr/lib/jvm/java-17-openjdk-amd64` |
| Hadoop | 3.4.3 (sha512 verified) | `/opt/hadoop` → `/opt/hadoop-3.4.3`, data `~/hadoop_data` |
| MySQL | 8.0.46 | data `/var/lib/mysql` |
| Python | 3.12.3 | venv `~/venvs/urbantransit` |
- `pip install -r requirements.txt` succeeded (venv 1.6 GB, including a 305 MB unused GPU library pulled by xgboost).

### Spark / HDFS failures and fixes (CMD-005)
| Problem | Cause | Fix |
|---|---|---|
| `NoSuchFileException: /tmp/blockmgr-...` in Spark SQL shuffle | WSL powers the distro off when no `wsl.exe` client is attached; the next cold boot's systemd `/tmp` cleanup raced with Spark | `spark.local.dir=~/spark_tmp`; Parquet check writes there |
| HDFS daemons disappeared between commands | Same idle power-off (NameNode got SIGTERM) | Keep an Ubuntu terminal open while working, or run a workflow in one WSL session |
| HDFS start failed ("Connection refused" :9000) on a cold boot | `ssh.socket` not listening yet | `ensure_sshd` retries 6×5 s |
| Pid files still in `/tmp` | Daemons launched over ssh only read `hadoop-env.sh` | `HADOOP_PID_DIR` written into `hadoop-env.sh` by `setup_hadoop.sh` |
| `echo ... \| pyspark` → `spark` undefined | Piped stdin isn't interactive, so the PySpark startup file never runs | `PYSPARK_DRIVER_PYTHON_OPTS=-i` |
| PySpark: "does not yet fully support pandas >= 3.0.0" | pandas 3.0.6 pinned | Pinned `pandas==2.3.3` |

### Versions (Phase 0 final)
| Component | Version |
|---|---|
| PySpark / Spark | 4.2.0 (Scala 2.13, bundled) |
| Hadoop | 3.4.3 |
| Java | OpenJDK 17.0.20.1 |
| Python | 3.12.3 |
| MySQL | 8.0.46 |
| pandas / NumPy | 2.3.3 / 2.5.3 |
| scikit-learn / XGBoost / statsmodels | 1.9.1 / 3.4.1 / 0.15.0 |
| Flask | 3.1.3 |

### Phase 0 completion (2026-09-24)
Checklist run in full (repo checks on Windows, WSL checks in one session from a cold distro): **12/12 PASS**.
Disk: WSL disk `D:\WSL\Ubuntu-24.04\ext4.vhdx` = 8.70 GB; C: 13.3 GB free; D: 186.3 GB free.
**Known quirk:** WSL powers the distro off shortly after the last `wsl.exe` session closes, which stops HDFS. Keep an Ubuntu terminal open while working, or restart HDFS with `hdfs_scripts/start_hdfs.sh`.

## 2026-09-24 — Phase 1: data generator (CMD-006 to CMD-008)
- Generator written (`data_generator/`), sample mode validated 52/52 on the first run.
- **Tuning (dry run):** first settings gave ~4.0M tickets/yr and delay records on ~75% of trips (median 8 min). Reduced card share, weekday peak congestion and junction penalty; delay records now need >= 5 min late.
- **Failure: validate_dataset (full) 58/59** - 102 more capacity violations than injected. **Cause:** breakdown swaps reported the load of the original (bigger) bus on the smaller spare. **Fix:** cap the load at the capacity of the vehicle that finishes the trip. Full dataset regenerated.
- **Failure:** first full validation attempt produced an empty log (exit code 4) because it was wrapped in `/usr/bin/time -v`; rerun with bash `time`.
- **Realism review failed on real statistics (full run #2):** delay did not depend on load (flat ~11.4 min across occupancy bands), peak vs off-peak was inverted (11.0 vs 12.4 min, partly because only already-late records were averaged), bunching was almost absent (0.16% of origin headways), BRT under-used (mean occupancy 0.23), Independence Day event showed -3% uplift (holiday compared to a normal Friday). **Fix:** headway-instability feedback, stronger dwell/crowding effects, crush load 1.3x, wider departure deviation, higher demand with lower card share (config `operations:` / `demand:`), tuned with in-memory dry runs (`tune_check.py`); stats now measure trip-level delays, first/last-stop headways and event-window uplift.
- **Failure:** pipeline script launched as `wsl.exe -e bash /mnt/d/...` from Git Bash exited 127 - Git Bash's MSYS path conversion rewrote `/mnt/d/...` to `C:/Program Files/Git/mnt/d/...`. **Fix:** `MSYS_NO_PATHCONV=1`.

### Phase 1 completion (2026-09-24)
- Final full dataset (seed 42): 62 files, 1,288 MB, generated in 454 s. tickets 3.03M rows (2.99M distinct), passenger_counts 1.94M, delays 0.99M, trips 2.10M, gps_events 1.14M, routes 118, stops 756, vehicles 775, passengers 58,000; 2025-09-01..2026-08-31.
- Validation: full 59/59, sample 52/52, hidden_like 56/56 PASS. Determinism: full 62/62 files byte-identical on a rerun; sample identical, control seed changes 7/12 files.
- Realism evidence in `documentation/dataset_statistics.md` (all computed): seasonal low 73% of peak month; weekend 56% of weekday; delay vs load 3.3 -> 8.4 min; peak 6.1 vs off-peak 1.6 min; 6.6% bunched headways at the last stop; event uplifts +61% to +218%.

## 2026-09-24 — Phase 2: storage and ingestion (CMD-006)
- HDFS layout `/urbantransit/{raw,parquet,quarantine}/<table>`; `upload_raw.sh full` uploaded 83 files / 1.29 GB and re-counted every table from HDFS: files, rows and bytes identical (UPLOAD_VERIFY PASS).
- Explicit StructTypes for all 12 tables (`spark_jobs/schemas.py`), checked against `documentation/schemas/` (0 differences).
- Schema inference comparison: 8 type differences in 5 tables (tickets.entry_time and delays.delay_minutes become strings because of injected invalid values; schedules HH:MM inferred as timestamps; JSON dates/timestamps stay strings).
- Ingestion (`ingest_raw.py`): 12 tables in 811 s; every table rows in = OK + quarantined; quarantine tickets 2,986 (= injected invalid timestamps), delays 666 (text delay values); Parquet (Snappy) 276 MB vs 1,288 MB raw (21%), 62 files, read-back counts equal OK rows.
- **Failure:** first ingest test crashed with `SESSION_OR_CONTEXT_NOT_EXISTS` - partition expressions (`F.date_format`) were built at import time, before a SparkSession existed. **Fix:** build them lazily (functions).
- **Problem:** HDFS stops when WSL powers the distro off between calls. **Fix for this phase:** a background idle `wsl.exe` session keeps the distro (and HDFS) up while the jobs run.
- Driver memory raised to 4g (`.env`/.env.example); Spark progress bars disabled for readable logs; strict time parser (`timeParserPolicy=CORRECTED`), Snappy and adaptive execution added to `config/settings.py`.
- Note: `count raw` timings for small tables are dominated by ~5 s JVM start-up of the `hdfs dfs` CLI calls used for file counts/sizes, not by Spark.

## 2026-09-25 — Phase 3: data quality and cleaning (CMD-010, CMD-011)
- Decisions recorded: ticket limitation (methodology section 8), README note on regenerating injection key lists.
- Profiling of all 12 tables (full 128-164 s, hidden_like 179 s).
- 25 generic rules (16 SRS defect types + 5 extra) from 14 check types in `config/data_quality.yaml`; detection precision = recall = 1.0 for all 18 (defect, table) pairs in full and all 22 in hidden_like (20 types incl. unknown vehicles, future timestamps, out-of-bounds coordinates, negative fares); no findings where nothing was injected.
- Cleaning: every table reconciles (rows in = clean + removed + quarantined) in both datasets; minimum volumes hold (tickets 2,976,868 clean); rerun idempotent (62/62 fingerprints identical); cleaning log 121,226 rows.
- No-manifest proof: `no_manifest_guard.py` audit hook wraps profile/DQ/clean jobs (no access); negative control (guard around dq_evaluate.py) is BLOCKED.
- **Failure:** DQ job stalled at idle CPU for 25+ min - one plan unioning 25 rules (many broadcast joins). **Fix:** one small Spark job per rule (whole run 125-163 s).
- **Failure:** cleaning stalled the same way when writing all cleaning-log parts as one union. **Fix:** append each part as its own job (log folder cleared once per run -> still idempotent).
- **Failure:** `SESSION_OR_CONTEXT_NOT_EXISTS` again (module-level `F.array()`); **fix:** build lazily.
- **Failure:** `INVALID_LAMBDA_FUNCTION_CALL.NUM_ARGS_MISMATCH` - PySpark counted a default argument (`lambda x, cols=cols`) as a second lambda parameter; **fix:** `arrays_overlap`.
- **Failure:** `run_phase3.sh` failed (`$'..\r'`, `pipefail: invalid option`) - files patched with Windows Python were saved with CRLF; Git Bash `grep` hides `\r`, so the first fix attempt did nothing. **Fix:** convert with Linux `sed` inside WSL; patch scripts now write with `newline='\n'`.
- Reporting gap: rows already quarantined at ingestion (DQ07) showed 0 in the per-rule table; report now adds them from the cleaning log.

## 2026-09-25 — Phase 4: integration and feature engineering (CMD-013, CMD-014)
- Implemented ten documented Spark SQL relationships and measured their output/orphan counts in `reports/join_report.md`.
- Built only from `/urbantransit/clean`: trip (2,097,157 rows), route (41,451), route-time (40,974), route daily demand (41,451), and stop daily demand (243,999) feature Parquet outputs. All five were read back from HDFS (8 files each).
- Chronological split: train 2025-09-01..2026-05-02 (1,433,507 rows), validation 2026-05-03..2026-07-02 (344,428), test 2026-07-03..2026-08-31 (319,222). No date has multiple split assignments.
- Historical windows explicitly use `scheduled_departure, trip_id` and end at the preceding row. `verify_phase4.py` recomputed historical demand for routes R001..R005: 0 mismatches.
- **Failure:** first Phase 4 run could not import `spark_jobs` when launched by filename. **Fix:** added the repository-root import bootstrap used by other jobs. No HDFS output was written by that failed start.

## 2026-09-25 — Phase 4 review fixes (CMD-015)
- **Measurement gaps are NULL, not 0.** 166,203 trips without a clean passenger count now have NULL boardings/occupancy; before the fix they had 0, so zero-boarding rows fell from 178,599 to 12,396. Delay is NULL for 23,970 not-evaluated trips (21,990 cancelled plus 1,980 whose delay record was quarantined by DQ08a). 1,283,340 completed trips without a record are `within_tolerance` = 0.0, because the generator only logs trips that are ≥ 5 min late, run early (≤ -2 min) or break down.
- **Headway bug:** the job compared buses across directions, which produced 19,045 negative headways. After partitioning by direction, 146 remain; these are real overtaking (bunching) and are flagged.
- **New features:** demand week-over-week and month-over-month growth, and `peak_hour_indicator_asof`. Split sizes now come from config: train 243 dates (2025-09-01..2026-05-01), validation 61 (..2026-07-01), test 61 (..2026-08-31).
- `route_features` is now one row per route (118 rows, train split only); `route_daily_demand` is 41,451 route-days.
- `verify_phase4.py` PASS, including the leakage test: as-of features recomputed on data truncated at 2026-07-02, and with that day's demand ×10, gave 0 mismatches.
- **Failure:** the first rerun crashed on a module-level `F.lit` (no SparkContext). **Fix:** moved it into the function.

## 2026-09-25 — Phase 5: analytics with Spark SQL (CMD-016)
- **Pipeline:** 45 parameterised Spark SQL files (`spark_sql/analytics/`) run by `phase5_analytics.py`, producing 41 Parquet outputs under `/urbantransit/analytics/`. All were read back; the largest are `overcrowding_trips` (1,930,954 rows) and `od_matrix` (316,810). A full run takes about 12 min.
- **Expansion factor:** the CMD-010 ticket expansion factor was promised as a Phase 4 feature but never built, so it is built here. It averages 31.2 at route × month × period level (range 17.1–61.9).
- **NULL-aware:** overcrowding categories cover exactly the 1,930,954 measured trips and the 166,203 unmeasured trips are reported separately. Delay analyses use the 2,073,187 evaluated trips.
- **Failure:** the first special-event baseline (same weekday, previous 8 weeks) produced false spikes on post-Ramadan April days, because Ramadan-timetable weeks sat in the baseline. **Fix:** the baseline is now partitioned by calendar day type. Spike dates fell from 80 to 51, and the three generator events (2025-10-12, 2025-12-20, 2026-03-01) remain the top city-wide dates.
- **Failure:** the duplicate-ticketing signal also counted quick transfers. **Fix:** a repeat tap must be at the same stop. The remaining 35,715 signals are overlapping journeys (the next tap-in before the previous tap-out).
- **Failure:** Spark 4 ANSI typing (`element_at` index BIGINT). **Fix:** CAST to INT; `try_divide` is used for all ratios.
- `verify_phase5.py`: 8/8 PASS.

## 2026-09-25 — Phase 5 corrections (CMD-017)
- **Route scoring is now score-first.** The composite (six performance components) sets High Performing (top 30%) and Low Performing (bottom 30%); the middle band is diagnosed as Overcrowded, then High Demand but Unreliable, then Reliable but Underutilized, then Mixed / Needs Review. "Overcrowded" is also an independent flag (persistent overload).
  - Before: 77 Overcrowded, 0 High Performing.
  - After: High Performing 35, Low Performing 35, Reliable but Underutilized 18, High Demand but Unreliable 13, Mixed / Needs Review 12, Overcrowded 4, Insufficient Data 1. The flag is on 78 routes (29 of them High Performing).
- **Failure:** the first score-first version had 0 Overcrowded routes; the 4 high-overload middle-band routes were caught by High Demand but Unreliable. **Fix:** Overcrowded is checked first in the middle band.
- **DQ22 overlapping_journeys** (new generic check `overlapping_intervals`), run alone on the clean data with `spark_jobs/run_dq_rule.py`: 36,260 of 2,976,868 tickets (1.22%), median overlap 772 s, p90 2,371 s, max 6,578 s.
  - This is more than the 35,715 Phase 5 signals because DQ22 compares with the latest end of all earlier journeys and includes the DQ16 tickets.
  - The clean data is not rewritten; the next full Phase 3 run applies the flag through `clean_data.py`.
- **Delay severity:** `thresholds.yaml` now holds the Phase 4 bands (< 5 / < 10 / < 20 / Severe) and `phase4_features.py` reads them. Nothing read the old bands. The stored `delay_severity` matches the config on all trips (0 mismatches), so Phase 4 did not need a rerun.
- **Hotspot sensitivity:** 0 stop-specific routes at 60% and still 0 at 40% (highest share 0.381).
- `verify_phase5.py` 9/9 PASS.

## 2026-09-25 — Phase 5: overcrowding scored in the composite (CMD-018) — Phase 5 approved
- **Composite:** now the nine SRS Step 15 inputs. The new overcrowding component is severity-weighted: penalty = 0.5 × median daily severity-weighted overload share (Overcrowded 0.5, Critical 1.0) + 0.5 × persistent-cell share, and score = 100 × max(0, 1 − penalty ÷ 0.5). Utilisation became underutilization only, so overload is not double-counted.
- **Classes (with overcrowded flag):** High Performing 35 (24), Low Performing 35 (19), High Demand but Unreliable 13 (12), Reliable but Underutilized 13 (6), Mixed / Needs Review 13 (8), Overcrowded 8 (8), Insufficient Data 1 (1).
- **R097:** High Performing → **Overcrowded** (overcrowding 0, load 0, composite 50.7, rank 0.431). R031, R036 and R020 moved Overcrowded → Low Performing.
- **Still High Performing:** 9 routes overload on 20–34.6% of trips on a normal day. They are penalised (overcrowding scores 19.7–53.3) but stay in the top 30% on the other eight components, and all nine carry the flag.
- `verify_phase5.py` 9/9 PASS; the composite recomputed from its components has 0 mismatches.

## 2026-09-26 — Backend: Flask + MySQL, branch `backend/flask-mysql` (CMD-019)
- **Pulled `8852571`** (Arham's Phase 6 finalisation) before branching. It changed three facts from the audit: 28 metric files instead of 21, relabelled clusters, and `macro_f1` renamed to `weighted_f1` in two legacy files. The Task A retrain still uses `occupancy_pct`, so the INVALID flag covers all delay-severity files. No Phase 6/7 path was modified.
- **Schema (Flask-Migrate):** 43 tables. There are 30 Phase 5 mirrors whose column names and types are generated from the live Parquet schemas (decimal precisions kept, all nullable), plus 3 reference tables, RBAC, audit_log, model_versions and job_runs (both empty by design), model_metrics and cluster_profiles. 11 analytics tables were skipped as intermediate or too granular; the reasons are in `documentation/database_schema.md`.
- **HDFS → MySQL load:** `load_analytics_to_mysql.py` checks each Parquet schema against the spec, then replaces the table in one transaction. All 33 tables matched Phase 5 = HDFS = MySQL, e.g. route_performance 118, od_matrix 316,810 (107 s), passenger_segments 56,779, vehicles 775. `verify_mysql_load.py` compared counts, sums and distinct counts on all 374 columns: 0 mismatches.
- **Model evidence:** 28 metric files in 4+ layouts were flattened to 340 `model_metrics` rows. All 169 delay_severity rows are flagged INVALID (occupancy leakage). `cluster_profiles` has 4 rows; no route-to-cluster table exists, so none was made.
- **API:** JWT login; permission guards that reload the user on each request; analytics JSON with strict filters (an unsupported filter is a 400); CSV export streaming exact decimals; admin CRUD validated against the Phase 1 schema JSON; read-only model metrics with an INVALID warning; 503 stubs for delay/crowding predictions and recommendations; JSON error envelope; CORS for the React dev server.
- **Tests:** 60 pytest tests on in-memory SQLite, all passing. A live smoke test against MySQL with a temporary admin (deleted afterwards) passed: R097 is Overcrowded with composite 50.7, as in Phase 5, and the od_matrix CSV has 316,811 lines.
- **Failure:** the first test run had one failing assertion. It expected 4 daily_boardings test-MAE rows, but there are 5 because Arham's trailing-28-day baseline is also a daily_boardings file. The test was fixed, not the data.
- **Finding for Phase 6:** the enhanced delay and crowding feature lists include `travel_time_min` and `headway_minutes`, which `feature_catalog.md` classes as same-trip outcomes. The crowding models are not flagged yet; this needs a decision.
