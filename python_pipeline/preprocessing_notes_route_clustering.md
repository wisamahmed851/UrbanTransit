# Task D preprocessing notes

Route profiles are independently recomputed from clean raw trips, delays, vehicle capacity, and passenger counts for the training dates only. The eight scaled inputs are average occupancy, average delay minutes, reliability share (<5-minute delay), trip frequency, peak-demand ratio, load factor, average actual travel time, and 28-day demand momentum growth. Numeric NULLs use median imputation; `StandardScaler` is fitted before every clustering algorithm.
