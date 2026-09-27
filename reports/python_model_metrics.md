# Python Model Metrics

Independent Phase 7 pandas/PyArrow pipeline. Chronological split: train 2025-09-01..2026-05-01; validation 2026-05-02..2026-07-01; test 2026-07-02..2026-08-31.

## crowding_flag

| algorithm | validation | test / silhouette |
|---|---|---|
| logistic_regression | `{'accuracy': 0.885409, 'macro_f1': 0.664635, 'per_class_f1': {'0.0': 0.936738, '1.0': 0.392532}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[234880, 20005], [11720, 10250]]}}` | `{'accuracy': 0.878204, 'macro_f1': 0.665711, 'per_class_f1': {'0.0': 0.932233, '1.0': 0.39919}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[226384, 20908], [12005, 10934]]}}` |
| random_forest | `{'accuracy': 0.913829, 'macro_f1': 0.769356, 'per_class_f1': {'0.0': 0.951898, '1.0': 0.586813}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[236057, 18828], [5029, 16941]]}}` | `{'accuracy': 0.905003, 'macro_f1': 0.762332, 'per_class_f1': {'0.0': 0.946474, '1.0': 0.578189}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[226966, 20326], [5345, 17594]]}}` |
| xgboost | `{'accuracy': 0.906301, 'macro_f1': 0.762824, 'per_class_f1': {'0.0': 0.947294, '1.0': 0.578353}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[233123, 21762], [4179, 17791]]}}` | `{'accuracy': 0.894117, 'macro_f1': 0.749294, 'per_class_f1': {'0.0': 0.93984, '1.0': 0.558748}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[223502, 23790], [4823, 18116]]}}` |

## daily_boardings

| algorithm | validation | test / silhouette |
|---|---|---|
| baseline_28day | `{'mae': 474.295287, 'rmse': 927.138142, 'mape': 47.83125, 'r2': 0.826249}` | `{'mae': 401.403731, 'rmse': 737.173292, 'mape': 33.205756, 'r2': 0.879103}` |
| random_forest | `{'mae': 276.266027, 'rmse': 683.193224, 'mape': 31.438675, 'r2': 0.905653}` | `{'mae': 195.300047, 'rmse': 426.707724, 'mape': 14.977334, 'r2': 0.959492}` |
| ridge | `{'mae': 318.280842, 'rmse': 741.875186, 'mape': 32.931067, 'r2': 0.88875}` | `{'mae': 206.306104, 'rmse': 422.258187, 'mape': 16.413577, 'r2': 0.960333}` |
| xgboost | `{'mae': 278.077271, 'rmse': 684.900517, 'mape': 31.327835, 'r2': 0.905181}` | `{'mae': 201.640427, 'rmse': 451.868067, 'mape': 15.701938, 'r2': 0.954575}` |

## delay_severity

