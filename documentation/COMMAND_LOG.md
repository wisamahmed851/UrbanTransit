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

---

## CMD-003 | 2026-09-24 12:59 (UTC+05:00) | Phase 0
**My command (verbatim):**
```text
Decisions:
1. WSL2 (Ubuntu 24.04) approved, not Docker.
2. Install MySQL inside WSL. Leave Laragon alone.
3. IMPORTANT: install everything on the D: drive. C: has very little free
   space. Do this:
   - After I install WSL, move the Ubuntu distro to D: with wsl --export /
     --unregister / --import (e.g. D:\WSL\Ubuntu-24.04). Set the default user
     back to my normal user in /etc/wsl.conf after the import.
   - Keep the Python venv, Hadoop, Spark, JDK 17, HDFS data and MySQL data
     inside the WSL disk (which will now live on D:). Do NOT put the venv or
     HDFS data on /mnt/d, it is very slow.
   - Any Windows-side tool you need (e.g. GitHub CLI) must also go on D:.
   - Set pip and npm caches so they don't fill C:.
   - Before each large install, tell me the disk space it needs and where it goes.
4. Limit WSL memory with a .wslconfig (e.g. memory=8GB) so Windows stays usable.
5. Log all of this as CMD-002 in COMMAND_LOG.md.
6. Question: the SRS layout has 25 folders and you created 26. Which one is
   the extra and why? Tell me before continuing.
7. GitHub remote: <PASTE YOUR REPO URL HERE>. GitHub CLI is not installed, so
   use Git Credential Manager or an HTTPS personal access token, and tell me
   if you need me to log in.

I will tell you as soon as WSL is installed and Ubuntu has been opened once.
Wait for that, then continue Phase 0.
```
**Understood as:** Approve WSL2 + MySQL-in-WSL; keep all installs/data on D: (distro moved to D:\WSL\Ubuntu-24.04, venv/HDFS/MySQL inside the WSL disk, caches off C:); add a .wslconfig memory cap; answer the folder-count question; then wait until the user confirms WSL is installed.

**Notes on the instruction:**
- Item 5 asks for "CMD-002", but CMD-002 was already used for the "replace the git origin" command. Rule 1 forbids rewriting entries, so this is logged as **CMD-003**.
- Item 6: correction to CMD-001. There are exactly **25** top-level folders (verified with `find . -mindepth 1 -maxdepth 1 -type d ! -name .git | wc -l` → 25). The "26 folders" in CMD-001 step 2 was a miscount in the log text; no extra folder exists.
- Item 7: the URL placeholder was not filled in, but CMD-002 already set origin to `https://github.com/wisamahmed851/UrbanTransit.git` and the push succeeded through Git Credential Manager (`credential.helper=manager`), so no login is needed.

**Actions taken:**
1. Verified folder count (25), npm location, pip cache location (`C:\Users\AKL\AppData\Local\pip\cache`), no existing `.wslconfig`, credential helper = manager.
2. Created `D:\WSL`, `D:\DevCache\pip`, `D:\DevCache\npm`, `D:\DevTools` (for any Windows-side tools).
3. Wrote `C:\Users\AKL\.wslconfig` (outside repo; must live in %UserProfile%): `memory=8GB`, `processors=4`, `swap=4GB`, `swapFile=D:\WSL\swap.vhdx`.
4. `[Environment]::SetEnvironmentVariable('PIP_CACHE_DIR','D:\DevCache\pip','User')`; `npm config set cache D:\DevCache\npm --location=user`. Verified both.
5. Measured existing caches on C:: pip 551 MB, npm 124 MB (left in place; user may purge).
6. Added CMD-003 decisions to DEV_LOG.md; committed and pushed.
7. **Waiting** for the user to confirm WSL/Ubuntu 24.04 is installed before moving the distro to D: and doing heavy installs.

**Files changed:** `documentation/COMMAND_LOG.md`, `DEV_LOG.md` (in repo); `C:\Users\AKL\.wslconfig`, user env var `PIP_CACHE_DIR`, user `.npmrc` (outside repo)

