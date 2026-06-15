# Build context is the REPO ROOT (same as worker-preprocessing) because
# cvops-api is a sibling package in this monorepo, not on PyPI.
FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates libxcb1 libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# nuctl — deploys Nuclio functions into CVAT
RUN curl -fsSL \
    "https://github.com/nuclio/nuclio/releases/download/1.15.9/nuctl-1.15.9-linux-amd64" \
    -o /usr/local/bin/nuctl && chmod +x /usr/local/bin/nuctl

# Docker CLI — needed by nuctl for container operations
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz \
    | tar -xz --strip-components=1 -C /usr/local/bin/ docker/docker

RUN pip install --no-cache-dir hatchling

COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/api/src/ services/api/src/
RUN pip install --no-cache-dir -e services/api

COPY services/worker-cvat/pyproject.toml services/worker-cvat/pyproject.toml
COPY services/worker-cvat/src/ services/worker-cvat/src/
RUN pip install --no-cache-dir -e services/worker-cvat

ENV PYTHONUNBUFFERED=1

RUN groupadd --system --gid 1001 app && \
    useradd  --system --uid 1001 --gid app --home /app --shell /usr/sbin/nologin app && \
    chown -R 1001:1001 /app
USER 1001:1001

ENTRYPOINT ["python", "-m", "worker_cvat"]
