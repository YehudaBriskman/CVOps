# Blobs Domain

## Purpose

Content-addressed immutable blob store. The SHA-256 hash of a file's contents is the primary key, which means identical bytes are deduplicated automatically — the same file uploaded twice produces exactly one row and one storage object. This domain powers frame storage, model weights, export archives, and thumbnails across the CVOps platform.

---

## Tables

### `blobs`

Stores metadata for every binary object in the system. The hash is the identity; there is no surrogate UUID column.

| Column | Type | Constraints |
|---|---|---|
| `hash` | `TEXT` | `PRIMARY KEY` — format: `sha256:<64-hex>` |
| `storage_backend` | `TEXT` | `NOT NULL` — one of `"s3"`, `"minio"`, `"gcs"` |
| `storage_key` | `TEXT` | `NOT NULL` — path pattern: `blobs/{hash[7:9]}/{hash[9:]}` |
| `size_bytes` | `BIGINT` | `NOT NULL` |
| `media_type` | `TEXT` | `NOT NULL` — MIME type, e.g. `"image/jpeg"`, `"application/zip"` |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, server default `now()` |

> **Note:** This table intentionally has no `id UUID`, `updated_at`, or `deleted_at` columns. The hash is the identity, and blobs are never updated — mutating content would invalidate the hash.

---

### `type_schemas`

Stores versioned JSON Schema definitions for step types, exporters, and other typed entities in the system. Acts as a registry that the executor and UI both consult at runtime.

| Column | Type | Constraints |
|---|---|---|
| `type_key` | `TEXT` | `PRIMARY KEY` — e.g. `"step.extract_frames"`, `"exporter.zip"` |
| `category` | `TEXT` | `NOT NULL` — e.g. `"step"`, `"exporter"` |
| `json_schema` | `JSONB` | `NOT NULL` — the full JSON Schema document |
| `schema_version` | `TEXT` | `NOT NULL`, default `"1"` |
| `ui_hints` | `JSONB` | nullable — display metadata consumed by the frontend |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, server default `now()` |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, server default `now()` |

---

## Key Behaviors and Invariants

- **Immutability.** Once a blob row is inserted it is never updated. The hash is a cryptographic commitment to the content — changing any byte would produce a different hash and therefore a different row.
- **Deduplication.** Because the hash is the primary key, uploading the same file twice is a no-op at the database layer. The storage object is also deduplicated since the key is derived from the hash.
- **Content addressing.** Consumers do not need to track an opaque ID. Any caller who holds the hash can reconstruct the full storage key independently.
- **References.** Blob hashes are used as foreign keys in several tables: `samples.blob_hash`, `samples.thumbnail_hash`, `data_sources.blob_hash`, `model_versions.blob_hash`, and `runs.logs_blob_hash`. Deleting a blob row without first clearing those references will violate FK constraints.

---

## Storage Key Pattern

A blob with hash `sha256:abcdef1234...` is stored at the key:

```
blobs/ab/cdef1234...
```

The prefix `blobs/` scopes blobs away from other storage namespaces. The next two characters (`ab`) form a one-level directory shard, and the rest of the hex string (`cdef1234...`) is the filename.

**Why this matters at scale.** Object stores like MinIO use consistent hashing or key-prefix routing to assign objects to storage nodes. If all keys share a long common prefix (e.g. every key starts with `blobs/sha256:`), all writes can land on the same node or partition. Sharding by the first two hex characters of the hash distributes keys across up to 256 equally likely prefixes (`00`–`ff`), spreading I/O and avoiding a single hot partition.

---

## ORM / Query Examples

The examples below use raw SQL. Adapt to your ORM of choice.

### Insert a blob (idempotent)

```sql
INSERT INTO blobs (hash, storage_backend, storage_key, size_bytes, media_type)
VALUES (
    'sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab',
    'minio',
    'blobs/ab/cdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab',
    204800,
    'image/jpeg'
)
ON CONFLICT (hash) DO NOTHING;
```

`ON CONFLICT (hash) DO NOTHING` makes the insert a safe upsert — calling it twice with the same hash is harmless and returns without an error.

### Look up a blob by hash

```sql
SELECT hash, storage_backend, storage_key, size_bytes, media_type, created_at
FROM blobs
WHERE hash = 'sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab';
```

### Find all blobs larger than X bytes

```sql
SELECT hash, storage_backend, storage_key, size_bytes, media_type
FROM blobs
WHERE size_bytes > 10485760  -- 10 MiB
ORDER BY size_bytes DESC;
```

---

## What NOT To Do

**Never update a blob row.**
The entire model relies on the hash being a permanent identifier for a specific sequence of bytes. Issuing an `UPDATE` on a blob row — even just changing `media_type` — is wrong because the hash would no longer accurately describe the new state. If the content changes, a new hash is computed and a new row is inserted.

```sql
-- WRONG — do not do this
UPDATE blobs SET media_type = 'image/png' WHERE hash = 'sha256:...';
```

**Never delete a blob without running the audited GC check.**
Multiple tables hold foreign key references to blob hashes (`samples`, `data_sources`, `model_versions`, `runs`). A bare `DELETE FROM blobs WHERE hash = '...'` will either fail with a FK violation or, if cascades are configured, silently remove data in dependent tables. Blob deletion must go through the garbage-collection process, which verifies that no live references to the hash remain before removing the row and the corresponding storage object.
