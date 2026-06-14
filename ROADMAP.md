# CVOps — State of the Repo & Roadmap

Living document. Last full audit: 2026-06-11.
For frontend-specific design plan, see [`PLAN.md`](./PLAN.md).
For product vision and the full data model, see [`docs/MASTER_PLAN.md`](./docs/MASTER_PLAN.md).

---

## TL;DR

**API is the most mature layer.** Every router defined in the data model spec is implemented, the workflow engine is end-to-end functional (topological sort, idempotency via input-hash, gate suspend/resume, ref resolution), auth is wired everywhere except `/auth/*` and `/internal/*`, and the DB has 22 ORM models all covered by a single Alembic migration. The only API gap that blocks workflow execution is that **all six step implementations in `packages/steps` raise `NotImplementedError`** — the engine has nothing to run yet.

**Frontend is mostly scaffolding.** 13 of 15 pages return empty or placeholder content. No react-query hooks are defined anywhere in the codebase. No SSE client. The Project Dashboard, Run View, and Workflow Builder — the three load-bearing screens — are stubs. The design-token migration shipped only for `Header.tsx`; every other component still hard-codes raw colors. Tests: zero.

**Phase-2 plumbing is doc-only.** The Celery worker container exists, has no tasks registered, and is not invoked from anywhere. The model-deployer service works end-to-end for a happy path but has no auth on `POST /deploy`, no idempotency, hardcoded credentials, and zero logging.

**Production-readiness is far away.** No TLS termination, no observability (no logging library, metrics, or tracing), no secret manager, no DB backup story, no Kubernetes manifests, no CI for frontend/worker/model-deployer, model-deployer container runs as root.

**Net assessment:** Phase 1 (single-tenant, dev environment, manual ops) is ~60% complete. Phase 2 (async workers, full CVAT loop, multi-user) is ~15% complete. Production deployment (TLS, secrets, k8s, observability, backup) is ~5% complete.

---

## 1. Completeness matrix

| Area | Implementation | Tests | CI | Notes |
|---|---|---|---|---|
| API — routers | ~95% | DB-only ~85% / router ~5% | Yes | 1 stub: `/internal/cvat/webhook` |
| API — workflow engine | 100% | Core only | Yes | Production-ready |
| API — auth + JTI blacklist | 100% | DB only | Yes | RBAC layer is a stub file |
| API — storage backend (Garage) | 100% | Yes | Yes | Presigned URLs working |
| API — audit log (`emit_event`) | 100% (helper) / ~5% (callers) | Yes | Yes | Only the executor calls it; routers don't |
| `packages/steps` — implementations | 0% | 0% | None | 6 classes, all `NotImplementedError` |
| `services/worker` — Celery tasks | 0% | 0% | None | Container shell only; no tasks; no bridge from API |
| `services/model-deployer` | 80% | 0% | None | Works; needs auth, idempotency, secrets, logging |
| `services/frontend` — pages | ~15% | 0% | **None** | 13/15 are stubs; Header is the only real component |
| `services/frontend` — data fetching | 0% | — | — | No react-query hooks anywhere |
| `services/frontend` — SSE/live | 0% | — | — | No EventSource setup |
| `services/frontend` — design tokens | ~5% | — | — | Migration done only for Header |
| `services/frontend` — auth wiring | 0% | — | — | Login/Register pages are empty |
| `tools/frame-extractor` | Functional CLI | 0% | None | Talks to MinIO/PG directly; needs porting into the engine |
| `services/cvat` (submodule) | Vendored | — | — | Pinned to commit; no tag |
| Observability (logs, metrics, traces) | 0% | — | — | None of: structlog, OTel, Prometheus, Sentry |
| Secrets & TLS | 0% | — | — | `.env` in repo; nginx is plain http |
| Container hygiene | ~70% | — | — | model-deployer runs as root; api/worker lack `.dockerignore` |
| CI/CD | API only | — | — | No workflows for frontend, worker, model-deployer; no image build/push |
| Deployment manifests | None | — | — | Compose only; no Helm, no k8s |
| DB backup | None | — | — | Local volume; no WAL archive or snapshots |

