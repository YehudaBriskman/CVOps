# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo at a glance

CVOps is an ML-lifecycle dashboard that collapses dataset versioning, workflow orchestration, human-in-the-loop labelling gates, blob storage, and training dispatch into one system. It is a small monorepo with four packages:

| Path | Role | Status |
|---|---|---|
| `services/api` | Python 3.12 / FastAPI — REST API, workflow engine, DB layer | implemented |
| `services/frontend` | TypeScript / React 18 + Vite — dashboard UI (auth, all pages, api layer, data-source/frame viewer) | implemented |
| `packages/steps` | Python — step implementations loaded by the engine (`extract_frames`, `commit_dataset`, `export_yolo`, `train` implemented; `auto_label`, `human_review` are stubs) | partial |
| `services/worker-preprocessing` | Python — Redis-Streams worker; consumes the `preprocessing` stream and runs steps out of the API process | implemented |

Standalone CLI prototypes for the same lifecycle steps live in `tools/frame-extractor/` (`extract_frames.py`, `auto_label.py`, `upload_to_cvat.py`).

`services/api/CLAUDE.md` is the authoritative orientation for API work — read it before touching `services/api`.

## Commands

### Stack

Two distinct entry points — keep them straight:

**Inner-loop dev → `tilt up`** (from repo root). Stateful infra (postgres, redis, garage) runs in containers; the API runs as a host `uvicorn --reload` and the frontend as host `npm run dev`. An nginx edge container is also brought up — it serves the placeholder `manifests/nginx/html/index.html` and proxies `/api/v1/*` to the host API (via `host.docker.internal`), reachable at `http://localhost` (and `http://<dev-vm>` for VM-based devs). The API *owns* the `/api/v1` prefix (routers are mounted under it in `main.py`), so both the nginx edge and Vite's `server.proxy` pass `/api/v1/*` through unchanged — no rewrite, prefix defined in one place. Migrations run automatically (`migrate-up`) and `packages/steps` is installed into the API venv (`steps-install`). Host prereqs: Python 3.12+, Node 20+, Docker, ffmpeg. First `tilt up` runs `pip install -e services/api[dev]` and `npm install` automatically.

**Pre-prod / integration → `docker compose` with profiles** (from `manifests/`). Everything containerised.

```bash
cd manifests

docker compose up                                                            # infra only (matches what Tilt uses)
docker compose --profile app up                                              # + api, frontend, nginx, worker-preprocessing (prod-target builds)
docker compose --profile all up                                              # everything

# Force dev-target containers (rare — for reproducing CI failures):
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile app up
```

All compose, env, and config files live under `manifests/`. Paths inside the compose files are relative to that directory.

The `worker-preprocessing` service runs in the `app`/`all` profiles (and as a host process under `tilt up`), so the ingest flow works end-to-end out of the API process.

### API (`services/api`)

```bash
pip install -e ".[dev]"
pip install "pydantic[email]"            # required for EmailStr schemas

pytest tests/ -q                          # full suite — uses testcontainers (needs Docker)
pytest tests/routers/test_auth.py -v      # single file
pytest tests/ -k "name_fragment"          # single test by name

ruff check src/ tests/
ruff format --check src/ tests/
mypy src/                                 # strict mode

uvicorn cvops_api.main:app --reload --port 8000
```

The test suite spins up a real PostgreSQL via `testcontainers` — there is no in-memory or SQLite fallback. DB layer changes must keep migrations and ORM models in sync; tests will catch divergence.

### Frontend (`services/frontend`)

```bash
npm install
npm run dev          # http://localhost:5173 in dev compose, :3000 in prod compose
npm run build        # tsc -b && vite build
npm run lint         # eslint, --max-warnings 0
npm run typecheck    # tsc --noEmit
```

## Architecture

```
Client ──► nginx ──► FastAPI ──► Depends(get_current_user)  ──► Router handler
                                  │  decode JWT                        │
                                  │  check Redis JTI blacklist         ├──► PostgreSQL (asyncpg)
                                  └  load User                         └──► Garage S3 (presigned URLs)
```

