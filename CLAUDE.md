# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo at a glance

CVOps is an ML-lifecycle dashboard that collapses dataset versioning, workflow orchestration, human-in-the-loop labelling gates, blob storage, and training dispatch into one system. It is a small monorepo with four packages:

| Path | Role | Status |
|---|---|---|
| `packages/api` | Python 3.12 / FastAPI — REST API, workflow engine, DB layer | implemented |
| `packages/frontend` | TypeScript / React 18 + Vite — dashboard UI | in progress |
| `packages/steps` | Python — step implementations (`extract_frames`, `auto_label`, …) loaded by the engine | scaffolding |
| `packages/worker` | Python / Celery — async worker queue | Phase 2 |

Standalone CLI prototypes for the same lifecycle steps live in `frame_extractor/` (`extract_frames.py`, `auto_label.py`, `upload_to_cvat.py`).

`packages/api/CLAUDE.md` is the authoritative orientation for API work — read it before touching `packages/api`.

## Commands

### Stack (Docker Compose)

```bash
docker compose up                                                  # full stack: postgres, garage, redis, api, frontend, nginx
docker compose -f docker-compose.yml -f docker-compose.dev.yml up  # hot-reload dev mode
docker compose --profile phase2 up                                 # also start the Celery worker
```

The `worker` service is gated behind the `phase2` profile and does not start by default.

### API (`packages/api`)

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

### Frontend (`packages/frontend`)

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

**Single FastAPI app, single process.** `packages/api/src/cvops_api/main.py` mounts every router and registers a `lifespan` that initialises Redis and (best-effort) imports `cvops_steps.register_all()` to populate the step registry.

**Persistence layers (must understand together):**

- PostgreSQL holds all relational state — 21 ORM models in `db/models/`, single Alembic migration `0001_initial_schema.py`.
- Garage (S3-compatible object store) holds every byte payload (images, annotations, model weights). Blobs are content-addressed by SHA-256; the API never proxies bytes — clients get presigned PUT/GET URLs.
- Redis holds the JWT `jti` revocation list and any transient cache.

**Workflow engine** (`engine/executor.py`, `engine/ref_resolver.py`, `engine/step.py`):

- A workflow is a DAG: `{steps: [...], edges: [...]}` stored on `Workflow.definition`.
- `POST /workflows/{id}/runs` returns immediately with `status: pending`; `execute_workflow(run_id, actor_id)` runs as a FastAPI `BackgroundTask` and creates its own `async_session_factory()` session.
- Execution: Kahn's topological sort → for each step, compute idempotency key `sha256(type + config + resolved inputs)`, reuse outputs of identical prior child runs, resolve `$steps.<id>.outputs.<name>` refs, call the registered step implementation.
- `GateException` from a step pauses the run (`status = waiting`); `POST /runs/{id}/gates/{step_id}/resolve` resumes it. Any other exception fails the run; the executor's outer `except` opens a fresh session and writes `status=failed` so transient session state can't swallow the error.
- Step implementations live in `cvops_steps` (separate package, dynamically loaded at startup). If it fails to import, the engine still runs — just with an empty registry.

**Multi-tenancy** is enforced at the query level: every resource has an `org_id` and routers filter on `current_user.org_id`. Do not rely on application-layer checks.

## Project-specific conventions

These are the conventions that are easy to violate without realising it. Most are documented in `packages/api/CLAUDE.md`; the highlights:

- **Cursor pagination, always.** Pattern: `WHERE id > cursor_uuid ORDER BY id LIMIT n+1`; cursor is the base64-encoded UUID of the last item. Response shape: `{"items": [...], "next_cursor": "..." | null}`.
- **No raw bytes through the API.** Use `get_storage().get_presigned_get(blob_hash)` / `get_presigned_put(blob_hash)`. Immutable blobs and commits get `Cache-Control: immutable, max-age=31536000`.
- **Soft-delete via `deleted_at: datetime | None`.** List queries must filter `WHERE deleted_at IS NULL`. Exceptions — `AnnotationRevision`, `Event`, `Commit` are append-only; never delete them.
- **Auth dependency:** `get_current_user` validates JWT, checks the Redis blacklist, and loads the `User`. Every endpoint except `/auth/*` requires it.
- **Internal endpoints** (`/internal/*`) authenticate with the `WORKER_TOKEN` shared secret, not user JWTs.
- **Routers without prefixes** (`data_sources`, `samples`, `ontologies`, `datasets`, `workflows`, `runs`, `models`, `training_containers`) define their full paths inline (e.g. `/projects/{id}/samples`). Only `auth`, `orgs`, `projects`, `registry`, `internal` use a router prefix.

## Adding a new step type

1. Subclass `Step` in `cvops_steps` (separate package, not in this repo).
2. Set `type_key`, `config_schema` (JSON Schema), `category`, `is_gate`.
3. Register in `cvops_steps.register_all()` via `registry.register(MyStep())`.
4. The executor picks it up at runtime — no API changes needed.

## Git workflow (enforced by hooks)

Hooks live in `.githooks/` and are activated by `sh scripts/git-setup.sh` (sets `core.hooksPath`).

- **Branch format:** `[Claude-Bot/]<Type>/<3-8-kebab-word-title>`, types are `Feat|Fix|Chore|Docs|Refactor|Style|Test|Lint` (capitalised). The `pre-push` hook rejects anything else and blocks direct push to `main`, `develop`, `master`.
- **Commit subject:** `<type>: <3-10 word title>` with lowercase types; subject and body separated by a blank line. The `commit-msg` hook enforces this.
- **Atomic commits.** One commit = one responsibility. Never mix feature + fix, refactor + logic change, or formatting + behaviour.
- **Bot identity.** Per the user's global rules, Claude-authored commits end with `Generated by [<Agent-Role>-Agent] [Claude-Bot] of [@Yehuda Briskman]` on the final line (blank line before it).

## Reference docs

- `README.md` — product overview, full API table, walkthrough.
- `docs/MASTER_PLAN.md` — full system reference.
- `docs/01-principles-and-architecture.md` through `docs/10-glossary-and-roadmap.md` — design docs.
- `docs/11-extract-frames.md`, `12-auto-label.md`, `13-upload-to-cvat.md` — the three CLI step specs implemented in `frame_extractor/`.
- `packages/api/docs/db/` — per-model schema notes.
- `packages/api/CLAUDE.md` — API developer orientation, shared deps, auth model.
