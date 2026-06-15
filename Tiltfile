# -*- mode: Python -*-
# Tiltfile for CVOps — inner-loop developer environment.
#
# Model:
#   • Stateful infra (postgres, redis, garage) → containers via docker_compose.
#   • App code (api, frontend)                → host processes via local_resource
#                                                (uvicorn --reload, npm run dev).
#   • Edge nginx (container)                   → proxies / → host Vite dev (with
#                                                HMR) and /api/v1 → host API, so
#                                                the real app is browser-usable at
#                                                http://localhost (and dev VMs).
#   Vite also proxies /api/v1 → http://localhost:8000 for the React app.
#
# For container-based pre-prod testing, use docker compose with profiles directly:
#   cd manifests
#   docker compose --profile app up                       # prod-target stack + worker-preprocessing
#   docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile app up
#
# Usage:
#   tilt up                       # postgres, redis, garage, api (host), frontend (host)
#   tilt down                     # stop everything
#
# Docs: https://docs.tilt.dev/

# ── Host prerequisites ──────────────────────────────────────────────────────
# Fail loud if the host can't run the app processes.
def require(cmd, hint):
    result = str(local('command -v %s >/dev/null 2>&1 && echo ok || echo missing' % cmd, quiet=True))
    if 'ok' not in result:
        fail('Missing host tool: %s\n  → %s' % (cmd, hint))

require('python3',  'install Python 3.12+ (mise/pyenv/system)')
require('node',     'install Node 20+')
require('npm',      'usually bundled with node')
require('docker',   'install Docker — needed for the infra containers')
require('openssl',  'install openssl — needed to generate dev secrets')

# ── Bootstrap manifests/.env from manifests/.env.example ────────────────────
if not os.path.exists('manifests/.env'):
    print('⚠  No manifests/.env file found — copying manifests/.env.example. Edit secrets before going live.')
    local('cp manifests/.env.example manifests/.env', quiet=True)

# Replace any leftover `change_me*` placeholders with freshly-generated secrets.
# A copied-but-unedited .env carries `GARAGE_RPC_SECRET=change_me_rpc_secret_hex_32_bytes`,
# which Garage rejects at startup ("Invalid RPC secret key: expected 32 bytes of
# random hex"). Idempotent — only placeholder values are touched, and POSTGRES_PASSWORD
# is left alone so it stays in sync with the DATABASE_URL string in the same file.
local('''
    cd manifests
    grep -q change_me .env || exit 0
    tmp=$(mktemp)
    while IFS= read -r line; do
        case "$line" in
            POSTGRES_PASSWORD=*|DATABASE_URL=*)
                echo "$line" ;;
            GARAGE_DEFAULT_ACCESS_KEY=GKchange_me*)
                echo "GARAGE_DEFAULT_ACCESS_KEY=GK$(openssl rand -hex 12)" ;;
            *=change_me*)
                echo "${line%%=*}=$(openssl rand -hex 32)" ;;
            *)
                echo "$line" ;;
        esac
    done < .env > "$tmp" && mv "$tmp" .env
    echo "⚠  Generated dev secrets for change_me placeholders in manifests/.env"
''', quiet=False)

# Parse .env into a dict so we can build localhost-rewritten connection strings
# for the host-side api and frontend processes.
def load_env(path):
    out = {}
    for line in str(read_file(path)).splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        out[k.strip()] = v.strip()
    return out

env = load_env('manifests/.env')

# Stale-env guard: catches both missing GARAGE_* (pre-Garage MinIO era) and
# any placeholder still on disk that would break Garage at startup.
if 'GARAGE_RPC_SECRET' not in env or 'MINIO_ROOT_USER' in str(read_file('manifests/.env')):
    fail("""manifests/.env is stale (missing GARAGE_* vars or still has MINIO_*).
  Diff against manifests/.env.example, then regenerate secrets with:
    openssl rand -hex 32                # for each *_SECRET / *_TOKEN / JWT_SECRET / WORKER_TOKEN
    echo "GK$(openssl rand -hex 12)"    # for GARAGE_DEFAULT_ACCESS_KEY""")

