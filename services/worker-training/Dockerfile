FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY packages/worker-common ./packages/worker-common
COPY services/api ./services/api
RUN pip install --no-cache-dir ./packages/worker-common ./services/api

COPY services/worker-training ./services/worker-training
RUN pip install --no-cache-dir ./services/worker-training

CMD ["python", "-m", "worker_training.main"]