**Result:** Partial (by design): config done, heavy steps waiting for WSL installation by the user.

**Problems and fixes:** none so far.

**Git commit:** `docs: log CMD-003 decisions (WSL2 on D:, MySQL in WSL, caches off C:)`

---

## CMD-004 | 2026-09-24 (UTC+05:00) | Phase 0
**My command (verbatim):**
```text
WSL is installed. The distro is named "Ubuntu" (WSL version 2), not
"Ubuntu-24.04". Use the real name from `wsl -l -v`. I have opened Ubuntu once
and created my Linux user, but verify the default user and Ubuntu version
yourself.

Answers:
- Yes, purge the old pip and npm caches on C: now that the new cache
  locations on D: are set.

Continue Phase 0 from where you paused:

1. Move the distro to D: (wsl --shutdown first, then export to D:\WSL,
   unregister, import to D:\WSL\Ubuntu with --version 2, delete the temporary
   tar after verifying the import works, restore my default user in
   /etc/wsl.conf). Confirm the distro works and my files are intact before
   deleting anything.

2. For installs inside WSL, use `wsl -d Ubuntu -u root -- ...` so no sudo
   password is needed. Run all project work (venv, pip, Spark, HDFS) as my
   normal user, not root.

3. Inside WSL, install: JDK 17 (set JAVA_HOME), Hadoop 3.4.x
   (pseudo-distributed single node, with the SSH-to-localhost setup it
   needs), MySQL server (create database urbantransit_iq and a dedicated
   user; credentials only in .env), and Python 3.12 + venv tools. Put the
   venv at ~/venvs/urbantransit, NOT on /mnt/d. Keep the repo on D:
   (/mnt/d/Techwise_2026) as the source of truth, but keep HDFS data and
   MySQL data inside the WSL disk.

4. Then do the rest of the Phase 0 tasks: requirements.txt (pinned),
   config/settings + config/thresholds.yaml, hdfs_scripts (start, stop,
   status, verify_hdfs.sh), spark_jobs/verify_spark.py,
   database/verify_mysql.py, and the Flask /health app in src/.

5. Tell me the disk space and location before each large download. Log
   everything as new CMD entries, keep committing in small logical commits and
   push.

6. Finish with the full PASS/FAIL checklist with real output. If something
   fails, log it in DEV_LOG.md and tell me. Then STOP. Do not start Phase 1.
```
**Understood as:** Move distro "Ubuntu" to D:\WSL\Ubuntu, purge old C: caches, install JDK 17 / Hadoop 3.4.x / MySQL / Python venv inside WSL (root for apt, normal user for project work), finish all remaining Phase 0 files and verification scripts, run the full checklist, then stop.

**Actions taken:**
1. `wsl -l -v`, check default user / Ubuntu version / home dir / current vhdx location (first attempt timed out at 120 s because of a slow recursive search under `%LOCALAPPDATA%\Packages`; moved to background).
2. Retried from Git Bash with `timeout 40 wsl.exe -d Ubuntu -e whoami` (with and without `</dev/null`): **timed out (exit 124)**. `wsl --status` and `wsl -l -v` worked (`Ubuntu  Running  2`, default distro Ubuntu).
3. Retried via PowerShell `Start-Process wsl.exe ... -RedirectStandardOutput`: **TIMEOUT** after 40 s.
4. `wsl --shutdown` (required by step 1 anyway): **timed out** twice (60 s). Killed the leftover `wsl.exe` processes this session had started (PIDs 8476, 9212); shutdown still timed out and `vmmemWSL` stays up. Restarting `WSLService` needs admin rights, which the assistant's shell does not have. **Blocked; user action needed.**
5. Cache purge (approved): `pip cache purge` / `npm cache clean --force` now target the new D: caches, so the old C: folders were removed directly: `Remove-Item C:\Users\AKL\AppData\Local\pip\cache` and `...\npm-cache`. C: free 11.75 GB → 12.45 GB.
6. Queried PyPI (`pip index versions`) for current releases; wrote pinned `requirements.txt` (pyspark 4.2.0 → needs Java 17+), `.env.example`, `config/__init__.py`, `config/settings.py`, `config/thresholds.yaml`.
7. Wrote `hdfs_scripts/{env,start_hdfs,stop_hdfs,status_hdfs,verify_hdfs}.sh`, `spark_jobs/verify_spark.py`, `database/verify_mysql.py`, `src/app.py`. **None of them has been run yet** (they need WSL).

