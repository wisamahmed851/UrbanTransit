# Command Log — UrbanTransit IQ

Every instruction given to the AI assistant is logged here **before** work starts and
updated when it finishes. Entries are numbered sequentially and are never rewritten or
deleted (later corrections go in a new entry). Failed attempts are logged too.

---

## CMD-001 | 2026-09-24 12:34 (UTC+05:00) | Phase 0
**My command (verbatim):**

<details>
<summary>Full Phase 0 instruction (click to expand)</summary>

```text
You are helping me build "UrbanTransit IQ", a public transport analytics app
(Big Data + Data Science). We build it phase by phase. This message starts
PHASE 0 (setup and repo) only. Do NOT start Phase 1 or write any data
generator, Spark job or app code.

Stack decisions (final):
- Backend: Flask (not FastAPI)
- Big Data: Apache Spark (PySpark), Spark SQL, Spark MLlib, HDFS, Parquet
- App database: MySQL
- Python data science: pandas, NumPy, scikit-learn, XGBoost, statsmodels, as needed
- Frontend: React/Next.js, built LAST (Phase 11). Do not create it now.
- Testing and deployment: decided later. Only leave the tests/ folder.
- Git and GitHub from day 1

=====================================================
RULE 1: COMMAND LOG (mandatory, applies to every phase)
=====================================================
Create and maintain `documentation/COMMAND_LOG.md`. Every time I give you a
command or instruction, add an entry BEFORE you start working, then update
it when done. Use this format:

## CMD-001 | <date and time> | Phase <n>
**My command (verbatim):** <exactly what I typed>
**Understood as:** <one-line interpretation>
**Actions taken:** <shell commands run, files created/edited, in order>
**Files changed:** <list>
**Result:** Success / Partial / Failed, with a short note
**Problems and fixes:** <errors hit and how they were solved, or "none">
**Git commit:** <hash and message>

Rules for the log:
- Number entries sequentially (CMD-001, CMD-002, ...) and never rewrite or
  delete old entries. The log continues in the same file in later phases.
- Log this very first message as CMD-001.
- Include failed attempts too. They feed the Development Log.
- Commit the log together with the work it describes.

=====================================================
RULE 2: WORKING RULES
=====================================================
- First detect my OS. If Windows, use WSL2 or Docker for Hadoop/HDFS and tell
  me which you chose and why BEFORE installing anything heavy, and wait for my
  OK on that choice only.
- Never commit secrets. Use `.env` (gitignored) plus `.env.example`.
- Make small, meaningful Git commits with clear messages. Commits are
  evaluated across all 5 competition days.
- If a step fails, do not skip it silently. Log it in COMMAND_LOG.md and
  DEV_LOG.md, then fix or ask me.
- Never invent results. Verification steps must actually run and show output.

=====================================================
PHASE 0 TASKS
=====================================================
1. Repo and structure
   - `git init` (or use the existing repo), add `.gitignore` (Python, venv,
     .env, Spark/Hadoop temp files, large data files, model binaries, node_modules)
   - Create this folder layout (add a `.gitkeep` in empty folders):
     src/, templates/, static/, data_generator/, raw_data/, processed_data/,
     parquet_data/, hdfs_scripts/, spark_jobs/, spark_sql/, python_pipeline/,
     notebooks/, models/, forecasting/, route_clustering/, delay_analysis/,
     occupancy_analysis/, recommendation_engine/, database/, tests/,
     sample_data/, documentation/, screenshots/, reports/, config/
   - Create root files: README.md (project overview + placeholder sections for
     installation and execution), AI_USAGE.md, requirements.txt, LICENSE (MIT),
     DEV_LOG.md, .env.example

2. Documentation files
   - `AI_USAGE.md`: table with columns Tool, Purpose, Type of help, Files
     affected, Modifications made, Testing completed, Verifying team member.
     Add the first row declaring Claude Code, used for project setup.
   - `DEV_LOG.md`: dated entries for work completed, problems, fixes, and
     later Spark failures, dataset changes and model errors. Add the Phase 0 entry.
   - `documentation/COMMAND_LOG.md` as described in Rule 1.

3. Environment
   - Python virtual environment (`.venv`) and a real `requirements.txt` with
     pinned versions: flask, flask-sqlalchemy, flask-migrate,
     flask-jwt-extended, flask-cors, pymysql, python-dotenv, pyspark, pandas,
     numpy, scikit-learn, xgboost, statsmodels, scipy, matplotlib, plotly,
     joblib, folium, pytest
   - Check or install Java (JDK 11 or 17, compatible with the Spark version) and set JAVA_HOME
   - Install Spark/PySpark, and record versions in DEV_LOG.md
   - Set up Hadoop/HDFS (single-node, pseudo-distributed) using the approach
     we agreed on in the OS step, with scripts in `hdfs_scripts/` (start,
     stop, status)
   - MySQL: install or run via Docker, create database `urbantransit_iq` and a
     dedicated user, store credentials only in `.env`

4. Config
   - `config/settings.py` (or `config.yaml`) loading from `.env`: paths, HDFS
     URI, Spark options, MySQL URL
   - `config/thresholds.yaml` with configurable thresholds as placeholders:
     occupancy categories (Low/Moderate/High/Overcrowded/Critical), delay
     severity (On Time/Minor/Moderate/Major/Severe), peak detection
     parameters, bunching headway ratio. Mark values "initial, to be tuned".

5. Verification scripts (these must actually run)
   - `hdfs_scripts/verify_hdfs.sh`: create a test directory, upload a small
     file, list it, read it back, clean up
   - `spark_jobs/verify_spark.py`: start a SparkSession, create a small
     DataFrame, run one Spark SQL query, write and read a Parquet file, and
     read the test file from HDFS
   - `database/verify_mysql.py`: connect to MySQL with the .env credentials
     and run `SELECT 1`
   - `src/app.py`: a minimal Flask app with one `/health` endpoint, and confirm it responds

6. Git
   - Commit in logical steps (structure, docs, environment, config,
     verification), not one big commit
   - Push to the GitHub remote (ask me for the URL if none is set)

=====================================================
PHASE 0 COMPLETION CHECKLIST
=====================================================
When finished, run every check and print a checklist with PASS/FAIL and
the real output for each. Phase 0 is complete only if all pass:

[ ] Folder structure and root files exist as specified
[ ] AI_USAGE.md, DEV_LOG.md and documentation/COMMAND_LOG.md exist and are filled in
[ ] Python venv works and `pip install -r requirements.txt` succeeds
[ ] `java -version` and `pyspark` work
[ ] `spark_jobs/verify_spark.py` runs, including Spark SQL and the Parquet write/read
[ ] `hdfs_scripts/verify_hdfs.sh` passes (file uploaded and read back from HDFS)
[ ] Spark can read a file from HDFS
[ ] `database/verify_mysql.py` connects and returns 1
[ ] Flask `/health` returns 200
[ ] No secrets in Git (`.env` ignored, `.env.example` present)
[ ] Multiple meaningful commits, pushed to GitHub
[ ] Every command I gave you is logged in COMMAND_LOG.md

Finish with a short summary: what was set up, versions installed, anything
that failed or needs my decision. Then STOP and wait for my Phase 1 command.
Do not start Phase 1.
```
</details>

