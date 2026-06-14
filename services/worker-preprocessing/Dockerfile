# Build context is the REPO ROOT (see manifests/docker-compose.yml) because
# cvops-api and cvops-steps are sibling packages in this monorepo, not on PyPI.
FROM python:3.12-slim
WORKDIR /app

# ffmpeg is required by the extract_frames step's decode path.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir hatchling

# Install the three packages editable, deps first so layers cache well. Each
# needs its src/ present at install time (hatchling scans for packages).
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/api/src/ services/api/src/
RUN pip install --no-cache-dir -e services/api

COPY packages/steps/pyproject.toml packages/steps/pyproject.toml
COPY packages/steps/src/ packages/steps/src/
RUN pip install --no-cache-dir -e packages/steps

COPY services/worker-preprocessing/pyproject.toml services/worker-preprocessing/pyproject.toml
COPY services/worker-preprocessing/src/ services/worker-preprocessing/src/
RUN pip install --no-cache-dir -e services/worker-preprocessing

ENV PYTHONUNBUFFERED=1

RUN groupadd --system --gid 1001 app && \
    useradd  --system --uid 1001 --gid app --home /app --shell /usr/sbin/nologin app && \
    chown -R 1001:1001 /app
USER 1001:1001

ENTRYPOINT ["python", "-m", "cvops_worker"]