---

## CMD-005 | 2026-09-24 14:28 (UTC+05:00) | Phase 0
**My command (verbatim):**
```text
WSL is responding again. Note: `wsl -d Ubuntu -- whoami` returns root, not my
normal user — the default user is not set correctly. Check /etc/wsl.conf and
fix the default user as part of restoring it during the move to D:. I also
commented out the swapFile= line in .wslconfig.

Continue Phase 0 from CMD-004 where you left off.
```
**Understood as:** WSL is fixed (swapFile disabled by user); resume CMD-004 — move distro to D:, set the correct non-root default user in /etc/wsl.conf, install the stack, run all verifications, finish the checklist.

**Actions taken:**
1. `wsl -d Ubuntu -u root -e sh -c '...'` now responds (exit 0). Findings:
   - Distro "Ubuntu" is **Ubuntu 26.04.1 LTS** with **Python 3.14.4**, not 24.04 / 3.12 as agreed in CMD-003.
   - **No normal user exists**: no passwd entries with UID ≥ 1000, `/home` is empty (4 KB). That explains `whoami` = root. `/etc/wsl.conf` contains only `[boot] systemd=true` (no `[user] default=`). The first-run user setup apparently never completed (possibly related to the CMD-004 hang).
   - Root filesystem uses 1.3 GB; `/root` has only default dotfiles (20 KB), so no user data would be lost.
