import subprocess
subprocess.run(["python", "python_pipeline/phase7_python_models.py", "--task", "all", "--enhanced-delay", "--full-train"], check=True)
subprocess.run(["python", "database/evaluate_saved_models.py"], check=True)
subprocess.run(["python", "database/load_model_outputs.py"], check=True)
