"""
Model Deployer Service (internal)
----------------------------------
POST /deploy    — receive .pt file, deploy to CVAT via Nuclio
GET  /models    — list models available in CVAT
POST /annotate  — upload images to CVAT + trigger auto-annotation
GET  /health
"""

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from cvat_client import annotate, list_models
from deployer import deploy

app = FastAPI(title="Model Deployer", docs_url="/docs")


class AnnotateRequest(BaseModel):
    task_name: str
    function_id: str
    threshold: float = 0.3


@app.post("/deploy")
async def deploy_model(
    model_name: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    if not file.filename.endswith(".pt"):
        raise HTTPException(400, "Only .pt files are supported")

    with tempfile.TemporaryDirectory() as tmp:
        pt_path = Path(tmp) / file.filename
        pt_path.write_bytes(await file.read())
        try:
            func_name = deploy(pt_path, model_name)
        except Exception as e:
            raise HTTPException(500, str(e))

    return {"status": "ok", "function_name": func_name, "model_name": model_name}


@app.get("/models")
def get_models() -> list[dict]:
    try:
        return list_models()
    except Exception as e:
        raise HTTPException(502, f"Could not reach CVAT: {e}")


@app.post("/annotate")
async def annotate_task(
    body: AnnotateRequest,
    files: list[UploadFile] = File(...),
) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        image_paths = []
        for f in files:
            dest = tmp_path / f.filename
            dest.write_bytes(await f.read())
            image_paths.append(dest)

        try:
            result = annotate(
                task_name=body.task_name,
                function_id=body.function_id,
                image_paths=image_paths,
                threshold=body.threshold,
            )
        except Exception as e:
            raise HTTPException(500, str(e))

    return result


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
