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
