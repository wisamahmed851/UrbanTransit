# notebooks/

Reserved for exploratory Jupyter notebooks (SRS repository layout). The exploratory and modelling work for this project was
written as scripts instead, so they can run unattended in WSL and be re-run on hidden data:

- `spark_jobs/profile_data.py`: data profiling
- `spark_sql/analytics/01x_eda_*.sql`: exploratory analysis (SRS step 8)
- `python_pipeline/phase7_python_models.py`: Python modelling
- `spark_jobs/phase6_colab_*.py`: the Colab-run Spark training scripts