# Helper: pull a required key from .env or fail.
def envreq(key):
    if key not in env:
        fail('manifests/.env is missing required key: %s' % key)
    return env[key]

# ── Infra containers (docker compose) ───────────────────────────────────────
# Two separate compose projects so that CVAT failures never affect the main
# infra (postgres, redis, garage, nginx). If the cvops-cvat project has issues
# (disk full, Docker daemon problems, etc.) the API and frontend stay up.
docker_compose(
    ['manifests/docker-compose.yml'],
    env_file='manifests/.env',
    project_name='cvops',
)

# cvat_cvat must exist before Docker Compose validates the override file.
local('docker network inspect cvat_cvat >/dev/null 2>&1 || docker network create cvat_cvat', quiet=True)

docker_compose(
    ['manifests/docker-compose.override.yml'],
    env_file='manifests/.env',
    project_name='cvops-cvat',
)

dc_resource('postgres',
    labels=['1-infra'],
    links=[link('postgres://localhost:5432', 'pg')],
)

dc_resource('garage-init',
    labels=['1-infra'],
)

dc_resource('garage',
    labels=['1-infra'],
    resource_deps=['garage-init'],
    links=[
        link('http://localhost:3900', 's3 endpoint'),
        link('http://localhost:3903', 'admin api'),
    ],
)

dc_resource('redis',
    labels=['1-infra'],
    links=[link('redis://localhost:6379', 'redis')],
)

# cvat_cvat is declared `external: true` in docker-compose.override.yml — it
# must exist before any CVAT container starts. This is idempotent.
local_resource('cvat-network',
    cmd='docker network inspect cvat_cvat >/dev/null 2>&1 || docker network create cvat_cvat',
    labels=['1-infra'],
)

# nuctl talks directly to /var/run/docker.sock. The socket is owned by the
# `docker` group, so only members can access it. Group membership only takes
# effect in a fresh login shell — processes started before `usermod` (including
# Tilt itself) won't see the new group. Widening the socket permissions here
# ensures nuctl and the CVAT worker always have Docker access on any machine,
# without requiring a logout/re-login cycle.
local_resource('docker-socket-perms',
    cmd='sudo chmod 666 /var/run/docker.sock',
    labels=['1-infra'],
)

# ── CVAT stack (from docker-compose.override.yml) ───────────────────────────
dc_resource('cvat_db',             labels=['3-cvat'], resource_deps=['cvat-network'])
dc_resource('cvat_redis_inmem',    labels=['3-cvat'], resource_deps=['cvat-network'])
dc_resource('cvat_redis_ondisk',   labels=['3-cvat'], resource_deps=['cvat-network'])
dc_resource('cvat_clickhouse',     labels=['3-cvat'], resource_deps=['cvat-network'])
dc_resource('cvat_opa',            labels=['3-cvat'], resource_deps=['cvat-network'])
dc_resource('cvat_server',         labels=['3-cvat'], resource_deps=['cvat-network'])
# NOTE: cvat_db is ephemeral — tilt down wipes all CVAT users. After every
# tilt down + tilt up you must recreate the superuser manually:
#   docker exec cvat_server python manage.py createsuperuser --username nati --email natipinyan@gmail.com --noinput
#   docker exec cvat_server python manage.py shell -c "from django.contrib.auth.models import User; u=User.objects.get(username='nati'); u.set_password('Nati2133'); u.save()"
dc_resource('cvat_ui',             labels=['3-cvat'])
dc_resource('traefik',
    labels=['3-cvat'],
    links=[link('http://localhost:8080', 'cvat')],
)
dc_resource('nuclio',              labels=['3-cvat'], resource_deps=['cvat-network'])
dc_resource('cvat_worker_utils',           labels=['3-cvat'])
dc_resource('cvat_worker_import',          labels=['3-cvat'])
dc_resource('cvat_worker_export',          labels=['3-cvat'])
dc_resource('cvat_worker_annotation',      labels=['3-cvat'])
dc_resource('cvat_worker_webhooks',        labels=['3-cvat'])
dc_resource('cvat_worker_quality_reports', labels=['3-cvat'])
dc_resource('cvat_worker_chunks',          labels=['3-cvat'])
dc_resource('cvat_worker_consensus',       labels=['3-cvat'])
dc_resource('cvat_vector',         labels=['3-cvat'])
dc_resource('cvat_grafana',        labels=['3-cvat'])

