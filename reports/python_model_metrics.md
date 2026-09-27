# Python Model Metrics

Independent Phase 7 pandas/PyArrow pipeline. Chronological split: train 2025-09-01..2026-05-01; validation 2026-05-02..2026-07-01; test 2026-07-02..2026-08-31.

## crowding_flag

| algorithm | validation | test / silhouette |
|---|---|---|
| logistic_regression | `{'accuracy': 0.885035, 'macro_f1': 0.665583, 'per_class_f1': {'0.0': 0.936486, '1.0': 0.39468}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[268403, 22910], [13497, 11869]]}}` | `{'accuracy': 0.878656, 'macro_f1': 0.666463, 'per_class_f1': {'0.0': 0.932497, '1.0': 0.400429}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[251025, 23123], [13220, 12136]]}}` |
| random_forest | `{'accuracy': 0.907, 'macro_f1': 0.750534, 'per_class_f1': {'0.0': 0.948102, '1.0': 0.552967}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[269013, 22300], [7151, 18215]]}}` | `{'accuracy': 0.899811, 'macro_f1': 0.74583, 'per_class_f1': {'0.0': 0.943662, '1.0': 0.547999}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[251307, 22841], [7166, 18190]]}}` |
| xgboost | `{'accuracy': 0.913941, 'macro_f1': 0.775447, 'per_class_f1': {'0.0': 0.951797, '1.0': 0.599097}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[269063, 22250], [5003, 20363]]}}` | `{'accuracy': 0.902679, 'macro_f1': 0.761303, 'per_class_f1': {'0.0': 0.945004, '1.0': 0.577602}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[250427, 23721], [5427, 19929]]}}` |

## daily_boardings

| algorithm | validation | test / silhouette |
|---|---|---|
| baseline_28day | `{'mae': 479.551826, 'rmse': 937.410494, 'mape': 46.303891, 'r2': 0.836657}` | `{'mae': 399.95635, 'rmse': 733.671496, 'mape': 33.184021, 'r2': 0.88012}` |
| random_forest | `{'mae': 273.913689, 'rmse': 670.717864, 'mape': 29.584053, 'r2': 0.916378}` | `{'mae': 193.367119, 'rmse': 422.417388, 'mape': 14.677831, 'r2': 0.96026}` |
| ridge | `{'mae': 302.161443, 'rmse': 709.078454, 'mape': 30.499825, 'r2': 0.906539}` | `{'mae': 216.122834, 'rmse': 452.048268, 'mape': 16.784818, 'r2': 0.95449}` |
| xgboost | `{'mae': 278.769836, 'rmse': 683.740631, 'mape': 29.47095, 'r2': 0.913099}` | `{'mae': 199.296387, 'rmse': 450.605409, 'mape': 15.518914, 'r2': 0.95478}` |

## delay_severity

| algorithm | validation | test / silhouette |
|---|---|---|
| logistic_regression | `{'accuracy': 0.649924, 'macro_f1': 0.40634, 'per_class_f1': {'Minor': 0.268892, 'Moderate': 0.383777, 'On Time': 0.800664, 'Severe': 0.172028}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[15941, 10952, 16582, 2423], [6716, 14137, 3261, 3348], [49650, 20334, 189970, 4419], [363, 788, 345, 1214]]}}` | `{'accuracy': 0.588108, 'macro_f1': 0.389072, 'per_class_f1': {'Minor': 0.263966, 'Moderate': 0.399275, 'On Time': 0.749834, 'Severe': 0.143212}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[16774, 13101, 16842, 2986], [8990, 18835, 5350, 4328], [51297, 23882, 152574, 4316], [328, 1025, 119, 1095]]}}` |
| logistic_regression | `{'accuracy': 0.652121, 'macro_f1': 0.406391, 'per_class_f1': {'Minor': 0.261164, 'Moderate': 0.384867, 'On Time': 0.802531, 'Severe': 0.177002}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[14609, 12281, 16747, 2261], [5616, 15483, 3181, 3182], [45415, 24350, 190752, 3856], [338, 883, 323, 1166]]}}` | `{'accuracy': 0.595892, 'macro_f1': 0.390593, 'per_class_f1': {'Minor': 0.259013, 'Moderate': 0.403154, 'On Time': 0.756729, 'Severe': 0.143476}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[15493, 13915, 17378, 2917], [7821, 19989, 5504, 4189], [46341, 26635, 155257, 3836], [273, 1121, 129, 1044]]}}` |
| random_forest | `{'accuracy': 0.66175, 'macro_f1': 0.42132, 'per_class_f1': {'Minor': 0.292815, 'Moderate': 0.389228, 'On Time': 0.808726, 'Severe': 0.194513}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[16217, 11497, 15634, 2550], [5340, 15761, 2337, 4024], [43046, 25557, 191892, 3878], [265, 709, 318, 1418]]}}` | `{'accuracy': 0.593577, 'macro_f1': 0.399289, 'per_class_f1': {'Minor': 0.288442, 'Moderate': 0.394061, 'On Time': 0.75382, 'Severe': 0.160831}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[17838, 12927, 15516, 3422], [8220, 19308, 4441, 5534], [47670, 27410, 152491, 4498], [254, 847, 65, 1401]]}}` |
| random_forest | `{'accuracy': 0.658128, 'macro_f1': 0.419203, 'per_class_f1': {'Minor': 0.289482, 'Moderate': 0.3874, 'On Time': 0.806035, 'Severe': 0.193895}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[16103, 11667, 15511, 2617], [5255, 15785, 2326, 4096], [43744, 25870, 190722, 4037], [254, 708, 303, 1445]]}}` | `{'accuracy': 0.588568, 'macro_f1': 0.396503, 'per_class_f1': {'Minor': 0.28617, 'Moderate': 0.391112, 'On Time': 0.749538, 'Severe': 0.159192}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[17869, 13070, 15281, 3483], [8194, 19221, 4384, 5704], [48859, 27649, 150918, 4643], [259, 846, 44, 1418]]}}` |
| xgboost | `{'accuracy': 0.669639, 'macro_f1': 0.434585, 'per_class_f1': {'Minor': 0.331409, 'Moderate': 0.398, 'On Time': 0.80957, 'Severe': 0.19936}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[19832, 8784, 15216, 2066], [6836, 14804, 2586, 3236], [46752, 22544, 192124, 2953], [365, 798, 333, 1214]]}}` | `{'accuracy': 0.59986, 'macro_f1': 0.404835, 'per_class_f1': {'Minor': 0.319302, 'Moderate': 0.395083, 'On Time': 0.75388, 'Severe': 0.151077}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[20651, 11229, 15074, 2749], [9647, 19043, 4578, 4235], [48959, 27551, 152321, 3238], [391, 1074, 57, 1045]]}}` |
| xgboost | `{'accuracy': 0.6591, 'macro_f1': 0.430238, 'per_class_f1': {'Minor': 0.324733, 'Moderate': 0.394702, 'On Time': 0.801143, 'Severe': 0.200372}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[19917, 8995, 14754, 2232], [6742, 14826, 2422, 3472], [49757, 23083, 188352, 3181], [353, 759, 307, 1291]]}}` | `{'accuracy': 0.588575, 'macro_f1': 0.401229, 'per_class_f1': {'Minor': 0.316143, 'Moderate': 0.394299, 'On Time': 0.742662, 'Severe': 0.151811}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[21104, 11352, 14386, 2861], [9717, 19103, 4284, 4399], [52614, 27881, 148131, 3443], [371, 1057, 49, 1090]]}}` |

