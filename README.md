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

_To be completed at the end of Phase 0 (Java, Hadoop/HDFS, Spark, MySQL, Python venv)._

## Execution

_To be completed as each phase adds runnable components._

## Project logs

- [DEV_LOG.md](DEV_LOG.md) — development log (work, problems, fixes)
- [AI_USAGE.md](AI_USAGE.md) — declaration of AI tool usage
- [documentation/COMMAND_LOG.md](documentation/COMMAND_LOG.md) — every instruction given to the AI assistant

## License

MIT — see [LICENSE](LICENSE).
