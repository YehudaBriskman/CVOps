# CVOps

> Model-agnostic ML lifecycle dashboard — from raw video to trained model, fully versioned.

[![API CI](https://github.com/YehudaBriskman/CVOps/actions/workflows/ci-api.yml/badge.svg)](https://github.com/YehudaBriskman/CVOps/actions/workflows/ci-api.yml)
[![Lint](https://github.com/YehudaBriskman/CVOps/actions/workflows/lint-api.yml/badge.svg)](https://github.com/YehudaBriskman/CVOps/actions/workflows/lint-api.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

```
raw video/images ──▶ extract frames ──▶ auto-label ──▶ human review (CVAT)
                                                               │
                                                               ▼
                                              commit dataset ──▶ export YOLO
                                                                      │
                                                                      ▼
                                                       dispatch Docker training
                                                                      │
                                                                      ▼
                                                               model_version ✓
```

## Features

- **Dataset versioning** — Git-like commits, refs (branches/tags), and set-diffs on labelled image collections
- **Workflow orchestration** — DAG-based pipelines where step outputs feed downstream steps via typed `$steps.<id>.outputs.<name>` refs
- **Human-in-the-loop gates** — A gate step pauses a run and waits for an operator to resolve it before the engine continues
- **Training dispatch** — Launches a Docker container per job, monitors it, and registers the resulting weights as a `ModelVersion`
- **Content-addressed blob storage** — Every image and weight file keyed by SHA-256 in MinIO; presigned URLs returned to clients, never raw bytes through the API
- **Org-scoped multi-tenancy** — All resources scoped to `org_id`; JWT HS256 auth with access/refresh token rotation and Redis-backed JTI revocation

## Quick start

```bash
# 1. Clone and fill in secrets
cp .env.example .env          # edit passwords and JWT_SECRET
sh scripts/git-setup.sh       # install git hooks (once per clone)

# 2. Start the full stack
docker compose up
```

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |
| MinIO console | http://localhost:9001 |

## Architecture

```
nginx (:80)
├── /api  ──▶ FastAPI (:8000)
│               ├── PostgreSQL 16   (SQLAlchemy 2.0 async + asyncpg)
│               ├── MinIO           (content-addressed blob storage)
│               └── Redis 7         (JWT blacklist)
└── /     ──▶ React SPA (:3000)
```

### Packages

| Package | Language | Status | Purpose |
|---|---|---|---|
| `packages/api` | Python 3.12 / FastAPI | ✅ Complete | REST API, workflow engine, DB layer (21 models, 146 tests) |
| `packages/frontend` | TypeScript / React | 🚧 In progress | Dashboard UI |
| `packages/steps` | Python | 🚧 Pending | Step implementations (extract, label, export, train) |
| `packages/worker` | Python / Celery | 📋 Phase 2 | Async worker queue |

## API overview

All endpoints (except `/auth/*`) require `Authorization: Bearer <token>`.

| Group | Endpoints |
|---|---|
| **Auth** | `POST /auth/register` `POST /auth/token` `POST /auth/refresh` `POST /auth/revoke` `GET /auth/me` |
| **Orgs** | `GET/PATCH /orgs/current` · `GET/POST/PATCH/DELETE /orgs/current/members/{id}` |
| **Projects** | `GET/POST /projects` · `GET/PATCH/DELETE /projects/{id}` |
| **Data sources** | `GET/POST /projects/{id}/data-sources` · `POST /data-sources/{id}/confirm-upload` · `GET/DELETE /data-sources/{id}` |
| **Samples** | `GET /projects/{id}/samples` · `GET /samples/{id}` · `GET /samples/{id}/image-url` · `GET/POST /samples/{id}/annotations` |
| **Ontologies** | `GET/POST /projects/{id}/ontologies` · `GET /ontologies/{id}` · `POST/PATCH/DELETE /ontologies/{id}/classes/{cid}` |
| **Datasets** | `GET/POST /projects/{id}/datasets` · `GET/POST /datasets/{id}/commits` · `GET/POST/DELETE /datasets/{id}/refs` · `GET /datasets/{id}/diff` |
| **Workflows** | `GET/POST /projects/{id}/workflows` · `GET/PATCH/DELETE /workflows/{id}` |
| **Runs** | `POST /workflows/{id}/runs` · `GET /runs/{id}` · `GET /runs/{id}/events[/stream]` · `POST /runs/{id}/cancel` · `POST /runs/{id}/retry` · `POST /runs/{id}/gates/{step_id}/resolve` |
| **Models** | `GET /projects/{id}/models` · `GET /models/{id}` · `GET /models/{id}/weights-url` |
| **Training containers** | `GET/POST /projects/{id}/training-containers` · `GET/PATCH/DELETE /training-containers/{id}` · `POST /training-containers/{id}/validate` |
| **Registry** | `GET /registry/types[?category=]` · `GET /registry/types/{key}` |

Full interactive docs at `http://localhost:8000/docs` once the stack is running.

## Development

### API (Python)

```bash
cd packages/api

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run tests — testcontainers spins up postgres automatically (requires Docker)
pytest tests/ -q

# Dev server with hot-reload
uvicorn cvops_api.main:app --reload --port 8000
```

### Frontend (TypeScript)

```bash
cd packages/frontend
npm install
npm run dev
```

### Full stack in development mode

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## Tech stack

| Layer | Technology |
|---|---|
| API framework | FastAPI 0.115 |
| Database | PostgreSQL 16 · SQLAlchemy 2.0 async · asyncpg |
| Migrations | Alembic |
| Blob storage | MinIO (S3-compatible) via boto3 |
| Cache / token blacklist | Redis 7 |
| Auth | JWT HS256 (python-jose) · bcrypt (passlib) |
| Validation | Pydantic v2 |
| Frontend | React 18 · TypeScript · Vite · TanStack Query · Zustand |
| Reverse proxy | nginx |
| Container runtime | Docker Compose |
| CI | GitHub Actions |

## Documentation

- [`docs/MASTER_PLAN.md`](docs/MASTER_PLAN.md) — full system reference (start here)
- [`docs/VISION.md`](docs/VISION.md) — product vision and roadmap
- [`packages/api/CLAUDE.md`](packages/api/CLAUDE.md) — API developer and agent orientation
- [`docs/db/`](docs/db/) — per-model database schema docs

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, branch conventions, and PR requirements.

## Security

See [SECURITY.md](SECURITY.md) for the vulnerability reporting policy.

## License

[MIT](LICENSE) © 2025 Yehuda Briskman