# ── Garage S3 bootstrap (cluster layout + bucket + key) ─────────────────────
# A fresh Garage node serves S3 only after a layout is applied. We also create
# the bucket and import the access/secret key from .env so the API can auth.
# All steps are idempotent so this resource can re-run safely.
local_resource('garage-bootstrap',
    cmd='''
        set -e
        cd manifests
        ak=$(grep ^GARAGE_DEFAULT_ACCESS_KEY .env | cut -d= -f2)
        sk=$(grep ^GARAGE_DEFAULT_SECRET_KEY .env | cut -d= -f2)
        bucket=$(grep ^GARAGE_DEFAULT_BUCKET .env | cut -d= -f2)

        gx() { docker compose exec -T garage /garage "$@"; }

        for i in $(seq 1 60); do
            if gx status >/dev/null 2>&1; then break; fi
            sleep 1
        done

        if ! gx layout show 2>/dev/null | grep -qE "cluster layout version: [1-9]"; then
            node_id=$(gx node id -q | cut -d@ -f1)
            gx layout assign -z dc1 -c 1G "$node_id"
            gx layout apply --version 1
        fi

        gx bucket create "$bucket" 2>/dev/null || true

        if ! gx key info "$ak" >/dev/null 2>&1; then
            gx key import "$ak" "$sk" --yes
            gx key rename "$ak" cvops-default >/dev/null 2>&1 || true
        fi

        gx bucket allow --read --write --owner "$bucket" --key "$ak" >/dev/null
        gx bucket info "$bucket"
    ''',
    labels=['1-infra'],
    resource_deps=['garage'],
)

# ── Host-side install resources (one-time, auto-run on first tilt up) ──────
# Editable install for the API package; uvicorn comes in as a dep.
# Build an isolated venv at services/api/.venv and install the API package into
# it. A bare `pip install --user` fails on PEP-668 / externally-managed hosts
# (Arch, Debian 12+): "error: externally-managed-environment". The venv sidesteps
# that and keeps the editable install off the system interpreter. `python -m venv`
# is idempotent, so re-running just reuses the existing venv.
local_resource('api-install',
    cmd='cd services/api && python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]" >/dev/null',
    deps=['services/api/pyproject.toml'],
    labels=['5-setup'],
)

# Install the step implementations (cvops_steps) into the API venv so the
# engine registry picks up extract_frames at startup. Base deps only (no ml/train
# extras → no torch); the engine import is best-effort, but without this the
# registry is empty and workflow creation rejects step.extract_frames.
local_resource('steps-install',
    cmd='cd services/api && .venv/bin/python -m pip install -e ../../packages/steps >/dev/null',
    deps=['packages/steps/pyproject.toml'],
    resource_deps=['api-install'],
    labels=['5-setup'],
)

# npm install for the frontend.
local_resource('frontend-install',
    cmd='cd services/frontend && npm install --silent',
    deps=['services/frontend/package.json'],
    labels=['5-setup'],
)

