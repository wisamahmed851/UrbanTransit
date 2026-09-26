# Phase 6 Class Distribution

Computed from `colab_export/features/trip_features` on 2026-09-26.

## Task A — delay severity

| split | On Time | Minor | Moderate | Severe |
|---|---:|---:|---:|---:|
| train | 1,050,527 | 196,040 | 148,202 | 16,757 |
| validation | 264,169 | 45,870 | 27,401 | 2,703 |
| test | 231,868 | 49,665 | 37,427 | 2,558 |

On Time is 74.4% of the training labels; Severe is only 1.2%. Macro F1 is therefore the appropriate primary measure.

## Task B — crowding flag

| split | False | True | positive rate |
|---|---:|---:|---:|
| train | 1,183,244 | 131,527 | 10.0% |
| validation | 291,313 | 25,366 | 8.0% |
| test | 274,148 | 25,356 | 8.5% |

Crowding is a minority class in every split; any probability threshold is selected on validation only.