| algorithm | validation | test / silhouette |
|---|---|---|
| logistic_regression | `{'accuracy': 0.665848, 'macro_f1': 0.399076, 'per_class_f1': {'Minor': 0.266923, 'Moderate': 0.385669, 'On Time': 0.813757, 'Severe': 0.129956}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[13113, 9441, 15584, 2159], [5367, 12099, 3573, 2827], [39287, 16715, 172243, 3568], [189, 622, 115, 708]]}}` | `{'accuracy': 0.587337, 'macro_f1': 0.384795, 'per_class_f1': {'Minor': 0.26006, 'Moderate': 0.397464, 'On Time': 0.751079, 'Severe': 0.130577}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[14545, 11635, 15996, 3197], [7671, 16925, 5704, 4606], [43975, 20760, 138024, 4938], [295, 939, 114, 1058]]}}` |
| logistic_regression | `{'accuracy': 0.652121, 'macro_f1': 0.406391, 'per_class_f1': {'Minor': 0.261164, 'Moderate': 0.384867, 'On Time': 0.802531, 'Severe': 0.177002}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[14609, 12281, 16747, 2261], [5616, 15483, 3181, 3182], [45415, 24350, 190752, 3856], [338, 883, 323, 1166]]}}` | `{'accuracy': 0.595892, 'macro_f1': 0.390593, 'per_class_f1': {'Minor': 0.259013, 'Moderate': 0.403154, 'On Time': 0.756729, 'Severe': 0.143476}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[15493, 13915, 17378, 2917], [7821, 19989, 5504, 4189], [46341, 26635, 155257, 3836], [273, 1121, 129, 1044]]}}` |
| random_forest | `{'accuracy': 0.678751, 'macro_f1': 0.436564, 'per_class_f1': {'Minor': 0.317351, 'Moderate': 0.410843, 'On Time': 0.817517, 'Severe': 0.200545}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[15832, 9067, 13955, 1443], [5398, 13996, 2064, 2408], [38106, 20559, 171365, 1783], [143, 645, 36, 810]]}}` | `{'accuracy': 0.606704, 'macro_f1': 0.410133, 'per_class_f1': {'Minor': 0.305642, 'Moderate': 0.407629, 'On Time': 0.761294, 'Severe': 0.165965}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[17073, 11123, 14974, 2203], [8195, 18327, 4710, 3674], [40800, 24494, 139790, 2613], [278, 1070, 72, 986]]}}` |
| random_forest | `{'accuracy': 0.658128, 'macro_f1': 0.419203, 'per_class_f1': {'Minor': 0.289482, 'Moderate': 0.3874, 'On Time': 0.806035, 'Severe': 0.193895}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[16103, 11667, 15511, 2617], [5255, 15785, 2326, 4096], [43744, 25870, 190722, 4037], [254, 708, 303, 1445]]}}` | `{'accuracy': 0.588568, 'macro_f1': 0.396503, 'per_class_f1': {'Minor': 0.28617, 'Moderate': 0.391112, 'On Time': 0.749538, 'Severe': 0.159192}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[17869, 13070, 15281, 3483], [8194, 19221, 4384, 5704], [48859, 27649, 150918, 4643], [259, 846, 44, 1418]]}}` |
| xgboost | `{'accuracy': 0.685696, 'macro_f1': 0.445751, 'per_class_f1': {'Minor': 0.338411, 'Moderate': 0.41396, 'On Time': 0.819629, 'Severe': 0.211006}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[17572, 7935, 14022, 768], [6577, 13540, 2388, 1361], [39172, 19288, 172402, 951], [232, 788, 58, 556]]}}` | `{'accuracy': 0.61916, 'macro_f1': 0.412576, 'per_class_f1': {'Minor': 0.322858, 'Moderate': 0.409494, 'On Time': 0.76847, 'Severe': 0.149484}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[17912, 10626, 15579, 1256], [8999, 18555, 5396, 1956], [38243, 25237, 142754, 1463], [432, 1300, 102, 572]]}}` |
| xgboost | `{'accuracy': 0.6591, 'macro_f1': 0.430238, 'per_class_f1': {'Minor': 0.324733, 'Moderate': 0.394702, 'On Time': 0.801143, 'Severe': 0.200372}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[19917, 8995, 14754, 2232], [6742, 14826, 2422, 3472], [49757, 23083, 188352, 3181], [353, 759, 307, 1291]]}}` | `{'accuracy': 0.588575, 'macro_f1': 0.401229, 'per_class_f1': {'Minor': 0.316143, 'Moderate': 0.394299, 'On Time': 0.742662, 'Severe': 0.151811}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[21104, 11352, 14386, 2861], [9717, 19103, 4284, 4399], [52614, 27881, 148131, 3443], [371, 1057, 49, 1090]]}}` |

## occupancy_forecast

| algorithm | validation | test / silhouette |
|---|---|---|
| random_forest | `{'mae': 0.120535, 'rmse': 0.176105, 'r2': 0.69578, 'mape_nonzero_pct': 61.164859, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.'}` | `{'mae': 0.118475, 'rmse': 0.174079, 'r2': 0.714109, 'mape_nonzero_pct': 54.578582, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.'}` |
| ridge | `{'mae': 0.142462, 'rmse': 0.201467, 'r2': 0.601845, 'mape_nonzero_pct': 82.334968, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.'}` | `{'mae': 0.134797, 'rmse': 0.192728, 'r2': 0.649572, 'mape_nonzero_pct': 70.030327, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.'}` |
| random_forest | `{'mae': 0.120535, 'rmse': 0.176105, 'r2': 0.69578, 'mape_nonzero_pct': 61.164859, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.'}` | `{'mae': 0.118475, 'rmse': 0.174079, 'r2': 0.714109, 'mape_nonzero_pct': 54.578582, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.'}` |

## route_clustering

| algorithm | validation | test / silhouette |
|---|---|---|
| agglomerative_k3 | `{}` | `0.271916` |
| agglomerative_k4 | `{}` | `0.287963` |
| agglomerative_k5 | `{}` | `0.312627` |
| dbscan_eps0.6 | `{}` | `-0.224299` |
| dbscan_eps0.8 | `{}` | `-0.106239` |
| dbscan_eps1.0 | `{}` | `-0.101361` |
| kmeans_k3 | `{}` | `0.312747` |
| kmeans_k4 | `{}` | `0.324651` |
| kmeans_k5 | `{}` | `0.353109` |

## stop_period_demand

| algorithm | validation | test / silhouette |
|---|---|---|
| random_forest | `{'mae': 0.960824, 'rmse': 1.641187, 'r2': 0.843946, 'mape_nonzero_pct': 47.892583, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` | `{'mae': 1.021776, 'rmse': 1.804427, 'r2': 0.844115, 'mape_nonzero_pct': 49.173845, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` |
| ridge | `{'mae': 1.064268, 'rmse': 1.814392, 'r2': 0.809269, 'mape_nonzero_pct': 53.414187, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` | `{'mae': 1.134617, 'rmse': 2.003881, 'r2': 0.807749, 'mape_nonzero_pct': 55.154153, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` |
| random_forest | `{'mae': 0.960824, 'rmse': 1.641187, 'r2': 0.843946, 'mape_nonzero_pct': 47.892583, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` | `{'mae': 1.021776, 'rmse': 1.804427, 'r2': 0.844115, 'mape_nonzero_pct': 49.173845, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` |
