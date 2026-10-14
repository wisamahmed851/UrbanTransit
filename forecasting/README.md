# forecasting/

SRS steps 22-24 (passenger demand forecasting, time-aware validation, evaluation) and 55 (forecast dashboard).
This folder is a pointer; the code lives where the pipelines run:

| What | Where |
|---|---|
| Python models (daily route demand, stop-period demand, occupancy forecast; chronological split, 28-day baseline) | `python_pipeline/phase7_python_models.py` |
| Spark MLlib demand models (Linear Regression, Decision Tree, Random Forest, GBT) | `spark_jobs/phase6_spark_models.py` |
| Serving and recursive multi-day forecast (configurable horizon, `config/serving.yaml`) | `src/services/forecasting.py`, `src/blueprints/insights.py` |
| Saved models and metrics (MAE, RMSE, MAPE, R2 vs baseline) | `models/python/`, `models/python/metrics/` |
| Dashboard | Demand forecast page (`frontend/src/pages/ForecastPage.tsx`) |
| Method and preprocessing | `python_pipeline/preprocessing_notes_daily_boardings.md`, `documentation/python_pipeline_explained.md`