## occupancy_forecast

| algorithm | validation | test / silhouette |
|---|---|---|
| random_forest | `{'mae': 0.12196, 'rmse': 0.176802, 'r2': 0.693595, 'mape_nonzero_pct': 62.165297, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.'}` | `{'mae': 0.118569, 'rmse': 0.1736, 'r2': 0.71533, 'mape_nonzero_pct': 55.455061, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.'}` |
| ridge | `{'mae': 0.142596, 'rmse': 0.200768, 'r2': 0.604898, 'mape_nonzero_pct': 80.865902, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.'}` | `{'mae': 0.134698, 'rmse': 0.192594, 'r2': 0.649628, 'mape_nonzero_pct': 70.064597, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.'}` |
| random_forest | `{'mae': 0.12196, 'rmse': 0.176802, 'r2': 0.693595, 'mape_nonzero_pct': 62.165297, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.'}` | `{'mae': 0.118569, 'rmse': 0.1736, 'r2': 0.71533, 'mape_nonzero_pct': 55.455061, 'mape_note': 'MAPE is calculated only for occupancy above 1%; zero occupancy makes ordinary MAPE undefined.'}` |

## route_clustering

| algorithm | validation | test / silhouette |
|---|---|---|
| agglomerative_k3 | `{}` | `0.284578` |
| agglomerative_k4 | `{}` | `0.28858` |
| agglomerative_k5 | `{}` | `0.324122` |
| dbscan_eps0.6 | `{}` | `-0.224531` |
| dbscan_eps0.8 | `{}` | `-0.103846` |
| dbscan_eps1.0 | `{}` | `-0.134714` |
| kmeans_k3 | `{}` | `0.310648` |
| kmeans_k4 | `{}` | `0.31911` |
| kmeans_k5 | `{}` | `0.317363` |

## stop_period_demand

| algorithm | validation | test / silhouette |
|---|---|---|
| random_forest | `{'mae': 0.960824, 'rmse': 1.641187, 'r2': 0.843946, 'mape_nonzero_pct': 47.892583, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` | `{'mae': 1.021776, 'rmse': 1.804427, 'r2': 0.844115, 'mape_nonzero_pct': 49.173845, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` |
| ridge | `{'mae': 1.064268, 'rmse': 1.814392, 'r2': 0.809269, 'mape_nonzero_pct': 53.414187, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` | `{'mae': 1.134617, 'rmse': 2.003881, 'r2': 0.807749, 'mape_nonzero_pct': 55.154153, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` |
| random_forest | `{'mae': 0.960824, 'rmse': 1.641187, 'r2': 0.843946, 'mape_nonzero_pct': 47.892583, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` | `{'mae': 1.021776, 'rmse': 1.804427, 'r2': 0.844115, 'mape_nonzero_pct': 49.173845, 'mape_note': 'MAPE is calculated only where observed tap-ins are above zero; ordinary MAPE is undefined at zero.'}` |