---

## 2. Gaps by severity

### P0 — Broken or unsafe

| # | Area | Gap | Evidence |
|---|---|---|---|
| 1 | `packages/steps` | All 6 step implementations are `NotImplementedError`. The engine cannot execute any real workflow. | `packages/steps/src/cvops_steps/` — every file |
| 2 | Frontend | No data fetching. All list pages render hardcoded placeholders; `lib/api/{projects,runs,datasets}.ts` are empty exports labelled `Phase 1: E11`. | `services/frontend/src/api/*.ts`, every `pages/*.tsx` |
| 3 | Frontend — Run View | No SSE subscription to `/runs/:id/events/stream`. Users cannot watch a run progress in real time. | `services/frontend/src/pages/RunView.tsx` (placeholder text only) |
| 4 | Frontend — auth | Login/Register are empty (`return null`). No JWT capture, no refresh interceptor in `lib/client.ts`. | `services/frontend/src/pages/{Login,Register}.tsx`, `lib/client.ts` |
| 5 | model-deployer | `POST /deploy` has no auth. Anyone reaching the container can deploy arbitrary `.pt` files and trigger Docker builds. | `services/model-deployer/app.py:28–44` |
| 6 | model-deployer | Runs as root in the container — violates the project's non-root rule. | `services/model-deployer/Dockerfile` (no final `USER`) |
| 7 | Secrets | CVAT password `Admin1234!` and other defaults baked into source. No env validation at startup. | `services/model-deployer/cvat_client.py:14–16`, `services/api/src/cvops_api/config.py:21,25` |
| 8 | Frontend lint | `package.json` runs `eslint src` but no eslint config file exists. Lint is silently a no-op. | `services/frontend/package.json:10` |
| 9 | Pre-commit hooks | `.githooks/pre-commit` references `black` and `flake8` — the API moved to `ruff` long ago. Hook never matches the current toolchain. | `.githooks/pre-commit` |

### P1 — Missing core feature for Phase 1 release

| # | Area | Gap |
|---|---|---|
| 10 | API — `/internal/cvat/webhook` | Returns `{"received":"ok"}` placeholder; needs to look up the `LabelingJob`, fetch annotations from CVAT, insert `AnnotationRevision` rows, and resume the parked run. |
| 11 | API — audit log integration | `emit_event()` is only called by the executor. Dataset commits, ref advances, model creation, training-container changes don't emit events; the activity feed will be empty. |
| 12 | API — router test coverage | 14 routers; only `/internal` has endpoint tests. The 147-test suite is almost all DB-layer. Cursor pagination, auth dependency, multi-tenancy filtering, and soft-delete behavior have no integration coverage. |
| 13 | Frontend — Project Dashboard (`/projects/:id`) | The product's actual home screen is a placeholder. Per `PLAN.md §4` it needs active-runs (live), recent commits, data growth sparkline, pending gates. |
| 14 | Frontend — Workflow Builder | Canvas renders a hardcoded demo DAG. No `/workflows` load/save, no registry-driven nodes, no `@rjsf` inspector, no run overlay. |
| 15 | Frontend — Files (Data Source detail) | Route + virtualized thumbnail grid don't exist. Cursor pagination on samples isn't wired. |
| 16 | Frontend — design token migration | Only `Header.tsx` uses the semantic tokens. Sidebar, all pages, and step components hardcode `text-mist`, `bg-cobalt`, `text-ink`, `bg-white`, `bg-slate-50`. Dark mode is broken on every screen except the top bar. |
| 17 | Frontend — Layout responsive collapse | Sidebar is fixed `w-60`; no `<1280px` icon-rail collapse, no `<768px` drawer, no read-only mobile variant. |
| 18 | Steps — CLI port to engine | `tools/frame-extractor/{extract_frames,cvat_autolabel}.py` are functional pipelines that bypass the API. They need to be wrapped as `Step` subclasses using `StepContext.storage` and `StepContext.session`. |
| 19 | model-deployer | No idempotency on `nuctl deploy`. Retries create duplicate images/functions. No exponential backoff or user-configurable polling timeout. |
| 20 | model-deployer | Hardcoded 10-minute polling cap (120 × 5s) for CVAT inference completion; exceptions in `task.upload_data()` and `create_requests()` not caught. |
| 21 | Observability | Zero logging library configured anywhere. No structured logs, no Sentry, no correlation IDs between API → deployer → CVAT. When a run hangs in production, no one knows why. |
| 22 | Tests — frontend | No test framework. TypeScript strict is on but only catches type errors. No vitest, no Playwright, no a11y. |
| 23 | CI/CD coverage | `.github/workflows/` only covers the API. Frontend can ship broken builds; worker can fail at deploy; no image build/push pipeline. |
| 24 | API Dockerfile + Frontend Dockerfile | `pip install` without version pin; `npm install` (not `npm ci --frozen-lockfile`) — non-deterministic builds. |
| 25 | Worker Dockerfile | Single-stage, all build deps baked in. Compare to API's two-stage. |
| 26 | Worker bridge | The API still uses `BackgroundTasks` to run workflows. Even after stub step implementations land, scaling beyond a handful of concurrent workflows will block the API event loop. |