2. `wsl --version` → WSL 2.7.14.0, kernel 6.18.33.2-2. Supports `wsl --install --location`, `--name`, `wsl --manage --move`, `--manage --set-default-user`. `wsl --list --online` offers Ubuntu-24.04.
3. Paused to ask the user: keep 26.04 or switch to 24.04, and which Linux username to create.
4. User answered: **fresh Ubuntu 24.04 on D:**, username **wisam**.
5. `wsl --install -d Ubuntu-24.04 --location D:\WSL\Ubuntu-24.04 --no-launch` → installed directly on D: (ext4.vhdx 1.2 GB). The export/import route was no longer needed.
6. As root: `useradd -m -s /bin/bash -G sudo,adm wisam`; `passwd -l wisam` (the user sets their own password); wrote `/etc/wsl.conf` = `[boot] systemd=true`, `[user] default=wisam`, `[interop] appendWindowsPath=false` (keeps Windows Java 8/Python off the Linux PATH). `wsl --terminate`, `wsl --set-default Ubuntu-24.04`. Verified `wsl -- whoami` → `wisam`; PID 1 = systemd; Ubuntu 24.04.5 LTS, Python 3.12.3.
7. `wsl --unregister Ubuntu` (empty 26.04 distro, approved by user). C: free 12.45 → 13.8 GB.
8. **Problem:** "Failed to start the systemd user session for 'wisam'" / `systemctl --user` → "Failed to connect to bus". `user@1000.service` never started at boot. **Fix:** `loginctl enable-linger wisam`, after which `systemctl --user is-system-running` → `running` (1 s). Remaining quirk: on a *cold* VM start the first WSL call can still hit the race (once took 44 s, once for root). Harmless for the project; retrying works.
9. As root: `apt-get install openjdk-17-jdk-headless mysql-server python3-venv python3-pip python3-dev openssh-server openssh-client curl rsync` → OpenJDK 17.0.20.1, MySQL 8.0.46. WSL disk 1.3 → 2.9 GB.
10. Hadoop: latest 3.4.x on dlcdn.apache.org = 3.4.3 (515 MB, no lean build). Downloaded to /tmp inside WSL, `sha512sum -c` → OK, extracted to `/opt/hadoop-3.4.3`, symlink `/opt/hadoop`, chown wisam, tarball deleted. 1.2 GB on disk.
11. Wrote `hdfs_scripts/conf/core-site.xml` (fs.defaultFS hdfs://localhost:9000), `hdfs-site.xml` (replication 1, name/data dirs in `~/hadoop_data`), `hdfs_scripts/setup_hadoop.sh`. `systemctl enable ssh.socket ssh.service`; ran `setup_hadoop.sh` as wisam → "SSH to localhost: OK", "Hadoop 3.4.3".
12. **Fix:** `env.sh` `ensure_sshd` used `pgrep sshd`, but Ubuntu 24.04 socket-activates sshd (no daemon until a connection comes in). Changed it to test a real `ssh localhost true`.
13. MySQL: `systemctl enable --now mysql`; created DB `urbantransit_iq` (utf8mb4) and user `urbantransit`@`localhost`/`127.0.0.1` with a random 24-char password; generated `.env` from `.env.example` with random SECRET_KEY/JWT_SECRET_KEY (values never printed; `.env` confirmed ignored by `git check-ignore`). Data dir `/var/lib/mysql` (inside WSL disk).
14. `python3 -m venv ~/venvs/urbantransit`; `pip install -r requirements.txt` (running).
15. `pip install -r requirements.txt` → **success**, venv 1.6 GB. xgboost pulled `nvidia-nccl-cu13` (305 MB GPU library, unused on this machine).
16. Started HDFS (`start_hdfs.sh` formatted the NameNode on the first run) → `verify_hdfs.sh` **PASS**.
17. **Failed attempt:** `pyspark` shell check via `echo ... | pyspark` → `NameError: name 'spark' is not defined` (piped stdin isn't interactive, so PYTHONSTARTUP never ran). **Fix:** `PYSPARK_DRIVER_PYTHON_OPTS=-i` → `PYSPARK_SHELL_OK 4.2.0 5`.
18. **Failed attempt:** `verify_spark.py` → `java.nio.file.NoSuchFileException: /tmp/blockmgr-.../15`; a rerun's `/tmp/vs.log` also vanished. **Root cause** (journal + NameNode log): WSL powers the distro off when no `wsl.exe` client is attached (`systemd-logind: The system will power off now!` at 15:03:14, NameNode `RECEIVED SIGNAL 15`). The next call cold-boots it, and systemd's boot-time `/tmp` cleanup runs while Spark is already using `/tmp`. **Fixes:** `spark.local.dir` = `~/spark_tmp` (settings.py, `.env.example` `SPARK_LOCAL_DIR`); Parquet check writes there; HDFS pid files moved to `~/hadoop_data/pids`; all verification runs in a single WSL session.
19. **Failed attempt:** HDFS did not start in the first single-session run (connection refused on :9000) because of a cold-boot race with `ssh.socket`. **Fix:** `ensure_sshd` retries 6×5 s; `stop_hdfs.sh` also calls it.
20. **Bug found:** `HADOOP_PID_DIR` exported in env.sh never reached the daemons (start-dfs.sh launches them over ssh and they read only `hadoop-env.sh`). **Fix:** `setup_hadoop.sh` appends `HADOOP_PID_DIR` to `hadoop-env.sh`; verified pid files in `~/hadoop_data/pids`.
21. **Own mistake:** cleanup command `pkill -f "org.apache.hadoop.hdfs"` matched its own `bash -c` command line and killed the session (exit 15). Reran with `pkill -f "[o]rg.apache.hadoop.hdfs.server"`.
22. Rerun: `setup_hadoop.sh`, `start_hdfs.sh`, `status_hdfs.sh`, `verify_hdfs.sh` PASS, pyspark shell OK, `verify_spark.py` PASS (Spark SQL, Parquet, HDFS read), `stop_hdfs.sh` OK. Earlier session: `verify_mysql.py` PASS, Flask `/health` → HTTP 200.
23. PySpark warned "does not yet fully support pandas >= 3.0.0". Pinned `pandas==2.3.3` (latest 2.x), reinstalled, `pip check` clean, `verify_spark.py` PASS with no warning.
