# Samples Domain — DB Layer

## Purpose

A **Sample** is the atomic unit of labeled data — one image, either a video frame or a still. The `extract_frames` pipeline step is responsible for producing samples from raw data sources and persisting them to the database. Everything downstream (annotations, commits, model training) references samples by their `id` or `blob_hash`.

---

## Tables

### `data_sources`

Represents a raw input asset uploaded by a user before any frame extraction has occurred.

| Column | Type | Notes |
|---|---|---|
| *(EntityBase)* | — | `id`, `created_at`, `updated_at` |
| `project_id` | UUID FK → `projects` | Required |
| `type` | TEXT | `"video"` \| `"image_folder"` \| `"external_uri"` |
| `blob_hash` | TEXT FK → `blobs` | Nullable — set after upload completes |
| `external_uri` | TEXT | Nullable — used when `type = "external_uri"` |
| `status` | TEXT | DEFAULT `"pending"` — see lifecycle below |
| `metadata` | JSONB | Nullable — arbitrary user-supplied or ingestion metadata |

**Status lifecycle:** `pending` → `uploaded` → `ingesting` → `ingested` \| `failed`

**Index:** `(project_id, status)` — supports efficient polling for sources that need processing.

---

### `samples`

One row per unique image in a project. Created (and never mutated) by `extract_frames`.

| Column | Type | Notes |
|---|---|---|
| *(EntityBase)* | — | `id`, `created_at`, `updated_at` |
| `project_id` | UUID FK → `projects` | Required |
| `blob_hash` | TEXT FK → `blobs` NOT NULL | Content-addressed reference to the full-resolution image |
| `source_id` | UUID FK → `data_sources` NOT NULL | The source this sample was extracted from |
| `width` | INTEGER NOT NULL | Pixel width of the image |
| `height` | INTEGER NOT NULL | Pixel height of the image |
| `frame_index` | INTEGER | Nullable — `NULL` for stills; 0-based position in the source video for frames |
| `perceptual_hash` | TEXT | Nullable — used for near-duplicate detection |
| `thumbnail_hash` | TEXT FK → `blobs` | Nullable — hash of the 256×256 JPEG preview blob |
| `metadata` | JSONB | Nullable — extra extraction metadata (codec info, timestamps, etc.) |

**Unique constraint:** `(project_id, blob_hash)` — one sample per distinct image per project.

---

## Deduplication Strategy

`extract_frames` applies a two-level deduplication pass before inserting any sample:

1. **Exact hash** — query `SELECT id FROM samples WHERE project_id = ? AND blob_hash = ?`. If a row exists, the frame is byte-for-byte identical to one already stored; skip it entirely.

2. **Perceptual hash** — compute a perceptual hash (e.g. dHash) for the candidate frame and query all existing `perceptual_hash` values for the project. If any existing sample has a Hamming distance below the configured threshold (e.g. `< 8`), the frame is considered a near-duplicate and is also skipped.

Only frames that pass both checks are inserted. This prevents bloating the dataset with repeated background frames in a video while still preserving genuinely distinct images that happen to be visually similar.

---

## Video Frames vs. Still Images

The `frame_index` column distinguishes the two cases:

- **Video frames** — `frame_index` is set to the 0-based position of the frame within the source video (`0`, `1`, `2`, …). Frames from the same source can be ordered by `frame_index ASC` to reconstruct temporal order.
- **Still images** — `frame_index` is `NULL`. A still has no meaningful position within a sequence.

Both cases share the same table and the same downstream annotation flow. Callers that need to distinguish them filter on `frame_index IS NULL` or `frame_index IS NOT NULL`.

---

## Thumbnails

Every sample stores a `thumbnail_hash` pointing to a 256×256 JPEG blob. The thumbnail is generated at extraction time and stored as a first-class blob in the same object store as full-resolution images. The UI uses thumbnail URLs for grid and filmstrip previews, avoiding the cost of fetching full frames until the annotator actually opens one.

A `NULL` `thumbnail_hash` means the thumbnail has not yet been generated (e.g. the source is still ingesting) and the UI should fall back to a placeholder.

---

## Common Query Patterns

**1. Deduplication check before insert (exact hash)**

```sql
SELECT id
FROM samples
WHERE project_id = $1
  AND blob_hash  = $2
LIMIT 1;
```

**2. All frames from a specific data source, in temporal order**

```sql
SELECT id, blob_hash, frame_index, width, height
FROM samples
WHERE source_id = $1
ORDER BY frame_index ASC NULLS LAST;
```

**3. Samples that have never been labeled (no annotation revision exists)**

```sql
SELECT s.id, s.blob_hash, s.thumbnail_hash
FROM samples s
WHERE s.project_id = $1
  AND NOT EXISTS (
    SELECT 1
    FROM annotation_revisions ar
    WHERE ar.sample_id = s.id
  )
ORDER BY s.created_at ASC;
```

---

## ORM Examples

The snippets below assume a SQLAlchemy-style ORM, but the intent maps directly to any query builder.

```python
# Exact dedup check
existing = (
    db.query(Sample.id)
    .filter(Sample.project_id == project_id, Sample.blob_hash == blob_hash)
    .first()
)
if existing:
    continue  # skip duplicate

# Fetch ordered frames for a source
frames = (
    db.query(Sample)
    .filter(Sample.source_id == source_id)
    .order_by(Sample.frame_index.asc().nullslast())
    .all()
)

# Unlabeled samples for a project
unlabeled = (
    db.query(Sample)
    .filter(Sample.project_id == project_id)
    .filter(~Sample.annotation_revisions.any())
    .order_by(Sample.created_at.asc())
    .all()
)
```

---

## What NOT To Do

- **Never update `blob_hash` or `source_id` on an existing sample.** Both fields are set once at creation and are treated as immutable identifiers. Changing them would silently corrupt annotation history and break content-addressed blob references.

- **Never delete a sample that appears in any `commit_samples` row.** Commits are append-only records of the dataset state at a point in time. Removing a committed sample orphans those commit records and makes past dataset snapshots unreproducible. Soft-delete or archive instead, and always check for `commit_samples` references before any removal.
