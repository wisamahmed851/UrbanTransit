# Dual-Pipeline Comparison Report

Generated 2026-09-28 by `python_pipeline/phase8_comparison.py`. Every figure below is read from a saved metrics JSON or computed from the compared cases.

- **Python model:** the one `config/serving.yaml` serves.
- **Spark model:** the saved, leakage-free MLlib model with the best validation score (test scores never choose a model).
- **Cases:** dates inside both pipelines' test splits, so neither pipeline trained on them or used them to choose a model.
- **Regression agreement:** predictions within 10% of each other; a prediction is correct when it is within 10% of the actual value.

## Per-task summary

| Task | Cases | Spark model | Python model | Spark score (cases) | Python score (cases) | Spark full test | Python full test | Agreement | Both correct | Spark only | Python only | Both wrong |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Task A (delay severity) | 0 | none eligible | xgboost v1 | - | - | - | 0.4126 | - | - | - | - | - |
| Task B (crowding risk) | 500 | gbt_sample | xgboost v1 | acc 0.856 / F1 0.711 | acc 0.890 / F1 0.721 | F1 0.687 | F1 0.749 | 89.0% | 81.8% | 3.8% | 7.2% | 7.2% |
| Task C (daily route demand) | 497 | random_forest | random_forest v1 | MAE 237.69 | MAE 203.01 | MAE 217.07 | MAE 195.30 | 58.6% | 40.0% | 11.3% | 10.1% | 38.6% |

## Task A (delay severity)

- **Python inputs:** `hour`, `day_of_week`, `weekend`, `distance_km`, `planned_runtime_min`, `headway_min`, `scheduled_runtime_min`, `prior_route_delay_mean`, `prior_route_hour_delay_mean`, `prior_route_hour_severe_rate`, `route_id`, `vehicle_id`, `direction`, `route_type`, `vehicle_type`
- **Not compared:** no saved Spark model qualifies. Candidates rejected:
  - `decision_tree_sample`: input includes occupancy_pct, which is known only after the trip has run
  - `gbt_one_vs_rest_sample`: input includes occupancy_pct, which is known only after the trip has run
  - `logistic_regression`: input includes occupancy_pct, which is known only after the trip has run
  - `random_forest`: input includes occupancy_pct, which is known only after the trip has run
  - `random_forest_full_weighted`: saved model folder is missing or empty on this machine
  - `random_forest_full_weighted_enhanced_v2`: input includes occupancy_pct, which is known only after the trip has run
  - `random_forest_full_weighted_enhanced_v3_sqrt_weights`: input includes occupancy_pct, which is known only after the trip has run
  - `random_forest_full_weighted_enhanced_v4_depth12`: input includes occupancy_pct, which is known only after the trip has run
  - `xgboost_gpu`: saved model folder is missing or empty on this machine

## Task B (crowding risk)

- **Python inputs:** `hour`, `day_of_week`, `weekend`, `distance_km`, `planned_runtime_min`, `headway_min`, `scheduled_runtime_min`, `prior_route_crowding_rate`, `route_id`, `vehicle_id`, `direction`, `route_type`, `vehicle_type`
- **Spark inputs:** not recorded in its metrics JSON
- **Case window:** 2026-07-08 to 2026-08-31
- **Spark training scope (from its JSON):** stratified 10% train/validation sample; full held-out test
- **Spark candidates not used:** `random_forest_full_weighted` (saved model folder is missing or empty on this machine); `random_forest_full_weighted_enhanced_v2` (saved model folder is missing or empty on this machine)

Examples of disagreement:

```csv
case_id,actual,spark_prediction,python_prediction
T2607070161,1.0,1.0,0.0
T2607078777,1.0,1.0,0.0
T2608101943,0.0,1.0,0.0
T2608015337,0.0,1.0,0.0
T2608138308,0.0,1.0,0.0
```

## Task C (daily route demand)

- **Python inputs:** `lag_1`, `lag_7`, `lag_28`, `rolling_7_mean`, `rolling_28_mean`
- **Spark inputs:** not recorded in its metrics JSON
- **Case window:** 2026-07-08 to 2026-08-31

Cases with the largest difference:

```csv
case_id,actual,spark_value,python_value,absolute_difference
R001_2026-07-31,10063.0,12622.884,9039.184,3583.701
R001_2026-07-15,11278.0,13961.97,10700.663,3261.306
R001_2026-08-07,11983.0,13508.324,10280.09,3228.234
R118_2026-08-03,292.0,2964.375,197.181,2767.193
R118_2026-08-13,285.0,2989.545,302.463,2687.082
```

## Task D (route clustering)

- **Spark:** kmeans_k4, silhouette 0.514
- **Python:** agglomerative_k5, silhouette 0.313
- **Agreement (adjusted Rand index over 116 routes):** 0.583 (1 = identical grouping, 0 = no better than chance)

```
Python cluster   0   1   2  3  4
Spark cluster                   
0                5   0  27  0  0
1               10  46   3  1  0
2               20   0   0  0  0
3                0   0   0  0  4
```

## Overall

- **Case-weighted agreement over 997 cases (Task B (crowding risk), Task C (daily route demand)):** 73.8%
