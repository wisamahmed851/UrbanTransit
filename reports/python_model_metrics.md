# Python Model Metrics

Independent Phase 7 pandas/PyArrow pipeline. Chronological split: train 2025-09-01..2026-05-01; validation 2026-05-02..2026-07-01; test 2026-07-02..2026-08-31.

## crowding_flag

| algorithm | validation | test / silhouette |
|---|---|---|
| logistic_regression | `{'accuracy': 0.881617, 'macro_f1': 0.66268, 'per_class_f1': {'0.0': 0.934437, '1.0': 0.390924}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[233562, 21323], [11452, 10518]]}}` | `{'accuracy': 0.872753, 'macro_f1': 0.662827, 'per_class_f1': {'0.0': 0.928875, '1.0': 0.396779}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[224536, 22756], [11630, 11309]]}}` |
| random_forest | `{'accuracy': 0.886114, 'macro_f1': 0.693593, 'per_class_f1': {'0.0': 0.936471, '1.0': 0.450716}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[232389, 22496], [9034, 12936]]}}` | `{'accuracy': 0.879866, 'macro_f1': 0.69497, 'per_class_f1': {'0.0': 0.932454, '1.0': 0.457487}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[224079, 23213], [9251, 13688]]}}` |
| xgboost | `{'accuracy': 0.905423, 'macro_f1': 0.718865, 'per_class_f1': {'0.0': 0.947881, '1.0': 0.489849}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[238100, 16785], [9399, 12571]]}}` | `{'accuracy': 0.900933, 'macro_f1': 0.723204, 'per_class_f1': {'0.0': 0.945003, '1.0': 0.501406}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[229999, 17293], [9478, 13461]]}}` |

## daily_boardings

| algorithm | validation | test / silhouette |
|---|---|---|
| baseline_28day | `{'mae': 474.295287, 'rmse': 927.138142, 'mape': 47.83125, 'r2': 0.826249}` | `{'mae': 401.403731, 'rmse': 737.173292, 'mape': 33.205756, 'r2': 0.879103}` |
| random_forest | `{'mae': 278.025314, 'rmse': 684.998441, 'mape': 31.929394, 'r2': 0.905154}` | `{'mae': 195.533922, 'rmse': 425.184865, 'mape': 15.193106, 'r2': 0.959781}` |
| ridge | `{'mae': 318.280842, 'rmse': 741.875186, 'mape': 32.931067, 'r2': 0.88875}` | `{'mae': 206.306104, 'rmse': 422.258187, 'mape': 16.413577, 'r2': 0.960333}` |
| xgboost | `{'mae': 274.323059, 'rmse': 669.355847, 'mape': 32.554153, 'r2': 0.909437}` | `{'mae': 196.168396, 'rmse': 419.867781, 'mape': 16.207643, 'r2': 0.960781}` |

## delay_severity

| algorithm | validation | test / silhouette |
|---|---|---|
| logistic_regression | `{'accuracy': 0.806962, 'macro_f1': 0.3614, 'per_class_f1': {'Minor': 0.313538, 'Moderate': 0.212652, 'On Time': 0.919411, 'Severe': 0.0}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[10839, 3174, 26279, 5], [13213, 3538, 7115, 0], [3827, 2184, 225783, 19], [964, 513, 157, 0]]}, 'within_one_band_accuracy': 0.964907, 'within_one_band_note': 'Ordinal severity prediction is exact or one adjacent band away.'}` | `{'accuracy': 0.752702, 'macro_f1': 0.369383, 'per_class_f1': {'Minor': 0.324253, 'Moderate': 0.255621, 'On Time': 0.897658, 'Severe': 0.0}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[13969, 4946, 26407, 51], [19357, 6458, 9082, 9], [5972, 3441, 198144, 140], [1490, 777, 139, 0]]}, 'within_one_band_accuracy': 0.950606, 'within_one_band_note': 'Ordinal severity prediction is exact or one adjacent band away.'}` |
| random_forest | `{'accuracy': 0.843718, 'macro_f1': 0.468463, 'per_class_f1': {'Minor': 0.243593, 'Moderate': 0.61418, 'On Time': 0.928718, 'Severe': 0.087362}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[6074, 6962, 27261, 0], [2773, 14627, 6458, 8], [595, 895, 230323, 0], [131, 1281, 147, 75]]}, 'within_one_band_accuracy': 0.974359, 'within_one_band_note': 'Ordinal severity prediction is exact or one adjacent band away.'}` | `{'accuracy': 0.799939, 'macro_f1': 0.438037, 'per_class_f1': {'Minor': 0.216152, 'Moderate': 0.605345, 'On Time': 0.904443, 'Severe': 0.026208}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[6049, 8606, 30718, 0], [3788, 20263, 10851, 4], [539, 1214, 205944, 0], [221, 1958, 195, 32]]}, 'within_one_band_accuracy': 0.957019, 'within_one_band_note': 'Ordinal severity prediction is exact or one adjacent band away.'}` |
| xgboost | `{'accuracy': 0.890068, 'macro_f1': 0.718554, 'per_class_f1': {'Minor': 0.614958, 'Moderate': 0.691401, 'On Time': 0.954931, 'Severe': 0.612927}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[23306, 4291, 12698, 2], [6109, 15607, 1876, 274], [6081, 596, 225136, 0], [4, 786, 0, 844]]}, 'within_one_band_accuracy': 0.991674, 'within_one_band_note': 'Ordinal severity prediction is exact or one adjacent band away.'}` | `{'accuracy': 0.851664, 'macro_f1': 0.685959, 'per_class_f1': {'Minor': 0.568146, 'Moderate': 0.675802, 'On Time': 0.937808, 'Severe': 0.562081}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[24453, 5408, 15511, 1], [9418, 21602, 3502, 384], [6829, 706, 200162, 0], [7, 1308, 0, 1091]]}, 'within_one_band_accuracy': 0.985481, 'within_one_band_note': 'Ordinal severity prediction is exact or one adjacent band away.'}` |

