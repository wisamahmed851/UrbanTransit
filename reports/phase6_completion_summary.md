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
| delay_severity_logistic_regression.json | delay_severity | logistic_regression | {'accuracy': 0.772877, 'macro_f1': 0.700389} |
| delay_severity_random_forest.json | delay_severity | random_forest | {'accuracy': 0.809124, 'macro_f1': 0.757941} |
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
