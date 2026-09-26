# Phase 7 Python pipeline

This is an independent pandas/PyArrow, scikit-learn, and XGBoost pipeline. It stages `/urbantransit/clean/` Parquet locally and recomputes joins, targets, lags, route profiles, imputations, encodings, and splits from raw cleaned data. It imports neither PySpark nor any Phase 4/6 feature table, Spark model, or Spark prediction. The common chronological split is train 2025-09-01..2026-05-01, validation 2026-05-02..2026-07-01, and test 2026-07-02..2026-08-31.

## Tasks and chosen methods

- **Delay severity:** Logistic Regression, balanced Random Forest (180 trees, depth 12), and balanced XGBoost (300 trees, depth 8). XGBoost is the strongest Python model: test accuracy .5752 and true macro F1 .3825. It falls short of Spark’s final .8341 accuracy/.6950 macro F1 because it deliberately uses independently recomputed, strictly prior and scheduled features rather than Spark’s richer feature set.
- **Crowding:** the same three algorithms, excluding `occupancy_pct` and all direct same-trip occupancy proxies. XGBoost with validation-selected threshold .70 is best: test accuracy .9022, macro F1 .7609. This beats Spark’s .7484 macro F1 (and also has higher accuracy than Spark’s .8832).
- **Daily boardings:** independent strict-prior 28-day baseline, Ridge, Random Forest (220 trees, depth 14), and XGBoost (350 trees, depth 7). Random Forest is best: test MAE 193.37 and RMSE 422.42, both lower than the independent baseline’s 399.96 and 733.67. The independently aggregated baseline differs modestly from Spark’s 430.03/800.95 because source aggregation and missing-measurement handling are independently implemented.
- **Route clustering:** StandardScaler plus K-Means, DBSCAN, and Agglomerative candidates. Agglomerative k=5 is selected (silhouette .3241), slightly above K-Means k=4 (.3191). Its profile means are saved in `reports/python_cluster_profiles.csv`.

Macro F1 is the unweighted average class F1, so it gives the minority crowding and severe-delay classes equal importance. Accuracy is the share of correct predictions. MAE/RMSE are average and squared-error demand differences; lower is better. Silhouette compares within-cluster compactness against separation; higher is better.

Spark and Python can disagree because they independently derive raw-data features, use different imputation/encoding/scaling implementations, use different algorithms, and select models on validation independently. A disagreement is expected evidence of independent pipelines, not reused output.
