# -*- mode: Python -*-
# Tiltfile for CVOps — ML-lifecycle dashboard
#
# Usage:
#   tilt up                       # full dev stack: postgres, garage(-init), redis, api, frontend, nginx
#   tilt up -- --phase2           # also start the Celery worker
#   tilt up -- --no-edge          # skip the nginx edge proxy
#   tilt down                     # stop everything
#
# Docs: https://docs.tilt.dev/

# ── Config flags ────────────────────────────────────────────────────────────
config.define_bool('phase2')      # --phase2  → start the Celery worker
config.define_bool('no-edge')     # --no-edge → skip nginx (use direct ports)
cfg = config.parse()

PHASE2 = cfg.get('phase2', False)
NO_EDGE = cfg.get('no-edge', False)

# ── Bootstrap .env from .env.example ────────────────────────────────────────
# Docker-compose reads .env at parse time; without it, vars resolve to "".
if not os.path.exists('.env'):
    print('⚠  No .env file found — copying .env.example. Edit secrets before going live.')
    local('cp .env.example .env', quiet=True)

# ── Docker Compose ──────────────────────────────────────────────────────────
# Base file plus the dev override (hot-reload, source mounts, debug ports).
compose_files = ['docker-compose.yml', 'docker-compose.dev.yml']
profiles = ['phase2'] if PHASE2 else []

docker_compose(compose_files, profiles=profiles, env_file='.env')

# ── Resource organisation ───────────────────────────────────────────────────
# Labels group services in the Tilt UI; resource_deps wire startup order.

# Data layer ----------------------------------------------------------------
dc_resource('postgres',
    labels=['1-data'],
    links=[link('postgres://localhost:5432', 'pg')],
)

# One-shot init: chowns the Garage volumes to UID 1000 so the non-root Garage
# server can write to them. Exits 0 on success; compose blocks `garage` until
# this completes successfully.
dc_resource('garage-init',
    labels=['1-data'],
)

dc_resource('garage',
    labels=['1-data'],
    resource_deps=['garage-init'],
    links=[
        link('http://localhost:3900', 's3 endpoint'),
        link('http://localhost:3903', 'admin api'),
    ],
)

dc_resource('redis',
    labels=['1-data'],
    links=[link('redis://localhost:6379', 'redis')],
)

# Application layer ---------------------------------------------------------
dc_resource('api',
    labels=['2-app'],
    resource_deps=['postgres', 'garage-bootstrap', 'redis'],
    links=[
        link('http://localhost:8000/docs', 'swagger'),
        link('http://localhost:8000/redoc', 'redoc'),
        link('http://localhost:8000/health', 'health'),
    ],
)

dc_resource('frontend',
    labels=['2-app'],
    resource_deps=['api'],
    links=[link('http://localhost:5173', 'vite dev')],
)

# Phase-2 worker (only when --phase2 passed) --------------------------------
if PHASE2:
    dc_resource('worker',
        labels=['3-phase2'],
        resource_deps=['api', 'redis'],
    )

# Edge proxy ----------------------------------------------------------------
if NO_EDGE:
    # Stop nginx but keep it parsed so compose stays consistent.
    dc_resource('nginx', labels=['4-edge'], auto_init=False,
                trigger_mode=TRIGGER_MODE_MANUAL)
else:
    dc_resource('nginx',
        labels=['4-edge'],
        resource_deps=['api', 'frontend'],
        links=[link('http://localhost', 'nginx')],
    )

