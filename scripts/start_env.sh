#!/usr/bin/env bash
# start_env.sh — bring up CVAT + YOLO12n auto-labeling environment
# Run once after every machine restart, then use cvat_autolabel.py normally.
#
# Usage:
#   bash scripts/start_env.sh

set -euo pipefail

# ── paths ────────────────────────────────────────────────────────────────────
CVAT_DIR="/home/natipinyan/Projects/cvat"
FUNC_YAML="$CVAT_DIR/serverless/pytorch/ultralytics/yolo12/nuclio/function.yaml"
NUCTL="/tmp/nuctl"
NUCTL_VERSION="1.15.9"
NUCTL_URL="https://github.com/nuclio/nuclio/releases/download/${NUCTL_VERSION}/nuctl-${NUCTL_VERSION}-linux-amd64"
SERVERLESS_IMAGE="cvat/yolo12n-serverless:latest"
BASE_IMAGE="nuclio/processor-pth-ultralytics-yolo12n:latest"
FUNC_NAME="pth-ultralytics-yolo12n"
CVAT_URL="http://localhost:8080"

# ── helpers ───────────────────────────────────────────────────────────────────
ok()   { echo "[✓] $*"; }
info() { echo "[*] $*"; }
fail() { echo "[!] $*" >&2; exit 1; }

wait_healthy() {
    local name=$1 seconds=${2:-60}
    info "Waiting for $name to be healthy (up to ${seconds}s)..."
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

# ── step 1: docker ────────────────────────────────────────────────────────────
info "Checking Docker..."
docker info > /dev/null 2>&1 || fail "Docker is not running. Start Docker first."
ok "Docker is running"

# ── step 2: start CVAT ────────────────────────────────────────────────────────
info "Starting CVAT..."
docker compose \
    -f "$CVAT_DIR/docker-compose.yml" \
    -f "$CVAT_DIR/components/serverless/docker-compose.serverless.yml" \
    --project-directory "$CVAT_DIR" \
    up -d 2>&1 | tail -5

wait_healthy "cvat_server" 120
wait_healthy "nuclio" 60
ok "CVAT is up"

# ── step 3: nuctl ─────────────────────────────────────────────────────────────
if [[ ! -x "$NUCTL" ]]; then
    info "Downloading nuctl ${NUCTL_VERSION}..."
    curl -fsSL "$NUCTL_URL" -o "$NUCTL"
    chmod +x "$NUCTL"
    ok "nuctl downloaded"
else
    ok "nuctl already present"
fi

# ── step 4: serverless image ──────────────────────────────────────────────────
if ! docker image inspect "$SERVERLESS_IMAGE" > /dev/null 2>&1; then
    info "Image $SERVERLESS_IMAGE not found — building it..."

    # 4a: build base processor image via nuctl (needed once to get the nuclio runtime)
    info "Building base processor image with nuctl..."
    "$NUCTL" create project cvat --platform local 2>/dev/null || true
    "$NUCTL" deploy --project-name cvat \
        --path "$(dirname "$FUNC_YAML")" \
        --file "$FUNC_YAML" \
        --platform local \
        --env CVAT_FUNCTIONS_REDIS_HOST=cvat_redis_ondisk \
        --env CVAT_FUNCTIONS_REDIS_PORT=6666 \
        --platform-config '{"attributes": {"network": "cvat_cvat"}}' 2>&1 | tail -5 || true

    # 4b: add Python packages on top (nuclio's build doesn't include them)
    info "Adding ultralytics/numpy to the processor image..."
    docker build -t "$SERVERLESS_IMAGE" - << 'DOCKERFILE'
FROM nuclio/processor-pth-ultralytics-yolo12n:latest
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir ultralytics Pillow numpy
DOCKERFILE
    ok "Image $SERVERLESS_IMAGE built"
else
    ok "Image $SERVERLESS_IMAGE already exists"
fi

# ── step 5: deploy function ───────────────────────────────────────────────────
RUNNING=$(docker ps --filter "name=nuclio-nuclio-${FUNC_NAME}" --filter "status=running" -q)

if [[ -z "$RUNNING" ]]; then
    info "Deploying YOLO12n function to Nuclio..."
    "$NUCTL" create project cvat --platform local 2>/dev/null || true
    "$NUCTL" deploy "$FUNC_NAME" \
        --project-name cvat \
        --platform local \
        --run-image "$SERVERLESS_IMAGE" \
        --file "$FUNC_YAML" \
        --env CVAT_FUNCTIONS_REDIS_HOST=cvat_redis_ondisk \
        --env CVAT_FUNCTIONS_REDIS_PORT=6666 \
        --platform-config '{"attributes": {"network": "cvat_cvat"}}'
    ok "Function deployed"
else
    ok "Function already running (container: $RUNNING)"
fi

# ── step 6: verify ────────────────────────────────────────────────────────────
info "Verifying CVAT can see the model..."
sleep 3

TOKEN=$(curl -sf -X POST "$CVAT_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"Admin1234!"}' \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['key'])" 2>/dev/null) \
    || fail "Could not authenticate to CVAT (wrong credentials?)"

HTTP=$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "Authorization: Token $TOKEN" "$CVAT_URL/api/lambda/functions")

if [[ "$HTTP" == "200" ]]; then
    COUNT=$(curl -sf -H "Authorization: Token $TOKEN" "$CVAT_URL/api/lambda/functions" \
        | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
    ok "CVAT lambda API OK — $COUNT model(s) available"
else
    fail "CVAT lambda API returned HTTP $HTTP — check docker logs cvat_server"
fi

# ── done ──────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════"
echo "  Environment ready."
echo "  CVAT:  $CVAT_URL"
echo ""
echo "  Run auto-labeling:"
echo "  cd frame_extractor"
echo "  python3 cvat_autolabel.py frames/<folder>"
echo "════════════════════════════════════════════"
