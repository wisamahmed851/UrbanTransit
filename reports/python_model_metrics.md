# Python Model Metrics

Independent Phase 7 pandas/PyArrow pipeline. Chronological split: train 2025-09-01..2026-05-01; validation 2026-05-02..2026-07-01; test 2026-07-02..2026-08-31.

## crowding_flag

| algorithm | validation | test / silhouette |
|---|---|---|
| logistic_regression | `{'accuracy': 0.895435, 'macro_f1': 0.688949, 'per_class_f1': {'0.0': 0.942381, '1.0': 0.435518}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[237994, 19977], [9126, 11227]]}}` | `{'accuracy': 0.890466, 'macro_f1': 0.697353, 'per_class_f1': {'0.0': 0.939107, '1.0': 0.455598}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[229414, 20988], [8763, 12449]]}}` |
| random_forest | `{'accuracy': 0.955631, 'macro_f1': 0.85388, 'per_class_f1': {'0.0': 0.975814, '1.0': 0.731946}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[249115, 8856], [3493, 16860]]}}` | `{'accuracy': 0.939712, 'macro_f1': 0.825686, 'per_class_f1': {'0.0': 0.96667, '1.0': 0.684702}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[237459, 12943], [3432, 17780]]}}` |
| xgboost | `{'accuracy': 0.947608, 'macro_f1': 0.841698, 'per_class_f1': {'0.0': 0.971181, '1.0': 0.712216}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[245698, 12273], [2309, 18044]]}}` | `{'accuracy': 0.942429, 'macro_f1': 0.835343, 'per_class_f1': {'0.0': 0.96813, '1.0': 0.702555}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[237510, 12892], [2745, 18467]]}}` |

## daily_boardings

| algorithm | validation | test / silhouette |
|---|---|---|
| baseline_28day | `{'mae': 478.372439, 'rmse': 935.138124, 'mape': 47.23088, 'r2': 0.829465}` | `{'mae': 401.755282, 'rmse': 733.194846, 'mape': 32.403096, 'r2': 0.884266}` |
| random_forest | `{'mae': 250.967864, 'rmse': 687.318159, 'mape': 28.799758, 'r2': 0.907875}` | `{'mae': 168.092488, 'rmse': 393.811994, 'mape': 12.024627, 'r2': 0.966611}` |
| ridge | `{'mae': 298.584994, 'rmse': 739.233876, 'mape': 30.692859, 'r2': 0.893432}` | `{'mae': 174.220117, 'rmse': 383.726948, 'mape': 13.374548, 'r2': 0.9683}` |
| xgboost | `{'mae': 249.254517, 'rmse': 681.612564, 'mape': 28.390521, 'r2': 0.909398}` | `{'mae': 169.07872, 'rmse': 405.546468, 'mape': 12.515956, 'r2': 0.964592}` |

## delay_severity

