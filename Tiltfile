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
    done < .env > "$tmp"
    # Only replace .env when something actually changed. POSTGRES_PASSWORD /
    # DATABASE_URL keep their `change_me_postgres` value by design, so `grep
    # change_me` stays true forever — an unconditional `mv` would rewrite .env on
    # every Tiltfile parse, churn its mtime, and (since .env is a read_file dep +
    # the compose env_file) trigger an endless re-parse + rebuild loop.
    if cmp -s "$tmp" .env; then
        rm -f "$tmp"
    else
        mv "$tmp" .env
        echo "⚠  Generated dev secrets for change_me placeholders in manifests/.env"
    fi
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

# ── Infra containers (docker compose, no profile = infra only) ──────────────
# Paths inside the compose files are relative to manifests/ (their own dir).
docker_compose(
    # The override adds the CVAT stack (server, ui, traefik:8080, db, redis,
    # opa, workers + analytics). Its profile-less services come up with the
    # infra; the auto-label layer (nuclio, model-deployer) and the containerised
    # worker-cvat stay profile-gated, so Tilt skips them — worker-cvat runs as a
    # host process below instead.
    ['manifests/docker-compose.yml', 'manifests/docker-compose.override.yml'],
    env_file='manifests/.env',
    project_name='cvops',
    # Activate the `worker` profile so worker-training (the `training` queue
    # consumer) comes up as a container — it carries the heavy ML stack
    # (torch/ultralytics) on its image, so it can't run as a host process like
    # the other workers. The `worker` profile pulls ONLY worker-training, not the
    # `app`-profile services (api/frontend/worker-cvat run on the host / are
    # gated), so it doesn't collide with the host processes.
    profiles=['worker'],
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

# MLflow tracking server (+ one-shot DB create). Both are no-profile compose
# services, so they come up with the infra. dc_resource only labels/links them.
dc_resource('mlflow-init',
    labels=['1-infra'],
    resource_deps=['postgres'],
)

dc_resource('mlflow',
    labels=['1-infra'],
    resource_deps=['mlflow-init', 'garage-bootstrap'],
    links=[link('http://localhost:5000', 'mlflow ui')],
)

# ── CVAT stack (containers, from docker-compose.override.yml) ────────────────
# The override's profile-less services come up here (cvat_server/ui, the data
# layer, workers, traefik). The analytics layer (cvat_vector/grafana) and the
# auto-label layer (nuclio/model-deployer) stay profile-gated, so Tilt skips
# them. Reach CVAT at :8080 (traefik).
#
# CVAT's compose bind-mounts a few config files from the services/cvat
# submodule (traefik's routing rules). `tilt up` doesn't init submodules, so do
# it here (shallow, idempotent) before the CVAT containers mount them —
# otherwise Docker auto-creates root-owned junk dirs at those paths. start_env.sh
# does the same init for its full-analytics run.
local_resource('cvat-submodule',
    cmd='git submodule update --init --depth 1 services/cvat',
    deps=['.gitmodules'],
    labels=['3-cvat'],
)

dc_resource('traefik',
    labels=['3-cvat'],
    resource_deps=['cvat-submodule'],
)
dc_resource('cvat_server',
    labels=['3-cvat'],
    links=[link('http://localhost:8080', 'cvat')],
)
dc_resource('cvat_ui',
    labels=['3-cvat'],
    resource_deps=['cvat_server'],
)

# Training-queue worker (container — torch/ultralytics live on its image, so it
# can't be a host process). Consumes the `training` stream: clones the trainer
# repo, runs it against the exported dataset, logs to MLflow, writes a
# ModelVersion. First `tilt up` builds the image (heavy ML deps) once.
dc_resource('worker-training',
    labels=['2-app'],
    resource_deps=['postgres', 'redis', 'garage-bootstrap', 'mlflow', 'migrate-up'],
)

# CVAT admin provisioning runs as the one-shot `cvat_admin_init` compose service
# (docker-compose.override.yml), so it happens under both `tilt up` and
# `docker compose --profile app` — not just here. dc_resource only labels it.
dc_resource('cvat_admin_init',
    labels=['3-cvat'],
    resource_deps=['cvat_server'],
)

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
    # The API's /internal/cvat/webhook verifies the HMAC signature CVAT signs
    # review-completion callbacks with; must match the secret worker-cvat
    # registers the webhook with (below).
    'CVAT_WEBHOOK_SECRET': envreq('CVAT_WEBHOOK_SECRET'),
    'PYTHONUNBUFFERED': '1',
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
    # MLflow comes up as a no-profile compose service on host :5000, so the
    # model-page "MLflow run" link points there. VM devs can override in .env.
    serve_env={'VITE_MLFLOW_URL': env.get('VITE_MLFLOW_URL', 'http://localhost:5000')},
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

# Install the CVAT worker (and its siblings worker-common + cvat-client, which
# pulls cvat-sdk) into the API venv so the host worker-cvat process can import
# them. Shares the venv with the API + steps, same as worker-preprocessing.
local_resource('worker-cvat-install',
    cmd='cd services/api && .venv/bin/python -m pip install -e ../../packages/worker-common -e ../../packages/cvat-client -e ../worker-cvat >/dev/null',
    deps=[
        'services/worker-cvat/pyproject.toml',
        'packages/worker-common/pyproject.toml',
        'packages/cvat-client/pyproject.toml',
    ],
    resource_deps=['api-install', 'steps-install'],
    labels=['5-setup'],
)

# ── Worker processes (host) ─────────────────────────────────────────────────
# Redis-Streams preprocessing worker: consumes the `preprocessing` stream and
# runs extract_frames (and future preprocessing steps) out of the API process.
worker_env = dict(api_env)
worker_env['REDIS_STREAM'] = 'preprocessing'

local_resource('worker-preprocessing',
    serve_cmd='cd services/api && .venv/bin/python -m cvops_worker',
    serve_env=worker_env,
    # Watch the step impls too — extract_frames/commit_dataset/export_yolo are
    # editable-installed from packages/steps, so the worker must restart to pick
    # up their changes (Python doesn't hot-reload).
    deps=['services/worker-preprocessing/src', 'packages/steps/src/cvops_steps'],
    resource_deps=['postgres', 'redis', 'garage-bootstrap', 'steps-install', 'worker-install', 'migrate-up'],
    labels=['2-app'],
)

# CVAT-queue worker (host): consumes the `cvat` stream, runs step.human_review
# (pushes the review batch into CVAT, parks the run at the gate) and, on a CVAT
# completion webhook, pulls reviewed annotations back and resumes the run.
# worker_cvat hardcodes its stream name to `cvat`, so no REDIS_STREAM here.
# CVAT_URL hits traefik on the host's published :8080.
#
# CVAT_WEBHOOK_TARGET is intentionally unset: CVAT 2.x dropped task-scoped
# webhooks, so auto-resume via webhook can't work. Completion is driven manually
# from the run page ("Sync from CVAT & complete" → POST .../gates/{step}/sync).
worker_cvat_env = dict(api_env)
worker_cvat_env.update({
    'CVAT_URL':            'http://localhost:8080',
    'CVAT_PUBLIC_URL':     env.get('CVAT_PUBLIC_URL', 'http://localhost:8080'),
    'CVAT_USERNAME':       envreq('CVAT_USERNAME'),
    'CVAT_PASSWORD':       envreq('CVAT_PASSWORD'),
})

local_resource('worker-cvat',
    serve_cmd='cd services/api && .venv/bin/python -m worker_cvat.main',
    serve_env=worker_cvat_env,
    # Watch the step + cvat-client sources too — they're editable-installed into
    # the venv, so the worker must restart to pick up changes to the human_review
    # step or the CVAT client (Python doesn't hot-reload like uvicorn --reload).
    deps=[
        'services/worker-cvat/src',
        'packages/worker-common/src/cvops_worker_common',
        'packages/steps/src/cvops_steps',
        'packages/cvat-client/src/cvops_cvat_client',
    ],
    resource_deps=['postgres', 'redis', 'garage-bootstrap', 'steps-install', 'worker-cvat-install', 'migrate-up', 'cvat_server', 'cvat_admin_init'],
    labels=['3-cvat'],
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