## occupancy_forecast

| algorithm | validation | test / silhouette |
|---|---|---|
| random_forest | `{'mae': 0.06969, 'rmse': 0.11056, 'r2': 0.869356, 'mape_nonzero_pct': 28.679733, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.', 'within_20pp_accuracy': 0.926917, 'within_20pp_note': 'Share of trips predicted within 20 percentage points of peak occupancy.'}` | `{'mae': 0.068297, 'rmse': 0.109394, 'r2': 0.87726, 'mape_nonzero_pct': 24.754239, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.', 'within_20pp_accuracy': 0.928114, 'within_20pp_note': 'Share of trips predicted within 20 percentage points of peak occupancy.'}` |
| ridge | `{'mae': 0.099956, 'rmse': 0.147061, 'r2': 0.768853, 'mape_nonzero_pct': 51.595067, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.', 'within_20pp_accuracy': 0.862857, 'within_20pp_note': 'Share of trips predicted within 20 percentage points of peak occupancy.'}` | `{'mae': 0.093518, 'rmse': 0.139694, 'r2': 0.799849, 'mape_nonzero_pct': 42.508949, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.', 'within_20pp_accuracy': 0.876798, 'within_20pp_note': 'Share of trips predicted within 20 percentage points of peak occupancy.'}` |
| xgboost | `{'mae': 0.06775, 'rmse': 0.104971, 'r2': 0.88223, 'mape_nonzero_pct': 29.213444, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.', 'within_20pp_accuracy': 0.934091, 'within_20pp_note': 'Share of trips predicted within 20 percentage points of peak occupancy.'}` | `{'mae': 0.06537, 'rmse': 0.102369, 'r2': 0.892518, 'mape_nonzero_pct': 24.185066, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.', 'within_20pp_accuracy': 0.938132, 'within_20pp_note': 'Share of trips predicted within 20 percentage points of peak occupancy.'}` |
| xgboost | `{'mae': 0.06775, 'rmse': 0.104971, 'r2': 0.88223, 'mape_nonzero_pct': 29.213444, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.', 'within_20pp_accuracy': 0.934091, 'within_20pp_note': 'Share of trips predicted within 20 percentage points of peak occupancy.'}` | `{'mae': 0.06537, 'rmse': 0.102369, 'r2': 0.892518, 'mape_nonzero_pct': 24.185066, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.', 'within_20pp_accuracy': 0.938132, 'within_20pp_note': 'Share of trips predicted within 20 percentage points of peak occupancy.'}` |

## route_clustering

| algorithm | validation | test / silhouette |
|---|---|---|
| agglomerative_k3 | `{}` | `0.2966` |
| agglomerative_k4 | `{}` | `0.305139` |
| agglomerative_k5 | `{}` | `0.336286` |
| dbscan_eps0.6 | `{}` | `-0.301045` |
| dbscan_eps0.8 | `{}` | `-0.033679` |
| dbscan_eps1.0 | `{}` | `-0.015649` |
| kmeans_k3 | `{}` | `0.316451` |
| kmeans_k4 | `{}` | `0.318164` |
| kmeans_k5 | `{}` | `0.326968` |

## stop_period_demand

| algorithm | validation | test / silhouette |
|---|---|---|
| random_forest | `{'mae': 1.093548, 'rmse': 2.055696, 'r2': 0.777738, 'mape_nonzero_pct': 58.274817, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` | `{'mae': 0.997778, 'rmse': 1.733447, 'r2': 0.849463, 'mape_nonzero_pct': 48.410796, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` |
| ridge | `{'mae': 1.181937, 'rmse': 2.128384, 'r2': 0.761743, 'mape_nonzero_pct': 63.088757, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` | `{'mae': 1.109203, 'rmse': 1.913492, 'r2': 0.816568, 'mape_nonzero_pct': 54.695928, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` |
| random_forest | `{'mae': 1.093548, 'rmse': 2.055696, 'r2': 0.777738, 'mape_nonzero_pct': 58.274817, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` | `{'mae': 0.997778, 'rmse': 1.733447, 'r2': 0.849463, 'mape_nonzero_pct': 48.410796, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` |
