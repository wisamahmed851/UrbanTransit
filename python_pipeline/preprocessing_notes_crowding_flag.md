# Task B preprocessing notes

Read directly with pandas/PyArrow from staged clean raw tables. `crowding_flag` is independently derived as `max_load / capacity_total > 0.90` only where both values exist. `occupancy_pct`, `max_load`, capacity-derived ratios, and same-trip boardings are deliberately excluded from the feature vector because they would disclose the target.

Features are scheduled calendar/planning fields, route/vehicle/direction/type fields, and a strictly prior 28-trip route-direction crowding rate. Numeric NULLs use median imputation; categoricals use most-frequent imputation and ordinal encoding. Validation searches thresholds .15 through .70 for maximum macro F1; the chosen threshold is applied unchanged to test.
