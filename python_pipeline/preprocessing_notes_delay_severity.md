# Task A preprocessing notes

Read directly with pandas/PyArrow from the locally staged Phase 3 clean `trips`, `delays`, `vehicles`, `routes`, `schedules`, and `passenger_counts` Parquet tables. No Spark table or model is read.

`delay_severity` is independently derived from the mean clean delay record per trip: On Time <5, Minor [5,10), Moderate [10,20), Severe >=20; a missing clean exception record is treated as 0 minutes within the documented tolerance. Features are scheduled hour/day/weekend, route/vehicle/direction/route type/vehicle type, distance, planned and scheduled runtime, scheduled headway, and a strictly prior 28-trip route-direction delay mean. Numeric NULLs use median imputation; categoricals use most-frequent imputation plus ordinal encoding. Class balancing is applied to all classifiers.
