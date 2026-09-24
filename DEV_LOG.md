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