**Single FastAPI app, single process.** `services/api/src/cvops_api/main.py` mounts every router and registers a `lifespan` that initialises Redis and (best-effort) imports `cvops_steps.register_all()` to populate the step registry.

**Persistence layers (must understand together):**

- PostgreSQL holds all relational state — 21 ORM models in `db/models/`, Alembic migrations in `alembic/versions/` (`0001_initial_schema`, `0002_project_default_ingest_workflow`, `0003_data_source_unique_blob_per_project`, `0004_model_version_optional_container`).
- Garage (S3-compatible object store) holds every byte payload (images, annotations, model weights). Blobs are content-addressed by SHA-256; the API never proxies bytes — clients get presigned PUT/GET URLs. Presigned URLs are signed against a browser-reachable host (derived per-request from the `Host` header, or `S3_PUBLIC_ENDPOINT` if set), not the internal `S3_ENDPOINT`.
- Redis holds the JWT `jti` revocation list and any transient cache.

**Workflow engine** (`engine/coordinator.py`, `engine/ref_resolver.py`, `engine/step.py`):

Steps execute **out of process** on Redis Streams (doorbell) with Postgres as the authority — see `docs/services/redis-streams.md`. There is no in-process `execute_workflow` anymore.

- A workflow is a DAG: `{steps: [...], edges: [...]}` stored on `Workflow.definition`.
- `POST /workflows/{id}/runs` (and the `confirm-upload` auto-trigger) create a `pending` parent run, then call `advance_workflow(session, run_id, actor_id)` **synchronously in-request**. That creates a child `runs` row for every ready step, **freezes** resolved inputs onto `child.input_refs`, and `XADD`s a thin `{job_id, step_type, queue}` message onto each step's queue (default `preprocessing`). It runs no step.
- A per-queue worker (`services/worker-preprocessing`) consumes the stream, claims one `pending` child via `SELECT … FOR UPDATE SKIP LOCKED`, runs it through `process_step`, writes results to PG, `XACK`s, and calls `advance_workflow` again to enqueue whatever became ready.
- Idempotency key `sha256(type + config + resolved inputs)` still reuses outputs of identical prior succeeded child runs (created already `succeeded`, no enqueue).
- `GateException` from a step pauses the run (`status = waiting`); `POST /runs/{id}/gates/{step_id}/resolve` resumes it by calling `advance_workflow`. Any other exception fails the child + parent on a fresh transaction so transient session state can't swallow the error.
- A step's queue is `Step.queue` (empty → `preprocessing`), so routing needs no edit to the step package.
- Step implementations live in `cvops_steps` (separate package, dynamically loaded at startup). If it fails to import, the engine still runs — just with an empty registry.

**Multi-tenancy** is enforced at the query level: every resource has an `org_id` and routers filter on `current_user.org_id`. Do not rely on application-layer checks.

## Project-specific conventions

These are the conventions that are easy to violate without realising it. Most are documented in `services/api/CLAUDE.md`; the highlights:

