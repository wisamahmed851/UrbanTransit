# delay_analysis/

SRS steps 17-20 (delay analysis, patterns, prediction, severity classes). This folder is a pointer to the code:

| What | Where |
|---|---|
| Delay by route / trip / stop / vehicle / time / day / direction / distance | `spark_sql/analytics/090_delay_by_dimension.sql` to `096_delay_top_trips.sql` |
| Recurring patterns and bottleneck stops | `092_delay_congestion_patterns.sql`, `091_delay_by_stop.sql`, `093_delay_accumulation.sql` |
| Severity classes and thresholds (configurable) | `config/thresholds.yaml`, `documentation/delay_severity_taxonomy.md` |
| Delay prediction (Python: Logistic Regression, Random Forest, XGBoost) | `python_pipeline/phase7_python_models.py`, `python_pipeline/preprocessing_notes_delay_severity.md` |
| Dashboards | Delays page, Predictions page (Delay severity tab) |
