# Spark Models Explained

## Metric integrity

The original Task A Logistic Regression and Random Forest artifacts report **weighted F1**, not macro F1. Their JSON keys have been corrected to `weighted_f1`. True macro F1 is the unweighted mean of each class's F1 score and is recorded explicitly for the later sampled Task A tree models and Task B models.

The final WSL/HDFS recoveries use the complete chronological training split and choose configurations only on the validation split. Task A's final depth-12 weighted Random Forest achieved 83.41% test accuracy and 0.6950 true macro F1; it is an improvement but does not meet the SRS test target. Task B's enhanced weighted Random Forest achieved 88.32% test accuracy and therefore meets the SRS alternative target, despite 0.7484 true macro F1. Both artifacts include per-class F1 and full confusion-matrix counts.

## Task C baseline

The demand baseline is a strict-prior trailing mean over at most 28 preceding route-days. It never uses the current day. On the test split it has MAE 430.03 and RMSE 800.95. The Random Forest forecast improves these to MAE 217.07 and RMSE 476.84.

## Task D cluster profiles

K-Means k=4 is selected with silhouette 0.514. Its profiles are based on the Phase 4 route features, rather than renamed dashboard aliases:

| cluster | routes | label | distinguishing means |
|---|---:|---|---|
| 0 | 32 | Low-occupancy delay-prone mid-demand routes | load .30; delay 3.67 min; punctuality .56 |
| 1 | 60 | Low-demand reliable routes | 951 daily boardings; delay 1.27 min; punctuality .72 |
| 2 | 20 | High-demand high-crowding routes | load .73; 3,366 daily boardings; crowding .35 |
| 3 | 4 | Very-high-demand unreliable trunk routes | 14,705 daily boardings; 100 boardings/trip; delay 8.39 min; punctuality .46 |