- **Cursor pagination, always.** Pattern: `WHERE id > cursor_uuid ORDER BY id LIMIT n+1`; cursor is the base64-encoded UUID of the last item. Response shape: `{"items": [...], "next_cursor": "..." | null}`.
- **No raw bytes through the API.** Use `get_storage().get_presigned_get(blob_hash)` / `get_presigned_put(blob_hash)`. Immutable blobs and commits get `Cache-Control: immutable, max-age=31536000`.
- **Soft-delete via `deleted_at: datetime | None`.** List queries must filter `WHERE deleted_at IS NULL`. Exceptions — `AnnotationRevision`, `Event`, `Commit` are append-only; never delete them.
- **API version prefix.** All public routers are mounted under `/api/v1` in `main.py` (the API owns the prefix; the nginx edge and Vite proxy pass it through unchanged). So a route is reachable at `/api/v1/...` (e.g. `/api/v1/projects/{id}/samples`, `/api/v1/auth/token`). The liveness probe `/health` and the human-facing `/dataset` viewer stay at root, unversioned.
- **Auth dependency:** `get_current_user` validates JWT, checks the Redis blacklist, and loads the `User`. Every endpoint except `/auth/*` requires it.
- **Internal endpoints** (`/api/v1/internal/*`) authenticate with the `WORKER_TOKEN` shared secret, not user JWTs.
- **Router path composition.** Some routers (`data_sources`, `samples`, `ontologies`, `datasets`, `workflows`, `runs`, `models`, `training_containers`) define their full paths inline (e.g. `/projects/{id}/samples`) and are mounted with just the `/api/v1` prefix; `auth`, `orgs`, `projects`, `registry`, `internal` add their own segment (e.g. `/api/v1/projects`). The router objects themselves must NOT declare `APIRouter(prefix=…)`, or paths double up (e.g. `/api/v1/projects/projects`).
- **Backend-triggered ingest.** `POST /data-sources/{id}/confirm-upload` registers the blob and, if the project has `default_ingest_workflow_id` set, auto-dispatches that workflow with `params.source_id` and returns its `run_id`. Hash is verified lazily in `extract_frames`, not at confirm. `confirm-upload` reuses an already-registered `Blob` without re-promoting (the add-without-reupload path) and returns `409` if the same content is already a live source in this project (`uq_data_sources_project_blob`).
- **Duplicate-upload check.** The client hashes the file *first*, then `POST /projects/{id}/data-sources/check` (`{blob_hash}` → `{exists, in_current_project, matches}`) probes for an existing org-wide copy so a duplicate is never pushed over the wire. The org-scoped join means cross-org copies are invisible. Exact-hash only; perceptual near-dup is out of scope.

## Adding a new step type

1. Subclass `Step` in `cvops_steps` (the `packages/steps` package in this monorepo, installed into the API env separately).
2. Set `type_key`, `config_schema` (JSON Schema), `category`, `is_gate`.
3. Register in `cvops_steps.register_all()` via `registry.register(MyStep())`.
4. The coordinator picks it up at runtime — no API changes needed. Override `queue` on the step to route it to a non-`preprocessing` worker.

## Git workflow (enforced by hooks)

Hooks live in `.githooks/` and are activated by `sh scripts/git-setup.sh` (sets `core.hooksPath`).

- **Branch format:** `[Claude-Bot/]<Type>/<3-8-kebab-word-title>`, types are `Feat|Fix|Chore|Docs|Refactor|Style|Test|Lint` (capitalised). The `pre-push` hook rejects anything else and blocks direct push to `main`, `develop`, `master`.
- **Commit subject:** `<type>: <3-10 word title>` with lowercase types; subject and body separated by a blank line. The `commit-msg` hook enforces this.
- **Atomic commits.** One commit = one responsibility. Never mix feature + fix, refactor + logic change, or formatting + behaviour.
- **Bot identity.** Claude-authored commits end with `Generated by [All-Powerful Agent] [Claude-Max] of [@BenRachmiel]` on the final line (blank line before it). This supersedes the default `Co-Authored-By: Claude …` trailer and the repo's earlier `[Claude-Bot] of [@Yehuda Briskman]` convention — do not add both.

## Reference docs

- `README.md` — product overview, full API table, walkthrough.
- `docs/MASTER_PLAN.md` — full system reference.
- `docs/01-principles-and-architecture.md` through `docs/10-glossary-and-roadmap.md` — design docs.
- `docs/11-extract-frames.md`, `12-auto-label.md`, `13-upload-to-cvat.md` — the three CLI step specs implemented in `tools/frame-extractor/`.
- `services/api/docs/db/` — per-model schema notes.
- `services/api/CLAUDE.md` — API developer orientation, shared deps, auth model.
