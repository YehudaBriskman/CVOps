FROM python:3.9-slim
RUN pip install --no-cache-dir ultralytics pillow numpy
COPY main.py /opt/nuclio/main.py
ENV MODEL_PATH=/opt/nuclio/model.pt
