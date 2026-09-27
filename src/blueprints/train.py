import subprocess
import threading
import sys
from pathlib import Path

from flask import Blueprint, jsonify, request

from src.security import permission_required

bp = Blueprint("train", __name__, url_prefix="/api/train")
ROOT = Path(__file__).resolve().parent.parent.parent

def run_tracked(name, log_path, cmd):
    log_file = ROOT / log_path
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    start_cmd = [sys.executable, "database/job_monitor.py", "start", "--name", name, "--log", str(log_path)]
    try:
        job_id = subprocess.check_output(start_cmd, cwd=str(ROOT), text=True).strip()
    except subprocess.CalledProcessError as e:
        print(f"Failed to start job {name}: {e}")
        return False
        
    with open(log_file, "w") as f:
        process = subprocess.run(cmd, cwd=str(ROOT), stdout=f, stderr=subprocess.STDOUT)
    
    status = "success" if process.returncode == 0 else "failed"
    subprocess.run([sys.executable, "database/job_monitor.py", "finish", "--id", job_id, "--status", status], cwd=str(ROOT))
    
    return process.returncode == 0

def _run_training(pipeline: str):
    subprocess.run(["bash", "hdfs_scripts/start_hdfs.sh"], cwd=str(ROOT))
    
    if pipeline in ("spark", "all"):
        run_tracked("spark_models", "reports/processing_logs/spark.log", [sys.executable, "spark_jobs/phase6_spark_models.py"])
    if pipeline in ("python", "all"):
        run_tracked("python_models", "reports/processing_logs/python.log", [sys.executable, "python_pipeline/phase7_python_models.py", "--task", "all", "--enhanced-delay", "--full-train"])
        
    run_tracked("evaluate_saved_models", "reports/processing_logs/evaluate.log", [sys.executable, "database/evaluate_saved_models.py"])
    run_tracked("load_model_outputs", "reports/processing_logs/load_model.log", [sys.executable, "database/load_model_outputs.py"])

@bp.post("")
@permission_required("models:read")
def train_models():
    data = request.get_json() or {}
    pipeline = data.get("pipeline", "all")
    threading.Thread(target=_run_training, args=(pipeline,), name="train-models", daemon=True).start()
    return jsonify(message=f"Training '{pipeline}' started in the background."), 202
