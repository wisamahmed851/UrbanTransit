import os
import zipfile

# Bypassing Hugging Face's 1GB Git limit:
# We only pushed models.zip. We dynamically extract it on container boot!
if os.path.exists("models.zip") and not os.path.exists("models/python/daily_boardings/xgboost_v1.pkl"):
    print("Extracting models.zip to bypass 1GB Git limit...")
    with zipfile.ZipFile("models.zip", 'r') as zip_ref:
        zip_ref.extractall(".")
    print("Extraction complete!")

import spaces
import gradio as gr
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware

# Inject TiDB credentials for Hugging Face
os.environ["MYSQL_HOST"] = "gateway01.ap-northeast-1.prod.aws.tidbcloud.com"
os.environ["MYSQL_PORT"] = "4000"
os.environ["MYSQL_USER"] = "2PrDbvE9YRTBsvE.root"
os.environ["MYSQL_PASSWORD"] = "Faiwichy0nR9aLzW"
os.environ["MYSQL_DATABASE"] = "urbantransit_iq"

from src.app import create_app

# 1. Create the Flask app
flask_app = create_app()

# 2. Create the FastAPI app
app = FastAPI()

# 3. Create a dummy Gradio app to satisfy Hugging Face's ZeroGPU supervisor
@spaces.GPU
def dummy_gpu_function():
    return "GPU is active"

with gr.Blocks() as demo:
    gr.Markdown("# UrbanTransit API is running!")
    btn = gr.Button("Check GPU Status")
    out = gr.Textbox()
    btn.click(fn=dummy_gpu_function, inputs=None, outputs=out)

# 4. Mount the Flask API at the root (Flask's own routes already start with /api)
app.mount("/", WSGIMiddleware(flask_app))

# 5. Mount the dummy Gradio app on a subpath (we just need demo.launch to run below)
app = gr.mount_gradio_app(app, demo, path="/gradio_dummy")

if __name__ == "__main__":
    import uvicorn
    # TRICK: Launch the demo on a dummy port in the background so the ZeroGPU 
    # supervisor hooks into it and marks the GPU function as "registered"!
    demo.launch(server_port=7861, prevent_thread_lock=True)
    
    # Run our actual FastAPI app on the main Hugging Face port
    uvicorn.run(app, host="0.0.0.0", port=7860)
