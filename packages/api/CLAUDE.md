# CVOps API — Agent & Developer Orientation

## 1. What's Implemented

- 21 SQLAlchemy 2.0 async DB models in `src/cvops_api/db/models/`
- Alembic migration: `alembic/versions/0001_initial_schema.py`
- Fully implemented routers: auth, orgs, projects, data_sources, samples, ontologies, datasets, workflows, runs, models, training_containers, registry
- Workflow engine: executor + ref_resolver in `src/cvops_api/engine/`
- 146-test suite in `tests/` (all passing)
- Per-service DB documentation in `docs/db/`

## 2. Key Shared Dependencies

```python
from cvops_api.db.session import get_session          # AsyncSession per request
from cvops_api.core.auth import get_current_user      # returns User ORM object, raises 401 if invalid
from cvops_api.core.storage import get_storage        # MinIOBackend singleton
from cvops_api.core.audit import emit_event           # append-only event log
from cvops_api.core.registry import registry          # in-memory step registry
```

## 3. Auth

- Bearer JWT (HS256), 15-min access / 7-day refresh
- All endpoints except `/auth/*` require `Authorization: Bearer <token>`
- `get_current_user` dependency handles validation and DB lookup
- Tokens created by `create_access_token(str(user.id))` / `create_refresh_token(str(user.id))`

## 4. Router Mounting (from `main.py`)

| Router | Prefix |
|---|---|
| auth | `/auth` |
| orgs | `/orgs` |
| projects | `/projects` |
| registry | `/registry` |
| internal | `/internal` |
| data_sources, samples, ontologies, datasets, workflows, runs, models, training_containers | `""` (routes define their own full paths, e.g. `/projects/{id}/samples`) |

## 5. Pagination Convention

Cursor-based on all list endpoints. Cursor = base64-encoded UUID of last item.

```
GET /projects/{id}/samples?cursor=<base64>&limit=50
Response: {"items": [...], "next_cursor": "<base64>" | null}
```

Query pattern: `WHERE id > cursor_uuid ORDER BY id LIMIT n+1` — if `n+1` items returned, slice to `n` and encode last id as `next_cursor`.

## 6. Blob Access

Never return raw bytes through the API. Always return presigned URLs:

```python
url = await get_storage().get_presigned_get(blob_hash)   # GET URL, 15-min TTL
url = await get_storage().get_presigned_put(blob_hash)   # PUT URL, 60-min TTL
```

Immutable blobs and commits get `Cache-Control: immutable, max-age=31536000`.

## 7. Soft-Delete Convention

- Most models use `deleted_at: datetime | None`
- Soft-delete by setting `deleted_at = datetime.now(UTC)`
- Always filter `WHERE deleted_at IS NULL` in list queries
- `AnnotationRevision`, `Event`, and `Commit` are append-only — never delete them

## 8. Running Locally

```bash
# Install deps
cd packages/api
pip install -e ".[dev]"
pip install "pydantic[email]"   # required for EmailStr in schemas

# Run tests (spins up postgres via testcontainers — requires Docker)
pytest tests/ -q

# Start dev server
uvicorn cvops_api.main:app --reload --port 8000

# Interactive API docs
open http://localhost:8000/docs
```

## 9. What's NOT Done Yet

- `POST /internal/cvat/webhook` — stub only; Phase 2 CVAT integration pending
- `cvops_steps` package — step implementations (extract_frames, auto_label, etc.) live in a separate package, not in this repo; the workflow engine is ready to execute them once registered

## 10. Adding a New Step Type

1. Create a subclass of `Step` in `cvops_steps` (separate package)
2. Set `type_key`, `config_schema`, `category`, `is_gate`
3. Register via `registry.register(MyStep())` in `cvops_steps.register_all()`
4. The executor picks it up automatically at runtime
