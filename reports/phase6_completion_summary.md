# Phase 6 Completion Summary

Generated from Colab output artifacts.

| metric file | task | algorithm | test metric |
|---|---|---|---|
| crowding_flag_gbt_sample.json | crowding_flag | gbt | {'accuracy': 0.842216, 'macro_f1': 0.687051} |
| crowding_flag_logistic_regression_sample.json | crowding_flag | logistic_regression | {'accuracy': 0.822269, 'macro_f1': 0.655276} |
| crowding_flag_random_forest_sample.json | crowding_flag | random_forest | {'accuracy': 0.834653, 'macro_f1': 0.676805} |
| daily_boardings_decision_tree.json | daily_boardings | decision_tree | {'mae': 262.848648, 'rmse': 542.532535, 'r2': 0.94563, 'mape': 21.70088} |
| daily_boardings_gbt.json | daily_boardings | gbt | {'mae': 236.85026, 'rmse': 490.553225, 'r2': 0.955549, 'mape': 18.635796} |
| daily_boardings_linear_regression.json | daily_boardings | linear_regression | {'mae': 261.758384, 'rmse': 515.932216, 'r2': 0.950831, 'mape': 28.335985} |
| daily_boardings_random_forest.json | daily_boardings | random_forest | {'mae': 217.072762, 'rmse': 476.839027, 'r2': 0.958, 'mape': 25.625851} |
| delay_severity_decision_tree_sample.json | delay_severity | decision_tree | {'accuracy': 0.815332, 'macro_f1': 0.617391} |
| delay_severity_gbt_one_vs_rest_sample.json | delay_severity | gbt_one_vs_rest | {'accuracy': 0.820847, 'macro_f1': 0.616302} |
| delay_severity_logistic_regression.json | delay_severity | logistic_regression | {'accuracy': 0.772877, 'weighted_f1': 0.700389} |
| delay_severity_random_forest.json | delay_severity | random_forest | {'accuracy': 0.809124, 'weighted_f1': 0.757941} |
| delay_severity_xgboost_gpu.json | delay_severity | xgboost_gpu_multiclass | {'accuracy': 0.768878, 'macro_f1': 0.67211} |
| route_clustering_bisecting_kmeans_k3.json | route_clustering | bisecting_kmeans | see file |
| route_clustering_bisecting_kmeans_k4.json | route_clustering | bisecting_kmeans | see file |
| route_clustering_bisecting_kmeans_k5.json | route_clustering | bisecting_kmeans | see file |
| route_clustering_gaussian_mixture_k3.json | route_clustering | gaussian_mixture | see file |
| route_clustering_gaussian_mixture_k4.json | route_clustering | gaussian_mixture | see file |
| route_clustering_gaussian_mixture_k5.json | route_clustering | gaussian_mixture | see file |
| route_clustering_kmeans_k3.json | route_clustering | kmeans | see file |
| route_clustering_kmeans_k4.json | route_clustering | kmeans | see file |
| route_clustering_kmeans_k5.json | route_clustering | kmeans | see file |

## Notes

- Task A GBT and Decision Tree used a stratified 10% train/validation sample; their JSON files state this explicitly.
- Task B excludes contemporaneous `occupancy_pct`, because it directly defines `crowding_flag`; it uses strictly prior rolling/lag occupancy features.
- Task C uses strict-prior demand lag and rolling features. Task D clusters only train-period route profiles.
- Class counts and Task B positive rates are recorded in `reports/phase6_class_distribution.md`.

## Forecast baseline and clustering interpretation

The strict-prior 28-day trailing-demand baseline has test MAE 430.03 and RMSE 800.95. The selected Random Forest forecast improves both (MAE 217.07; RMSE 476.84). See `models/spark/metrics/demand_forecast_baseline.json`.

K-Means k=4 cluster profiles use the stored Phase 4 route features: `route_load_factor`, `route_reliability_delay_min`, `trip_punctuality_rate`, `avg_trip_boardings`, `avg_daily_boardings`, `crowding_rate`, `bunching_rate`, and `arrival_delay_std_min`.

| cluster | routes | interpretation | evidence |
|---|---:|---|---|
| 0 | 32 | Low-occupancy delay-prone mid-demand routes | load .30, delay 3.67 min, punctuality .56 |
| 1 | 60 | Low-demand reliable routes | 951 daily boardings, 1.27 min delay, punctuality .72 |
| 2 | 20 | High-demand high-crowding routes | load .73, 3,366 daily boardings, crowding .35 |
| 3 | 4 | Very-high-demand unreliable trunk routes | 14,705 daily boardings, 100 boardings/trip, delay 8.39 min, punctuality .46 |

## Metric integrity and WSL evidence status

- The historical Logistic Regression and Random Forest fields previously called `macro_f1` are Spark `MulticlassClassificationEvaluator(metricName="f1")` results, which are weighted F1. Their JSON fields have been corrected to `weighted_f1`; they are not evidence of the macro-F1 target.
- Task A's final full-data, class-weighted Random Forest recovery is complete. The selected depth-12 model has true test macro F1 0.695002 and test accuracy 0.834071, so it does not meet either SRS test target. Per-class metrics and the confusion matrix are saved with the final artifact.
- Task B's enhanced full-data, class-weighted Random Forest recovery and validation-only threshold selection are complete. Its true test macro F1 is 0.748354 and test accuracy is 0.883150; it meets the SRS alternative through test accuracy. Threshold .50 was selected by validation macro F1.
- The WSL/HDFS Task D demo executed with Spark 4.2.0 and read 116 route profiles from `hdfs://localhost:9000/urbantransit/features/route_features`. Canonical route ordering and one input partition make seeded K-Means reproducible: silhouette 0.494760 versus the Colab artifact's 0.514014 (delta 0.019254, within +/-0.05). The model was saved to `hdfs://localhost:9000/urbantransit/models/phase6/route_clustering/kmeans_k4_wsl_v1`; terminal evidence is in `reports/processing_logs/phase6_taskD_wsl.log`.

## Final full-data recovery results (WSL/HDFS, 2026-09-26)

Both recovery models were trained from the complete chronological training split using inverse-frequency weights.  Depth was selected only on validation; test was not used for fitting or selection. `weighted_f1` is Spark's `MulticlassClassificationEvaluator(metricName="f1")`; `macro_f1` is the unweighted mean of separately calculated class F1 scores.

| task | selected RF | validation accuracy | validation macro F1 | test accuracy | test macro F1 | result |
|---|---|---:|---:|---:|---:|---|
| A: delay severity | 100 trees, depth 12, square-root class weights | .866115 | .717740 | .834071 | .695002 | misses target |
| B: crowding flag | 80 trees, depth 8, threshold .50 | .872972 | .729796 | .883150 | .748354 | meets target via test accuracy |

- Task A test per-class F1: On Time .916109, Minor .494620, Moderate .736660, Severe .632618. Its confusion matrix shows 20,266 Minor trips predicted On Time and 12,194 On Time trips predicted Minor. The target remains difficult to predict from the available strictly pre-departure features; Severe is only 1.2% of training rows and Minor remains strongly confusable with On Time.
- Task B test per-class F1: non-crowding .932530, crowding .564177. Validation threshold tuning tried .20, .30, .40 and .50; .50 was best, so reducing the threshold would have reduced macro F1 rather than improved it.
- Final full metrics, class weights, validation trials and confusion matrices are saved in `models/spark/metrics/delay_severity_random_forest_full_weighted_enhanced_v4_depth12.json` and `models/spark/metrics/crowding_flag_random_forest_full_weighted_enhanced_v2.json`.
