# CVOps

Model-agnostic ML lifecycle dashboard — from raw video to trained model, fully versioned.

```
raw video/images → extract frames → auto-label → human review (CVAT) →
commit dataset → export YOLO → dispatch Docker training → model_version
```

## Quick start

```bash
cp .env.example .env        # fill in secrets
sh scripts/git-setup.sh     # activate git hooks (once per clone)
docker compose up           # starts postgres, minio, redis, api, frontend, nginx
```

API: http://localhost:8000 · Frontend: http://localhost:3000 · MinIO console: http://localhost:9001

## Docs

- [`docs/MASTER_PLAN.md`](docs/MASTER_PLAN.md) — full system reference (start here)
- [`docs/VISION.md`](docs/VISION.md) — product vision
- [`docs/`](docs/) — detailed design docs (01–10)

## Packages

| Package | Language | Purpose |
|---|---|---|
| `packages/api` | Python / FastAPI | REST API, workflow engine, DB layer |
| `packages/steps` | Python | Step implementations (extract, label, export, train) |
| `packages/worker` | Python / Celery | Async worker queue (Phase 2) |
| `packages/frontend` | TypeScript / React | Dashboard UI |

## Branch convention

```
Claude-Bot/<Type>/<5-8-kebab-word-title>
Types: Feat  Fix  Chore  Docs  Refactor  Style  Test  Lint
```
