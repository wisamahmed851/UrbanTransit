import subprocess
import sys
tasks = ["b", "c", "e", "f"]
for t in tasks:
    print(f"Running {t}...")
    subprocess.run([sys.executable, "python_pipeline/phase7_python_models.py", "--task", t, "--full-train"], check=False)
print("Evaluating...")
subprocess.run([sys.executable, "database/evaluate_saved_models.py"], check=False)
print("Loading...")
subprocess.run([sys.executable, "database/load_model_outputs.py"], check=False)