### P2 — Required for production deployment

| # | Area | Gap |
|---|---|---|
| 27 | TLS | nginx terminates plain `http:8080`. JWTs travel unencrypted. |
| 28 | Secret management | `.env` lives in `manifests/` and is parsed at compose boot. No HashiCorp Vault / AWS Secrets Manager / k8s Secret integration. |
| 29 | RBAC | `services/api/src/cvops_api/core/rbac.py` is a one-line skeleton. Routers enforce `org_id` filtering but not role-based access. Owner/editor/viewer roles defined in the schema are never checked. |
| 30 | Healthchecks on app services | Infra (postgres, redis, garage) have healthchecks; `api`, `worker`, `frontend`, `nginx` do not. Rolling updates hang silently. |
| 31 | Base image pinning | `postgres:16-alpine`, `redis:7-alpine`, `nginxinc/nginx-unprivileged:1.27-alpine` use major.minor; patch drift breaks determinism. |
| 32 | DB backup | `postgres_data:`, `garage_meta:`, `garage_data:` are local named volumes. No WAL archive, no snapshots, no replication. |
| 33 | Kubernetes manifests / Helm | None. For HA / multi-AZ deployment, compose is not the answer. |
| 34 | Submodule pinning | `services/cvat` pinned to a commit, not a tag. No documented update procedure in `CLAUDE.md`. |
| 35 | Blob garbage collection | `S3Backend.delete_blob()` exists but no caller. Storage grows forever. |
| 36 | `.dockerignore` on api/worker | Test fixtures, `.pytest_cache`, `.venv`, git metadata baked into image layers. |
| 37 | model-deployer Python version | Uses `python:3.9-slim` while the rest of the project targets 3.12+. Should align or remove. |

### P3 — Polish / post-launch

- Idempotency key for runs lives inside `run.config` (executor.py:159) — mixes user-supplied step config with engine state. Move to a dedicated column.
- Presigned-URL TTLs hardcoded (GET 900s, PUT 3600s). Move to settings.
- `EventOut` schema may miss event types as routers integrate `emit_event`.
- Docs 11–14 are slightly inconsistent: the original 3-step local pipeline is described alongside the new Nuclio-based flow. Unify.
- Lucide-react not installed; the theme toggle uses inline SVGs.

---

## 3. Phased roadmap

### Phase 1.5 — Close the MVP loop (target: 3-4 weeks)

Goal: a developer can sign up, create a project, ingest a video, watch a workflow run end-to-end against real steps, see the resulting dataset, and the UI shows it all live.

