# Task C preprocessing notes

Clean `trips` are joined to clean `passenger_counts` in pandas and aggregated independently to measured route-day boardings. Features are `lag_1`, `lag_7`, `lag_28`, `rolling_7_mean`, and `rolling_28_mean`. Every lag is computed with `groupby(...).shift()` before rolling, so no row uses its own or future boardings. Missing lag values are median-imputed for learned models. The baseline is the strict-prior `rolling_28_mean`.