# ── Local install resources (host-side deps for editor/typecheck/pytest) ────
local_resource('api-install',
    cmd='cd packages/api && pip install -e ".[dev]" && pip install "pydantic[email]"',
    deps=['packages/api/pyproject.toml'],
    labels=['5-setup'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('frontend-install',
    cmd='cd packages/frontend && npm install',
    deps=['packages/frontend/package.json'],
    labels=['5-setup'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('worker-install',
    cmd='cd packages/worker && pip install -e .',
    deps=['packages/worker/pyproject.toml'],
    labels=['5-setup'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('git-hooks',
    cmd='sh scripts/git-setup.sh',
    deps=['scripts/git-setup.sh'],
    labels=['5-setup'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

# ── Quality gates ───────────────────────────────────────────────────────────
local_resource('api-test',
    cmd='cd packages/api && pytest tests/ -q',
    labels=['6-quality'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('api-lint',
    cmd='cd packages/api && ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/',
    labels=['6-quality'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('frontend-lint',
    cmd='cd packages/frontend && npm run lint && npm run typecheck',
    labels=['6-quality'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('frontend-build',
    cmd='cd packages/frontend && npm run build',
    labels=['6-quality'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

# ── DB operations ───────────────────────────────────────────────────────────
# Alembic migrations execute inside the running api container — uses the
# compose-network postgres connection rather than localhost.
local_resource('migrate-up',
    cmd='docker compose exec -T api alembic upgrade head',
    labels=['7-db'],
    resource_deps=['api'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('migrate-down',
    cmd='docker compose exec -T api alembic downgrade -1',
    labels=['7-db'],
    resource_deps=['api'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('migrate-revision',
    cmd='docker compose exec -T api alembic revision --autogenerate -m "tilt-generated"',
    labels=['7-db'],
    resource_deps=['api'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('psql',
    cmd='''
        user=$(grep ^POSTGRES_USER .env | cut -d= -f2)
        db=$(grep ^POSTGRES_DB .env | cut -d= -f2)
        pw=$(grep ^POSTGRES_PASSWORD .env | cut -d= -f2)
        docker compose exec -e PGPASSWORD="$pw" postgres psql -U "$user" "$db"
    ''',
    labels=['7-db'],
    resource_deps=['postgres'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

# ── Garage S3 bootstrap ─────────────────────────────────────────────────────
# A fresh Garage node serves S3 only after a cluster layout is assigned +
# applied. We also need to create the bucket and import the access/secret
# key from .env so the API can authenticate (Garage env vars only cover the
# admin/RPC/metrics tokens — bucket and key are runtime-managed).
#
# The Garage image is distroless: no shell, no awk, no grep. Every step
# invokes /garage directly via `docker compose exec`, and parsing happens
# on the host. All steps are idempotent so this resource can re-run safely.
local_resource('garage-bootstrap',
    cmd='''
        set -e
        ak=$(grep ^GARAGE_DEFAULT_ACCESS_KEY .env | cut -d= -f2)
        sk=$(grep ^GARAGE_DEFAULT_SECRET_KEY .env | cut -d= -f2)
        bucket=$(grep ^GARAGE_DEFAULT_BUCKET .env | cut -d= -f2)

        gx() { docker compose exec -T garage /garage "$@"; }

        # Wait for the daemon to answer status
        for i in $(seq 1 60); do
            if gx status >/dev/null 2>&1; then break; fi
            sleep 1
        done

        # Layout: assign capacity to the single node, then apply.
        # `layout show` prints "Current cluster layout version: N" — N>0 means applied.
        if ! gx layout show 2>/dev/null | grep -qE "cluster layout version: [1-9]"; then
            node_id=$(gx node id -q | cut -d@ -f1)
            gx layout assign -z dc1 -c 1G "$node_id"
            gx layout apply --version 1
        fi

        # Bucket — idempotent
        gx bucket create "$bucket" 2>/dev/null || true

        # Key — import with the exact access/secret from .env so the API can use them
        if ! gx key info "$ak" >/dev/null 2>&1; then
            gx key import --yes -a "$ak" -s "$sk" cvops-default
        fi

        # Grant the key r/w on the bucket (idempotent)
        gx bucket allow --read --write --owner "$bucket" --key "$ak" >/dev/null

        gx bucket info "$bucket"
    ''',
    labels=['7-db'],
    resource_deps=['garage'],
)

local_resource('garage-status',
    cmd='docker compose exec -T garage /garage status && docker compose exec -T garage /garage layout show',
    labels=['7-db'],
    resource_deps=['garage'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

print('CVOps Tiltfile loaded — phase2={}, no-edge={}'.format(PHASE2, NO_EDGE))
