#!/bin/bash
set -e

PROCESSOR_BASE="cvat/nuclio-processor-base:latest"
BASE_IMAGE="cvat/yolo-base:latest"

if ! docker image inspect "$BASE_IMAGE" > /dev/null 2>&1; then
    echo "[bootstrap] First-time setup: building Nuclio base image..."

    nuctl create project cvat --platform local 2>/dev/null || true

    # Build a minimal Nuclio processor image (generic, not model-specific)
    nuctl deploy \
        --project-name cvat \
        --path /bootstrap \
        --file /bootstrap/function.yaml \
        --platform local \
        --env "CVAT_FUNCTIONS_REDIS_HOST=${CVAT_FUNCTIONS_REDIS_HOST:-cvat_redis_ondisk}" \
        --env "CVAT_FUNCTIONS_REDIS_PORT=${CVAT_FUNCTIONS_REDIS_PORT:-6666}" \
        --platform-config '{"attributes": {"network": "cvat_cvat"}}' 2>&1 || true

    echo "[bootstrap] Adding Python packages to base image..."
    TMPDIR=$(mktemp -d)
    cp /bootstrap/main.py "$TMPDIR/main.py"
    cat > "$TMPDIR/Dockerfile" << 'EOF'
FROM cvat/nuclio-processor-base:latest
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir ultralytics Pillow numpy
COPY main.py /opt/nuclio/main.py
EOF
    docker build -t "$BASE_IMAGE" "$TMPDIR"
    rm -rf "$TMPDIR"

    echo "[bootstrap] Base image ready: $BASE_IMAGE"
fi

exec uvicorn app:app --host 0.0.0.0 --port 8001
