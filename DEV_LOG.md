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
