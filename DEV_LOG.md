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
