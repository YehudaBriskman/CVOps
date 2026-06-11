#!/usr/bin/env bash
# start_env.sh — bring up the full CVOps + CVAT + YOLO12n environment
# Run once after every machine restart.
#
# Usage:
#   bash scripts/start_env.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FUNC_YAML="$REPO_DIR/services/cvat/serverless/pytorch/ultralytics/yolo12/nuclio/function.yaml"
NUCTL_VERSION="1.15.9"
NUCTL_URL="https://github.com/nuclio/nuclio/releases/download/${NUCTL_VERSION}/nuctl-${NUCTL_VERSION}-linux-amd64"
SERVERLESS_IMAGE="cvat/yolo12n-serverless:latest"
FUNC_NAME="pth-ultralytics-yolo12n"
CVAT_URL="http://localhost:8080"

ok()   { echo "[✓] $*"; }
info() { echo "[*] $*"; }
fail() { echo "[!] $*" >&2; exit 1; }

wait_healthy() {
    local name=$1 seconds=${2:-60}
    info "Waiting for $name (up to ${seconds}s)..."
    for i in $(seq 1 $seconds); do
        if docker inspect --format '{{.State.Health.Status}}' "$name" 2>/dev/null | grep -q "healthy"; then
            ok "$name is healthy"; return 0
        fi
        if docker inspect --format '{{.State.Status}}' "$name" 2>/dev/null | grep -q "running"; then
            if ! docker inspect --format '{{.State.Health}}' "$name" 2>/dev/null | grep -q "Status"; then
                ok "$name is running (no healthcheck)"; return 0
            fi
        fi
        sleep 2
    done
    fail "$name did not become healthy in ${seconds}s"
}

# ── step 1: submodule ─────────────────────────────────────────────────────────
info "Ensuring submodules are initialised..."
git -C "$REPO_DIR" submodule update --init --recursive
ok "Submodules ready"

# ── step 2: docker compose up ─────────────────────────────────────────────────
info "Starting full stack (CVOps + CVAT + Nuclio)..."
docker compose -f "$REPO_DIR/docker-compose.yml" \
               -f "$REPO_DIR/docker-compose.override.yml" \
               --project-directory "$REPO_DIR" \
               up -d 2>&1 | tail -5

wait_healthy "cvat_server" 120
wait_healthy "nuclio" 60
ok "Stack is up"

# ── step 3: nuctl ─────────────────────────────────────────────────────────────
NUCTL="$REPO_DIR/services/model-deployer/nuctl"
if [[ ! -x "$NUCTL" ]]; then
    info "Downloading nuctl ${NUCTL_VERSION}..."
    curl -fsSL "$NUCTL_URL" -o "$NUCTL"
    chmod +x "$NUCTL"
    ok "nuctl downloaded to services/model-deployer/nuctl"
else
    ok "nuctl already present"
fi

# ── step 4: serverless image ──────────────────────────────────────────────────
if ! docker image inspect "$SERVERLESS_IMAGE" > /dev/null 2>&1; then
    info "Building YOLO12n serverless image..."

    "$NUCTL" create project cvat --platform local 2>/dev/null || true
    "$NUCTL" deploy --project-name cvat \
        --path "$(dirname "$FUNC_YAML")" \
        --file "$FUNC_YAML" \
        --platform local \
        --env CVAT_FUNCTIONS_REDIS_HOST=cvat_redis_ondisk \
        --env CVAT_FUNCTIONS_REDIS_PORT=6666 \
        --platform-config '{"attributes": {"network": "cvat_cvat"}}' 2>&1 | tail -5 || true

    docker build -t "$SERVERLESS_IMAGE" - << 'DOCKERFILE'
FROM nuclio/processor-pth-ultralytics-yolo12n:latest
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir ultralytics Pillow numpy
DOCKERFILE
    ok "Image $SERVERLESS_IMAGE built"
else
    ok "Image $SERVERLESS_IMAGE already exists"
fi

# ── step 5: deploy YOLO12n function ──────────────────────────────────────────
RUNNING=$(docker ps --filter "name=nuclio-nuclio-${FUNC_NAME}" --filter "status=running" -q)
if [[ -z "$RUNNING" ]]; then
    info "Deploying YOLO12n to Nuclio..."
    "$NUCTL" create project cvat --platform local 2>/dev/null || true
    "$NUCTL" deploy "$FUNC_NAME" \
        --project-name cvat \
        --platform local \
        --run-image "$SERVERLESS_IMAGE" \
        --file "$FUNC_YAML" \
        --env CVAT_FUNCTIONS_REDIS_HOST=cvat_redis_ondisk \
        --env CVAT_FUNCTIONS_REDIS_PORT=6666 \
        --platform-config '{"attributes": {"network": "cvat_cvat"}}'
    ok "YOLO12n deployed"
else
    ok "YOLO12n already running"
fi

# ── done ──────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════"
echo "  Environment ready."
echo "  CVAT:     $CVAT_URL"
echo "  CVOps API: http://localhost:8000"
echo "════════════════════════════════════════════"