| Order | Task | Owner area |
|---|---|---|
| 1 | Port `extract_frames` from CLI to a `Step` subclass in `packages/steps`. Use `ctx.storage` + `ctx.session`. | Steps team |
| 2 | Port `cvat_autolabel` to a `Step`. | Steps team |
| 3 | Implement `commit_dataset` and `export_yolo` step bodies. | Steps team |
| 4 | Fix the `.githooks/pre-commit` hook to call `ruff` + `tsc`. | DevOps |
| 5 | Add an eslint config (`.eslintrc.json` or flat `eslint.config.js`) for the frontend. | Frontend |
| 6 | Add `vitest` to the frontend (unit) + 5 smoke tests. | Frontend |
| 7 | Build the frontend component primitives backlog from `PLAN.md §2` (Button, Card, Sheet, Dialog, DataTable, EmptyState, StatusBadge, Skeleton, Toast). | Frontend |
| 8 | Migrate the design tokens across Sidebar + Layout + all step components. Verify dark mode end-to-end. | Frontend |
| 9 | Wire react-query hooks for `/projects`, `/projects/:id/data-sources`, `/projects/:id/runs`. Make the Projects, Project Dashboard, and Run View pages real. | Frontend |
| 10 | Wire SSE client for `/runs/:id/events/stream`. Project Dashboard + Run View consume it. | Frontend |
| 11 | Wire Login/Register pages to `/auth/register` + `/auth/token`. Implement 401 → refresh interceptor in `lib/client.ts`. | Frontend |
| 12 | Implement `POST /internal/cvat/webhook` (resolve `LabelingJob`, fetch CVAT annotations, insert `AnnotationRevision`, resume the run). | API |
| 13 | Add router endpoint tests for every router, focusing on cursor pagination, auth dependency, soft-delete filter, multi-tenancy. | API |
| 14 | Integrate `emit_event()` into datasets, models, training-containers routers. | API |

### Phase 2 — Async workers + production hardening of integrations (target: 4-6 weeks after 1.5)

| Order | Task |
|---|---|
| 15 | Wire Celery: register `execute_workflow` as a `@shared_task` in `services/worker`. Change `runs.py` to `delay()` instead of `BackgroundTasks`. Use `WORKER_TOKEN` to authenticate worker → API callbacks. |
| 16 | Add auth + idempotency to `model-deployer/POST /deploy`. Remove hardcoded CVAT password; require explicit env. |
| 17 | Add `structlog` + JSON logging + correlation IDs across api / worker / model-deployer. Pipe to a log aggregator (Loki or CloudWatch). |
| 18 | Implement Workflow Builder (`PLAN.md §6`): registry-driven nodes, rjsf inspector, validation, run-from-step, live run overlay. |
| 19 | Implement Data Mapping editor (`PLAN.md §8`) — reuses the React Flow runtime. |
| 20 | Implement Run View live DAG + gate UI + virtualized log viewer (`PLAN.md §7`). |
| 21 | Implement Files / Data Source detail with virtualized grid (`PLAN.md §5`). |
| 22 | Embed Recharts in Dataset, Model, Run pages (`PLAN.md §9`). |
| 23 | RBAC enforcement layer: implement `core/rbac.py`; add role checks across mutating routers. |

### Phase 3 — Production deployment (target: post-Phase-2)

| Order | Task |
|---|---|
| 24 | Helm chart + k8s manifests (Deployments, Services, Ingress, HPA, PDB, NetworkPolicy). |
| 25 | TLS termination via cert-manager + Let's Encrypt. |
| 26 | Secret management: External Secrets Operator → Vault or AWS Secrets Manager. |
| 27 | DB backup: WAL archive to S3 + nightly base backup; document restore. |
| 28 | Sentry or equivalent for unhandled exceptions. |
| 29 | Prometheus exporters on api / worker / nginx; basic Grafana dashboards. |
| 30 | Blue-green or canary deploy via Argo Rollouts. |
| 31 | Pin all base images to patch level. Add Renovate / Dependabot. |
| 32 | Blob GC job: scan `Sample.blob_hash` + `AnnotationRevision.blob_hash` + `ModelVersion.weights_blob_hash`, delete unreferenced `Blob` rows + objects. |

