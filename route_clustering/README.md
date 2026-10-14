# route_clustering/

SRS step 21 (route clustering). This folder is a pointer to the code:

| What | Where |
|---|---|
| Python clustering (K-Means, DBSCAN, Agglomerative; Agglomerative k=5 served) | `python_pipeline/phase7_python_models.py`, notes in `python_pipeline/preprocessing_notes_route_clustering.md` |
| Spark MLlib K-Means (k=4) | `spark_jobs/phase6_colab_tasks_cd.py`, `spark_jobs/phase6_taskD_wsl_demo.py` |
| Saved models and silhouette scores | `models/python/route_clustering/`, `models/spark/route_clustering/` |
| Spark vs Python agreement (adjusted Rand index) | `reports/dual_pipeline_comparison_report.md`, Task D |
| Dashboard | Model results page (route group tables) |