| algorithm | validation | test / silhouette |
|---|---|---|
| logistic_regression | `{'accuracy': 0.868547, 'macro_f1': 0.426911, 'per_class_f1': {'Minor': 0.280507, 'Moderate': 0.298043, 'On Time': 0.938454, 'Severe': 0.190641}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[5579, 3182, 20861, 22], [2892, 3412, 8625, 47], [1545, 1165, 249931, 48], [118, 161, 538, 110]]}, 'within_one_band_accuracy': 0.964739, 'within_one_band_note': 'Ordinal severity prediction is exact or one adjacent band away.'}` | `{'accuracy': 0.800841, 'macro_f1': 0.403518, 'per_class_f1': {'Minor': 0.268615, 'Moderate': 0.309902, 'On Time': 0.903285, 'Severe': 0.132269}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[7381, 4853, 25656, 83], [5341, 6106, 14242, 122], [4005, 2328, 219408, 74], [256, 308, 679, 116]]}, 'within_one_band_accuracy': 0.939297, 'within_one_band_note': 'Ordinal severity prediction is exact or one adjacent band away.'}` |
| logistic_regression | `{'accuracy': 0.652121, 'macro_f1': 0.406391, 'per_class_f1': {'Minor': 0.261164, 'Moderate': 0.384867, 'On Time': 0.802531, 'Severe': 0.177002}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[14609, 12281, 16747, 2261], [5616, 15483, 3181, 3182], [45415, 24350, 190752, 3856], [338, 883, 323, 1166]]}}` | `{'accuracy': 0.595892, 'macro_f1': 0.390593, 'per_class_f1': {'Minor': 0.259013, 'Moderate': 0.403154, 'On Time': 0.756729, 'Severe': 0.143476}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[15493, 13915, 17378, 2917], [7821, 19989, 5504, 4189], [46341, 26635, 155257, 3836], [273, 1121, 129, 1044]]}}` |
| random_forest | `{'accuracy': 0.894825, 'macro_f1': 0.574867, 'per_class_f1': {'Minor': 0.485353, 'Moderate': 0.488788, 'On Time': 0.952156, 'Severe': 0.373169}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[11565, 1875, 16192, 12], [3816, 5907, 5146, 107], [2545, 980, 249155, 9], [86, 432, 167, 242]]}, 'within_one_band_accuracy': 0.97854, 'within_one_band_note': 'Ordinal severity prediction is exact or one adjacent band away.'}` | `{'accuracy': 0.826752, 'macro_f1': 0.490576, 'per_class_f1': {'Minor': 0.399239, 'Moderate': 0.434885, 'On Time': 0.915539, 'Severe': 0.21264}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[12073, 2918, 22948, 34], [5900, 8709, 11099, 103], [4314, 1896, 219588, 17], [220, 718, 241, 180]]}, 'within_one_band_accuracy': 0.953577, 'within_one_band_note': 'Ordinal severity prediction is exact or one adjacent band away.'}` |
| random_forest | `{'accuracy': 0.658128, 'macro_f1': 0.419203, 'per_class_f1': {'Minor': 0.289482, 'Moderate': 0.3874, 'On Time': 0.806035, 'Severe': 0.193895}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[16103, 11667, 15511, 2617], [5255, 15785, 2326, 4096], [43744, 25870, 190722, 4037], [254, 708, 303, 1445]]}}` | `{'accuracy': 0.588568, 'macro_f1': 0.396503, 'per_class_f1': {'Minor': 0.28617, 'Moderate': 0.391112, 'On Time': 0.749538, 'Severe': 0.159192}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[17869, 13070, 15281, 3483], [8194, 19221, 4384, 5704], [48859, 27649, 150918, 4643], [259, 846, 44, 1418]]}}` |
| xgboost | `{'accuracy': 0.89511, 'macro_f1': 0.596473, 'per_class_f1': {'Minor': 0.499798, 'Moderate': 0.491807, 'On Time': 0.952656, 'Severe': 0.441632}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[12363, 1797, 15460, 24], [4129, 5973, 4731, 143], [3258, 1113, 248304, 14], [78, 431, 104, 314]]}, 'within_one_band_accuracy': 0.979667, 'within_one_band_note': 'Ordinal severity prediction is exact or one adjacent band away.'}` | `{'accuracy': 0.826422, 'macro_f1': 0.520947, 'per_class_f1': {'Minor': 0.413995, 'Moderate': 0.437934, 'On Time': 0.915475, 'Severe': 0.316384}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[12963, 2776, 22181, 53], [6247, 8827, 10542, 195], [5264, 2163, 218356, 32], [177, 735, 139, 308]]}, 'within_one_band_accuracy': 0.954956, 'within_one_band_note': 'Ordinal severity prediction is exact or one adjacent band away.'}` |
| xgboost | `{'accuracy': 0.6591, 'macro_f1': 0.430238, 'per_class_f1': {'Minor': 0.324733, 'Moderate': 0.394702, 'On Time': 0.801143, 'Severe': 0.200372}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[19917, 8995, 14754, 2232], [6742, 14826, 2422, 3472], [49757, 23083, 188352, 3181], [353, 759, 307, 1291]]}}` | `{'accuracy': 0.588575, 'macro_f1': 0.401229, 'per_class_f1': {'Minor': 0.316143, 'Moderate': 0.394299, 'On Time': 0.742662, 'Severe': 0.151811}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[21104, 11352, 14386, 2861], [9717, 19103, 4284, 4399], [52614, 27881, 148131, 3443], [371, 1057, 49, 1090]]}}` |

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
