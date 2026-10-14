# occupancy_analysis/

SRS steps 12-14 and 25-26 (overcrowding, persistence, underutilisation, occupancy forecast, crowding risk).
This folder is a pointer to the code:

| What | Where |
|---|---|
| Overcrowded trips, persistent overcrowding, underused services | `spark_sql/analytics/050_overcrowding_trips.sql`, `051_*`, `060_persistent_overcrowding.sql`, `070_underutilized_services.sql` |
| Occupancy bands (Low to Critical) | `config/thresholds.yaml` (`occupancy_categories`) |
| Crowding-risk models (Python and Spark MLlib) | `python_pipeline/phase7_python_models.py`, `spark_jobs/phase6_*.py` |
| Occupancy forecast (XGBoost) | `models/python/occupancy_forecast/`, `python_pipeline/preprocessing_notes_occupancy_forecast.md` |
| Dashboards | Crowding and capacity page, Predictions page |
