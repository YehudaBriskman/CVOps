import base64
import io
import json
import os

import numpy as np
from PIL import Image
from ultralytics import YOLO

MODEL_PATH = os.environ.get("MODEL_PATH", "/opt/nuclio/model.pt")
model = None


def init_context(context):
    global model
    context.logger.info(f"Loading model from {MODEL_PATH}")
    model = YOLO(MODEL_PATH)
    context.logger.info(f"Model loaded: {len(model.names)} classes")


def handler(context, event):
    data = event.body
    buf = io.BytesIO(base64.b64decode(data["image"]))
    image = np.array(Image.open(buf).convert("RGB"))
    threshold = float(data.get("threshold", 0.5))

    results = model(image, conf=threshold, verbose=False)[0]

    detections = []
    for box in results.boxes:
        xyxy = box.xyxy[0].tolist()
        detections.append({
            "confidence": float(box.conf[0]),
            "label": model.names[int(box.cls[0])],
            "points": [xyxy[0], xyxy[1], xyxy[2], xyxy[3]],
            "type": "rectangle",
        })

    return context.Response(
        body=json.dumps(detections),
        headers={},
        content_type="application/json",
        status_code=200,
    )
