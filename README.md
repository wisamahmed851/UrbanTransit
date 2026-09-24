# UrbanTransit IQ

Public transport analytics platform combining **Big Data** (Apache Spark, Spark SQL,
Spark MLlib, HDFS, Parquet) and **Data Science** (pandas, NumPy, scikit-learn, XGBoost,
statsmodels) to analyse ridership, occupancy, delays, bunching and route performance,
and to produce forecasts and recommendations for transit operators.

## Architecture (planned)

| Layer | Technology |
|---|---|
| Storage | HDFS (single-node, pseudo-distributed), Parquet |
| Processing | Apache Spark (PySpark), Spark SQL, Spark MLlib |
| Data science | pandas, NumPy, scikit-learn, XGBoost, statsmodels |
| App database | MySQL |
| Backend API | Flask |
| Frontend | React / Next.js (Phase 11) |

## Repository layout

| Folder | Purpose |
|---|---|
| `src/` | Flask application |
| `templates/`, `static/` | Server-rendered templates and static assets |
| `data_generator/` | Synthetic transit data generator |
| `raw_data/`, `processed_data/`, `parquet_data/` | Local data stages (git-ignored) |
| `hdfs_scripts/` | HDFS start/stop/status and verification scripts |
| `spark_jobs/`, `spark_sql/` | PySpark jobs and Spark SQL queries |
| `python_pipeline/` | pandas-based processing pipeline |
| `notebooks/` | Exploratory notebooks |
| `models/` | Trained model binaries (git-ignored) |
| `forecasting/`, `route_clustering/`, `delay_analysis/`, `occupancy_analysis/`, `recommendation_engine/` | Analytics modules |
| `database/` | MySQL schema, migrations and checks |
| `config/` | Settings and thresholds |
| `tests/` | Tests |
| `sample_data/` | Small sample files safe to commit |
| `documentation/`, `reports/`, `screenshots/` | Project documentation and outputs |

## Installation

The Big Data stack runs inside **WSL2 (Ubuntu 24.04)** on Windows. The repository stays
on the Windows drive (`/mnt/d/Techwise_2026` inside WSL); the venv, HDFS data and MySQL
data live inside the WSL disk for speed.

| Component | Version |
|---|---|
| Ubuntu (WSL2) | 24.04 LTS |
| Java | OpenJDK 17 |
| Hadoop / HDFS | 3.4.3 (single-node, pseudo-distributed) |
| Spark | PySpark 4.2.0 (bundled Spark) |
| MySQL | 8.0 |
| Python | 3.12 |

1. **WSL** (Administrator PowerShell):
   `wsl --install -d Ubuntu-24.04 --location D:\WSL\Ubuntu-24.04`
2. **System packages** (inside WSL):
   ```bash
   sudo apt-get install -y openjdk-17-jdk-headless mysql-server python3-venv python3-pip python3-dev openssh-server curl rsync
   sudo systemctl enable --now ssh mysql
   ```
3. **Hadoop 3.4.3**: extract `hadoop-3.4.3.tar.gz` from dlcdn.apache.org to `/opt`, symlink `/opt/hadoop`, then:
   `bash hdfs_scripts/setup_hadoop.sh`
4. **Python venv**:
   ```bash
   python3 -m venv ~/venvs/urbantransit
   source ~/venvs/urbantransit/bin/activate
   pip install -r requirements.txt
   ```
5. **MySQL**: create database `urbantransit_iq` and a dedicated user, then
   `cp .env.example .env` and fill in the credentials (`.env` is git-ignored).

## Execution

All commands run inside WSL from the repository root with the venv active.

```bash
bash hdfs_scripts/start_hdfs.sh        # start HDFS (formats NameNode on first run)
bash hdfs_scripts/status_hdfs.sh       # daemon status
bash hdfs_scripts/verify_hdfs.sh       # HDFS upload / read-back check
python spark_jobs/verify_spark.py      # Spark SQL, Parquet, HDFS read check
python database/verify_mysql.py        # MySQL SELECT 1
python src/app.py                      # Flask on http://127.0.0.1:5000/health
bash hdfs_scripts/stop_hdfs.sh         # stop HDFS
```

### Regenerating the defect-injection lists (not in Git)

`data_generator/manifests/<mode>/injection_manifest.json` (counts per defect) is committed.
The per-row key lists `injection_keys.jsonl.gz` for `full` and `hidden_like` are **gitignored**
(large); they are produced by the generator and are deterministic, so regenerate them with:

```bash
python -m data_generator.generate --mode full          # also rewrites raw_data/full
python -m data_generator.generate --mode hidden_like
```

Only the separate evaluation script (`spark_jobs/dq_evaluate.py`) reads them; the data-quality
pipeline never does.

## Project logs

- [DEV_LOG.md](DEV_LOG.md) — development log (work, problems, fixes)
- [AI_USAGE.md](AI_USAGE.md) — declaration of AI tool usage
- [documentation/COMMAND_LOG.md](documentation/COMMAND_LOG.md) — every instruction given to the AI assistant

## License

MIT — see [LICENSE](LICENSE).
