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
| logistic_regression | `{'accuracy': 0.597163, 'macro_f1': 0.357212, 'per_class_f1': {'Minor': 0.243859, 'Moderate': 0.312721, 'On Time': 0.763814, 'Severe': 0.108454}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[14246, 10751, 15487, 5414], [5034, 12271, 3632, 6525], [51324, 27355, 175350, 10344], [336, 640, 301, 1433]]}}` | `{'accuracy': 0.534054, 'macro_f1': 0.337444, 'per_class_f1': {'Minor': 0.245362, 'Moderate': 0.320331, 'On Time': 0.713664, 'Severe': 0.070418}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[15315, 11137, 15831, 7420], [7878, 14568, 5755, 9302], [51547, 26923, 140828, 12771], [393, 825, 179, 1170]]}}` |
| random_forest | `{'accuracy': 0.632388, 'macro_f1': 0.392633, 'per_class_f1': {'Minor': 0.280355, 'Moderate': 0.345612, 'On Time': 0.789086, 'Severe': 0.155478}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[16023, 11100, 14977, 3798], [5552, 14050, 2256, 5604], [46528, 28095, 183687, 6063], [304, 598, 276, 1532]]}}` | `{'accuracy': 0.574757, 'macro_f1': 0.373099, 'per_class_f1': {'Minor': 0.276494, 'Moderate': 0.361749, 'On Time': 0.742485, 'Severe': 0.111668}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[17135, 12335, 15732, 4501], [8876, 17636, 4581, 6410], [47835, 29078, 149052, 6104], [396, 952, 61, 1158]]}}` |
| xgboost | `{'accuracy': 0.63811, 'macro_f1': 0.406059, 'per_class_f1': {'Minor': 0.315751, 'Moderate': 0.365046, 'On Time': 0.787171, 'Severe': 0.156269}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[19602, 8931, 14027, 3338], [6575, 14055, 2177, 4655], [51678, 25831, 182288, 4576], [408, 725, 282, 1295]]}}` | `{'accuracy': 0.575702, 'macro_f1': 0.381782, 'per_class_f1': {'Minor': 0.315292, 'Moderate': 0.368599, 'On Time': 0.732724, 'Severe': 0.110512}, 'confusion_matrix': {'labels': ['Minor', 'Moderate', 'On Time', 'Severe'], 'values': [[20931, 10975, 14508, 3289], [10486, 18312, 4497, 4208], [51155, 31398, 145201, 4315], [497, 1172, 57, 841]]}}` |

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