# ── App processes (host) ────────────────────────────────────────────────────
# Connection strings rewritten to localhost:<published-port> — the host process
# hits Docker's exposed ports, not the compose-internal network DNS.
api_env = {
    'DATABASE_URL': 'postgresql+asyncpg://%s:%s@localhost:5432/%s' % (
        envreq('POSTGRES_USER'), envreq('POSTGRES_PASSWORD'), envreq('POSTGRES_DB'),
    ),
    'REDIS_URL':       'redis://localhost:6379/0',
    'S3_ENDPOINT':     'http://localhost:3900',
    # S3_PUBLIC_ENDPOINT intentionally unset: the API derives the presign host
    # per-request from the browser's Host header, so uploads work from localhost
    # and dev VMs alike. Set it only to force a fixed host/scheme (e.g. HTTPS).
    'S3_ACCESS_KEY':   envreq('GARAGE_DEFAULT_ACCESS_KEY'),
    'S3_SECRET_KEY':   envreq('GARAGE_DEFAULT_SECRET_KEY'),
    'S3_BUCKET':       envreq('GARAGE_DEFAULT_BUCKET'),
    'S3_REGION':       'garage',
    'JWT_SECRET':      envreq('JWT_SECRET'),
    'WORKER_TOKEN':    envreq('WORKER_TOKEN'),
    'PYTHONUNBUFFERED': '1',
    # worker-cvat exposes GET /models on port 8001 (proxied by cvats.py router).
    'MODEL_DEPLOYER_URL': 'http://localhost:8001',
}

local_resource('api',
    serve_cmd='cd services/api && .venv/bin/python -m uvicorn cvops_api.main:app --host 0.0.0.0 --port 8000 --reload',
    serve_env=api_env,
    deps=['services/api/src'],
    resource_deps=['postgres', 'redis', 'garage-bootstrap', 'api-install', 'steps-install', 'migrate-up'],
    readiness_probe=probe(
        period_secs=5,
        http_get=http_get_action(port=8000, path='/openapi.json'),
    ),
    links=[
        link('http://localhost:8000/docs',  'swagger'),
        link('http://localhost:8000/redoc', 'redoc'),
    ],
    labels=['2-app'],
)

local_resource('frontend',
    # Vite already proxies /api/v1 → http://localhost:8000 (see vite.config.ts).
    serve_cmd='cd services/frontend && npm run dev -- --host 0.0.0.0 --port 5173',
    deps=['services/frontend/src', 'services/frontend/vite.config.ts', 'services/frontend/index.html'],
    resource_deps=['api', 'frontend-install'],
    readiness_probe=probe(
        period_secs=5,
        http_get=http_get_action(port=5173, path='/'),
    ),
    links=[link('http://localhost:5173', 'vite dev')],
    labels=['2-app'],
)

# ── Edge proxy (container) ──────────────────────────────────────────────────
# nginx proxies / → host Vite dev (with HMR) and /api/v1 → host API. This is
# what makes `tilt up` a one-stop, browser-usable stack at http://localhost
# (and http://<dev-vm>:80 for VM-based devs). Swap the Vite proxy for a static
# frontend dist/ build later. Defined (profile-less) in docker-compose.yml.
dc_resource('nginx',
    labels=['2-app'],
    resource_deps=['api', 'frontend'],
    links=[link('http://localhost', 'app (nginx)')],
)