---

## 4. Quick-win sequence (next 7–10 days)

Pick this up first; each item unblocks others.

1. **Day 1 — Repair the dev quality gates** (90 min)
   - Fix `.githooks/pre-commit` to call `ruff check` and `tsc --noEmit`.
   - Add `services/frontend/eslint.config.js` (flat config) and verify `npm run lint` actually fails on a violation.

2. **Day 1 — Lock the model-deployer down** (60 min)
   - Add a `USER 1001:1001` stage to `services/model-deployer/Dockerfile`.
   - Remove the hardcoded `CVAT_PASSWORD` default; raise at startup if unset.
   - Add bearer-token check to `POST /deploy` using `WORKER_TOKEN`.

3. **Day 2 — Step 1 of the engine loop** (~1 day)
   - Port `extract_frames` to `packages/steps`. Write 3 unit tests against testcontainers.

4. **Day 3 — Frontend primitives** (~2 days)
   - Build `<Button>`, `<Card>`, `<EmptyState>`, `<Skeleton>`, `<StatusBadge>`. Migrate Sidebar to use semantic tokens.

5. **Day 5 — First live screen** (~1 day)
   - Build the Projects list with a real react-query hook. End-to-end smoke: log in, list projects, click into one, see the (stub) Project page.

6. **Day 6 — Auth wiring** (~1 day)
   - Login/Register pages → real form → JWT in localStorage → axios interceptor with 401 refresh.

7. **Day 7 — `/internal/cvat/webhook`** (~0.5 day)
   - Implement the handler; add an integration test that posts a fake CVAT payload and asserts the run resumes.

8. **Day 8 — CI for frontend** (~0.5 day)
   - Add `.github/workflows/ci-frontend.yml` running typecheck, lint, build on PR.

After day 10 you have: real auth, a live list page, one working step, a CVAT-backed annotation loop, and dev quality gates that actually fire. From there, the rest of Phase 1.5 is repeatable application of the same patterns.

---

## 5. Open decisions

These should be resolved before the Phase-2 roadmap is committed:

1. **Worker model.** Stay on Celery, or evaluate `Arq`/`Dramatiq`/`Procrastinate`? Celery is heavy; Procrastinate uses Postgres as the queue (one less moving part).
2. **Observability stack.** Loki+Grafana vs. CloudWatch vs. Datadog vs. self-hosted ELK? The choice constrains everything downstream.
3. **K8s flavor.** Managed (EKS / GKE) or bare-metal (k3s + Rancher)? The Rancher kubeconfig in `~/.kube/config` suggests Rancher is already provisioned.
4. **Frontend a11y test budget.** Manual review per PR vs. Playwright + `@axe-core/playwright` in CI? The second adds time but catches regressions.
5. **Ontology editor shape** (still open from `PLAN.md`).
6. **CVAT submodule update cadence.** Pin to a tag, automate updates via Renovate, or freeze?

---

## 6. Where each section of this doc came from

So you can verify and re-run the analysis:

- API report → file-by-file scan of `services/api/src/cvops_api/{routers,engine,core,db,schemas}/`
- Frontend report → file-by-file scan of `services/frontend/src/{pages,components,api,lib,store}/`
- Engine + steps report → `services/api/src/cvops_api/engine/`, `packages/steps/`, `tools/frame-extractor/`, `docs/11..14`
- Worker + observability report → `services/worker/`, `services/model-deployer/`, grep for logging/metrics across all services
- Infra report → `manifests/`, `.github/workflows/`, `Tiltfile`, all `Dockerfile`s
- Tests report → `services/api/tests/`, frontend test config, lint config

Each scan was independent; findings cross-checked where they overlapped (e.g. router test coverage appears in both API and tests reports). The full reports are reproducible by re-running the same prompts against an Explore agent on a fresh checkout.
