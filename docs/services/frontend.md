# ICD — Frontend

**Owner:** TBD
**Last updated:** 2026-06-11

---

## What it is

React SPA served by Nginx. The user's window into the entire system. Communicates with two backends: the API (all business logic) and MinIO (file bytes via presigned URLs). Never talks to workers, PostgreSQL, Redis, or CVAT directly.

---

## Dependencies at runtime

```
API     REST + SSE
MinIO   presigned URLs for upload and download
```

---

## Environment Variables (build-time, injected via Vite)

```
VITE_API_BASE_URL    /api   (Nginx proxies to api:8000 — no CORS issues)
```

---

## Communicates With

### API — REST

All business logic goes through the API. Base URL `/api`, proxied by Nginx.

```
Auth headers:  Authorization: Bearer <access_token>  on every request
Token refresh: automatic via axios interceptor on 401 response
```

Key interactions:
```
POST /auth/token                       login
POST /auth/refresh                     token refresh
GET  /projects                         list projects
POST /projects                         create project
GET  /registry/types?category=step     load workflow builder palette
POST /projects/{id}/workflows          save workflow
POST /workflows/{id}/runs              start a run
GET  /runs/{id}                        poll run status
GET  /projects/{id}/data-sources       list sources (+ per-source sample_count)
GET  /data-sources/{id}/url            presigned GET for the raw source blob (preview)
GET  /projects/{id}/samples            sample browser (cursor paginated; ?source= filters)
GET  /samples/{id}/thumbnail-url       get presigned thumbnail URL
GET  /samples/{id}/image-url           get presigned full-image URL (lightbox)
GET  /models/{id}                      model detail + MLflow link
```

Full endpoint list: see MASTER_PLAN §12.

### API — SSE

Live run monitoring without polling:

```
GET /api/runs/{id}/events/stream

Opens a persistent connection.
API pushes JSON on every run status transition.
Frontend updates run view in real time.
Connection closes when run reaches terminal state (succeeded / failed / canceled).
```

### MinIO — presigned URLs

The frontend never uploads or downloads files through the API. The API issues a short-lived signed URL and the browser talks to MinIO directly.

**Upload flow:**
```
1. POST /api/projects/{id}/data-sources
   → API returns { data_source, presigned_put_url }
2. Browser PUTs file bytes directly to presigned_put_url (MinIO)
3. POST /api/data-sources/{id}/confirm-upload  { blob_hash }
   → API verifies hash, inserts blobs row, sets status = 'uploaded'
```

**Download flow (images, thumbnails, weights):**
```
1. GET /api/samples/{id}/thumbnail-url
   → API returns { url: "<presigned GET, 1-hr TTL>" }
2. Browser fetches bytes directly from MinIO URL
   img src={url} — browser handles caching
```

**Source preview flow (Data Sources page):**
```
1. GET /api/data-sources/{id}/url
   → API returns { url: "<presigned GET>" } for the original blob
2. Browser renders it directly:
   <video src={url} controls>  for type=video,  <img>  for type=image
The data-sources list carries sample_count per source; the page polls while
any source is still ingesting (no blob yet, or 0 frames) so extracted frames
surface on their own, and links to /projects/{id}/samples?source={id}.
```

---

## Workflow Builder Palette

The palette is built entirely from a single API call — no hardcoded step lists:

```
GET /api/registry/types?category=step

Response:
[
  { type_key: "step.extract_frames",
    ui_hints: { group: "Data Preprocessing", icon: "video",
                description: "Extract frames from a video source", order: 1 },
    json_schema: { ... }   ← rendered as a config form via react-jsonschema-form
  },
  { type_key: "step.auto_label",
    ui_hints: { group: "Data Preprocessing", icon: "sparkles",
                description: "Auto-label with a registered model", order: 2 },
    ...
  },
  { type_key: "step.human_review",
    ui_hints: { group: "Labeling", icon: "user",
                description: "Human annotation via CVAT", order: 1 },
    ...
  },
  ...
]
```

Frontend groups by `ui_hints.group`, sorts by `ui_hints.order` within each group. Adding a new step type to the registry adds it to the palette with zero frontend changes.

---

## Does NOT

```
✗ talk to PostgreSQL directly
✗ talk to Redis
✗ talk to workers
✗ talk to CVAT directly (all CVAT interaction goes through the API)
✗ store credentials anywhere other than localStorage (access_token, refresh_token)
✗ proxy bytes — all file transfers go directly to/from MinIO via presigned URLs
```
