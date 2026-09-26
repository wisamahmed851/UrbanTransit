# Python Model Metrics

Independent Phase 7 pandas/PyArrow pipeline. Chronological split: train 2025-09-01..2026-05-01; validation 2026-05-02..2026-07-01; test 2026-07-02..2026-08-31.

## crowding_flag

| algorithm | validation | test / silhouette |
|---|---|---|
| logistic_regression | `{'accuracy': 0.874649, 'macro_f1': 0.665427, 'per_class_f1': {'0.0': 0.930002, '1.0': 0.400851}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[263704, 27609], [12087, 13279]]}}` | `{'accuracy': 0.866499, 'macro_f1': 0.664681, 'per_class_f1': {'0.0': 0.924822, '1.0': 0.404539}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[245938, 28210], [11774, 13582]]}}` |
| random_forest | `{'accuracy': 0.907, 'macro_f1': 0.750534, 'per_class_f1': {'0.0': 0.948102, '1.0': 0.552967}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[269013, 22300], [7151, 18215]]}}` | `{'accuracy': 0.899811, 'macro_f1': 0.74583, 'per_class_f1': {'0.0': 0.943662, '1.0': 0.547999}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[251307, 22841], [7166, 18190]]}}` |
| xgboost | `{'accuracy': 0.913414, 'macro_f1': 0.774686, 'per_class_f1': {'0.0': 0.951483, '1.0': 0.597888}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[268874, 22439], [4981, 20385]]}}` | `{'accuracy': 0.902195, 'macro_f1': 0.760896, 'per_class_f1': {'0.0': 0.944703, '1.0': 0.577088}, 'confusion_matrix': {'labels': ['0.0', '1.0'], 'values': [[250225, 23923], [5370, 19986]]}}` |

## daily_boardings

| algorithm | validation | test / silhouette |
|---|---|---|
| baseline_28day | `{'mae': 479.551826, 'rmse': 937.410494, 'mape': 46.303891, 'r2': 0.836657}` | `{'mae': 399.95635, 'rmse': 733.671496, 'mape': 33.184021, 'r2': 0.88012}` |
| random_forest | `{'mae': 273.913689, 'rmse': 670.717864, 'mape': 29.584053, 'r2': 0.916378}` | `{'mae': 193.367119, 'rmse': 422.417388, 'mape': 14.677831, 'r2': 0.96026}` |
| ridge | `{'mae': 302.161443, 'rmse': 709.078454, 'mape': 30.499825, 'r2': 0.906539}` | `{'mae': 216.122834, 'rmse': 452.048268, 'mape': 16.784818, 'r2': 0.95449}` |
| xgboost | `{'mae': 278.440063, 'rmse': 683.069634, 'mape': 29.302683, 'r2': 0.91327}` | `{'mae': 201.81076, 'rmse': 455.224412, 'mape': 15.499973, 'r2': 0.953848}` |

## delay_severity

| algorithm | validation | test / silhouette |
|---|---|---|
| logistic_regression | `{'accuracy': 0.585951, 'macro_f1': 0.354211, 'per_class_f1': {'Minor': 0.236476, 'Moderate': 0.311423, 'On Time': 0.754296, 'Severe': 0.114649}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[13499, 12708, 14589, 5102], [4495, 13858, 2653, 6456], [49953, 34291, 170684, 9445], [323, 679, 266, 1442]]}}` | `{'accuracy': 0.529446, 'macro_f1': 0.336315, 'per_class_f1': {'Minor': 0.241536, 'Moderate': 0.31854, 'On Time': 0.709334, 'Severe': 0.075848}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[14736, 12570, 15327, 7070], [7368, 15704, 4919, 9512], [49846, 31977, 138750, 11496], [366, 846, 147, 1208]]}}` |
| random_forest | `{'accuracy': 0.632388, 'macro_f1': 0.392633, 'per_class_f1': {'Minor': 0.280355, 'Moderate': 0.345612, 'On Time': 0.789086, 'Severe': 0.155478}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[16023, 11100, 14977, 3798], [5552, 14050, 2256, 5604], [46528, 28095, 183687, 6063], [304, 598, 276, 1532]]}}` | `{'accuracy': 0.574757, 'macro_f1': 0.373099, 'per_class_f1': {'Minor': 0.276494, 'Moderate': 0.361749, 'On Time': 0.742485, 'Severe': 0.111668}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[17135, 12335, 15732, 4501], [8876, 17636, 4581, 6410], [47835, 29078, 149052, 6104], [396, 952, 61, 1158]]}}` |
| xgboost | `{'accuracy': 0.637123, 'macro_f1': 0.405989, 'per_class_f1': {'Minor': 0.316241, 'Moderate': 0.364673, 'On Time': 0.786158, 'Severe': 0.156884}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[19695, 8908, 13951, 3344], [6591, 14070, 2148, 4653], [51981, 25998, 181840, 4554], [392, 727, 292, 1299]]}}` | `{'accuracy': 0.575186, 'macro_f1': 0.382491, 'per_class_f1': {'Minor': 0.316029, 'Moderate': 0.368355, 'On Time': 0.731923, 'Severe': 0.113659}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[21002, 11082, 14395, 3224], [10441, 18394, 4468, 4200], [51278, 31724, 144868, 4199], [488, 1168, 56, 855]]}}` |

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