**Understood as:** Set up Phase 0 only: repo, folder layout, docs, pinned environment, Java/Spark/HDFS/MySQL, config, and verification scripts that really run; ask for OK on the WSL2-vs-Docker choice before heavy installs; no Phase 1 work.

**Actions taken:** *(in progress)*
1. OS/tool detection (PowerShell): Windows 11 Pro 10.0.22000, Python 3.13.7, Git 2.45.1, Java 1.8.0_401 JRE only (no JAVA_HOME), no Docker, WSL feature present but no distro installed, MySQL 8.4.3 present via Laragon (`D:\laragon`, service not running), 14.9 GB RAM, virtualization enabled in firmware, shell not elevated.
2. `git init -b main`; created the 26 folders with `.gitkeep` (bash loop); wrote `.gitignore`.
3. Commit `2199067` (structure).
4. Wrote `.gitattributes`, `README.md`, `AI_USAGE.md`, `LICENSE`, `DEV_LOG.md`; updated this log.
5. Commit `36db8aa` (docs).
6. **Paused** before heavy installs: proposed WSL2 (Ubuntu 24.04) for Hadoop/HDFS + Spark, asked the user for OK (Rule 2), a GitHub remote URL, and MySQL placement.

**Files changed:** *(in progress)* `.gitignore`, `.gitattributes`, `*/.gitkeep`, `README.md`, `AI_USAGE.md`, `LICENSE`, `DEV_LOG.md`, `documentation/COMMAND_LOG.md`

**Result:** *(in progress)*

**Problems and fixes:** *(in progress)*
- Git CRLF warning on `.gitignore` → added `.gitattributes` forcing LF for `.sh/.py/.yaml/.xml`.

**Git commit:** *(in progress)*

---

## CMD-002 | 2026-09-24 12:50 (UTC+05:00) | Phase 0
**My command (verbatim):**
```text
replace the git origin to this url
https://github.com/wisamahmed851/UrbanTransit
```
**Understood as:** Change the `origin` remote URL to `https://github.com/wisamahmed851/UrbanTransit` (answers the GitHub-URL question from CMD-001; the WSL2/MySQL questions are still open).

**Actions taken:**
1. `git remote -v` showed an existing `origin` = `https://github.com/wisammanzoor158/UrbanTransit.git` (added by the user outside this session, along with user commit `2fae74f init`, which contains the CMD-001 log update).
2. `git remote set-url origin https://github.com/wisamahmed851/UrbanTransit.git`
3. `git remote -v` and `git ls-remote origin` to verify (exit 0, no refs: repo exists and is empty).
4. Committed this log update and ran `git push -u origin main` (Phase 0 task 6).

**Files changed:** `documentation/COMMAND_LOG.md`

**Result:** Success: origin now points to `https://github.com/wisamahmed851/UrbanTransit.git`.

**Problems and fixes:** none. Old origin (`wisammanzoor158/UrbanTransit`) had never been pushed to.

**Git commit:** `chore: point origin to wisamahmed851/UrbanTransit and log CMD-002`
