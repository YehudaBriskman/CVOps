# Build context is the REPO ROOT (see manifests/docker-compose.yml): the cvops
# packages are siblings in this monorepo, not on PyPI.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/api ./services/api
COPY packages/worker-common ./packages/worker-common
COPY packages/cvat-client ./packages/cvat-client
COPY packages/steps ./packages/steps
RUN pip install --no-cache-dir \
    ./services/api ./packages/worker-common ./packages/cvat-client ./packages/steps

COPY services/worker-cvat ./services/worker-cvat
RUN pip install --no-cache-dir ./services/worker-cvat

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "worker_cvat.main"]
