# Build context is the REPO ROOT (see manifests/docker-compose.override.yml):
# cvops-cvat-client is a sibling package in this monorepo, not on PyPI.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y curl libxcb1 libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz \
    | tar -xz --strip-components=1 -C /usr/local/bin/ docker/docker

RUN curl -fsSL \
    "https://github.com/nuclio/nuclio/releases/download/1.15.9/nuctl-1.15.9-linux-amd64" \
    -o /usr/local/bin/nuctl && chmod +x /usr/local/bin/nuctl

WORKDIR /app

# Shared CVAT client (pulls cvat-sdk). Installed before the app so the layer
# caches independently of app changes.
COPY packages/cvat-client ./packages/cvat-client
RUN pip install --no-cache-dir ./packages/cvat-client

COPY services/model-deployer/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/model-deployer/ ./
RUN chmod +x entrypoint.sh
COPY services/model-deployer/bootstrap/ /bootstrap/

CMD ["./entrypoint.sh"]