# ── Optional helper resources (manual trigger) ──────────────────────────────
local_resource('git-hooks',
    cmd='sh scripts/git-setup.sh',
    deps=['scripts/git-setup.sh'],
    labels=['5-setup'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

# Install the preprocessing worker into the API venv (which already carries
# cvops-api + cvops-steps). The worker reuses those packages, so it shares the env.
local_resource('worker-install',
    cmd='cd services/api && .venv/bin/python -m pip install -e ../worker-preprocessing >/dev/null',
    deps=['services/worker-preprocessing/pyproject.toml'],
    resource_deps=['api-install', 'steps-install'],
    labels=['5-setup'],
)

local_resource('worker-cvat-install',
    cmd='cd services/api && .venv/bin/python -m pip install -e ../worker-cvat >/dev/null',
    deps=['services/worker-cvat/pyproject.toml'],
    resource_deps=['api-install'],
    labels=['4-cvat-app'],
)

# Download nuctl (Nuclio CLI) once — used by the CVAT worker to deploy .pt models.
# Idempotent: skipped if the binary is already present and executable.
local_resource('nuctl-install',
    cmd='test -x services/worker-cvat/nuctl || curl -fsSL "https://github.com/nuclio/nuclio/releases/download/1.15.9/nuctl-1.15.9-linux-amd64" -o services/worker-cvat/nuctl && chmod +x services/worker-cvat/nuctl',
    labels=['4-cvat-app'],
)

# ── Worker processes (host) ─────────────────────────────────────────────────
# Redis-Streams preprocessing worker: consumes the `preprocessing` stream and
# runs extract_frames (and future preprocessing steps) out of the API process.
worker_env = dict(api_env)
worker_env['REDIS_STREAM'] = 'preprocessing'

local_resource('worker-preprocessing',
    serve_cmd='cd services/api && .venv/bin/python -m cvops_worker',
    serve_env=worker_env,
    deps=['services/worker-preprocessing/src'],
    resource_deps=['postgres', 'redis', 'garage-bootstrap', 'steps-install', 'worker-install', 'migrate-up'],
    labels=['2-app'],
)

# Redis-Streams CVAT worker: consumes the `cvat` stream (step.deploy_model),
# and also exposes GET /models on :8001 (proxied by the API's cvat.py router).
cvat_worker_env = dict(api_env)
cvat_worker_env['REDIS_STREAM']        = 'cvat'
cvat_worker_env['MODEL_DEPLOYER_PORT'] = '8001'
cvat_host_raw = env.get('CVAT_HOST', 'localhost')
cvat_worker_env['CVAT_HOST'] = cvat_host_raw if cvat_host_raw.startswith('http') else 'http://%s:8080' % cvat_host_raw
cvat_worker_env['CVAT_USERNAME']       = env.get('CVAT_USERNAME', 'admin')
cvat_worker_env['CVAT_PASSWORD']       = env.get('CVAT_PASSWORD', '')
cvat_worker_env['NUCTL_PATH']          = str(local('pwd', quiet=True)).strip() + '/services/worker-cvat/nuctl'

# worker-cvat waits for postgres/redis/garage (its own infra deps) but is
# intentionally NOT in the resource_deps of api/frontend/nginx — so a CVAT
# failure never blocks the main stack.
local_resource('worker-cvat',
    serve_cmd='cd services/api && .venv/bin/python -m worker_cvat',
    serve_env=cvat_worker_env,
    deps=['services/worker-cvat/src'],
    resource_deps=['postgres', 'redis', 'garage-bootstrap', 'migrate-up', 'worker-cvat-install', 'nuctl-install', 'docker-socket-perms'],
    labels=['4-cvat-app'],
)

# ── Quality gates ───────────────────────────────────────────────────────────
local_resource('api-test',
    cmd='cd services/api && pytest tests/ -q',
    labels=['6-quality'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('api-lint',
    cmd='cd services/api && ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/',
    labels=['6-quality'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('frontend-lint',
    cmd='cd services/frontend && npm run lint && npm run typecheck',
    labels=['6-quality'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('frontend-build',
    cmd='cd services/frontend && npm run build',
    labels=['6-quality'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

# ── DB operations (run against the local uvicorn process or via containers) ─
# Alembic migrations execute on the host against the local DATABASE_URL.
migrate_env = {'DATABASE_URL': api_env['DATABASE_URL']}

# Auto-runs on `tilt up` (api depends on it) so the schema — including new
# migrations like 0002 — is always applied before the API serves.
local_resource('migrate-up',
    cmd='cd services/api && .venv/bin/alembic upgrade head',
    env=migrate_env,
    labels=['7-db'],
    resource_deps=['postgres', 'api-install'],
)

local_resource('migrate-down',
    cmd='cd services/api && .venv/bin/alembic downgrade -1',
    env=migrate_env,
    labels=['7-db'],
    resource_deps=['postgres', 'api-install'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('migrate-revision',
    cmd='cd services/api && .venv/bin/alembic revision --autogenerate -m "tilt-generated"',
    env=migrate_env,
    labels=['7-db'],
    resource_deps=['postgres', 'api-install'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

local_resource('psql',
    cmd='''
        cd manifests
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

local_resource('garage-status',
    cmd='cd manifests && docker compose exec -T garage /garage status && docker compose exec -T garage /garage layout show',
    labels=['7-db'],
    resource_deps=['garage'],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

print('CVOps Tiltfile loaded — host dev mode (api + frontend on host, infra in compose)')
