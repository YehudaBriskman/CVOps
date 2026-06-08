# Auth Domain — DB Layer

## Purpose

The auth domain is the multi-tenant root of CVOps. It owns three tables:

- **`orgs`** — tenant root; every other resource is scoped to an org.
- **`users`** — human identities; globally unique by email, may belong to many orgs.
- **`memberships`** — join table that binds a user to an org with a specific role.

---

## Tables

### `orgs`

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK, auto-generated (`gen_random_uuid()`) |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, server default `now()` |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, server default `now()`, auto-updated on write |
| `created_by` | `UUID` | nullable (user id, no FK enforced at DB level) |
| `deleted_at` | `TIMESTAMPTZ` | nullable, indexed — soft-delete marker |
| `name` | `TEXT` | NOT NULL, UNIQUE |
| `settings` | `JSONB` | nullable — org-level feature flags / config |

---

### `users`

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK, auto-generated |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, server default `now()` |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, server default `now()`, auto-updated on write |
| `created_by` | `UUID` | nullable |
| `deleted_at` | `TIMESTAMPTZ` | nullable, indexed — soft-delete marker |
| `org_id` | `UUID` | FK → `orgs.id` (home/primary org) |
| `email` | `TEXT` | NOT NULL, UNIQUE |
| `password_hash` | `TEXT` | nullable — NULL for SSO-only accounts |
| `is_active` | `BOOL` | NOT NULL, DEFAULT `true` |

---

### `memberships`

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK, auto-generated |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, server default `now()` |
| `org_id` | `UUID` | NOT NULL, FK → `orgs.id` |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` |
| `role` | `TEXT` | NOT NULL — see roles below |

**Unique constraint:** `(org_id, user_id)` — one membership row per org per user.

**Valid roles:** `"owner"` | `"maintainer"` | `"annotator"` | `"viewer"`

---

## Key Behaviors and Invariants

- **Soft-delete:** `deleted_at IS NULL` means the row is live. Always filter with `WHERE deleted_at IS NULL` in queries that should exclude deleted records. Never rely on application-layer filtering alone.
- **Org name uniqueness:** `name` is UNIQUE across all orgs globally. A deleted org's name is still reserved until the row is hard-deleted (which should be rare — see warnings below).
- **User email uniqueness:** `email` is UNIQUE across all users globally, regardless of org.
- **Multi-org membership:** A user can belong to multiple orgs. Each additional org membership is a separate row in `memberships`. The `org_id` on `users` is the primary/home org only.
- **SSO support:** `password_hash` is nullable. A NULL value means the account authenticates via SSO; no password-based login is possible for that user.
- **Soft-disable:** Setting `is_active = false` disables login without removing the user or their associated audit history, runs, or annotations.

---

## Common Query Patterns

**All active orgs:**
```sql
SELECT * FROM orgs
WHERE deleted_at IS NULL;
```

**All orgs a user belongs to (via membership):**
```sql
SELECT o.*
FROM orgs o
JOIN memberships m ON m.org_id = o.id
WHERE m.user_id = :user_id
  AND o.deleted_at IS NULL;
```

**A user's role in a specific org:**
```sql
SELECT role
FROM memberships
WHERE org_id = :org_id
  AND user_id = :user_id;
```

**Active, non-disabled users in an org:**
```sql
SELECT u.*
FROM users u
JOIN memberships m ON m.user_id = u.id
WHERE m.org_id = :org_id
  AND u.deleted_at IS NULL
  AND u.is_active = true;
```

---

## ORM Examples (SQLAlchemy 2.0 async)

### Create an Org

```python
async def create_org(session: AsyncSession, name: str, created_by: UUID | None = None) -> Org:
    org = Org(name=name, created_by=created_by)
    session.add(org)
    await session.flush()  # populates org.id without committing
    return org
```

### Create a User with a home Org

```python
async def create_user(
    session: AsyncSession,
    org_id: UUID,
    email: str,
    hashed_password: str | None = None,
) -> User:
    user = User(org_id=org_id, email=email, password_hash=hashed_password)
    session.add(user)
    await session.flush()
    return user
```

### Create a Membership

```python
async def add_member(
    session: AsyncSession,
    org_id: UUID,
    user_id: UUID,
    role: str,
) -> Membership:
    membership = Membership(org_id=org_id, user_id=user_id, role=role)
    session.add(membership)
    await session.flush()
    return membership
```

### Check if a User is a Member of an Org

```python
async def get_membership(
    session: AsyncSession,
    org_id: UUID,
    user_id: UUID,
) -> Membership | None:
    result = await session.execute(
        select(Membership).where(
            Membership.org_id == org_id,
            Membership.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()
```

---

## What NOT To Do

- **Never hard-delete an org or user** if any audit events, projects, pipeline runs, or annotations reference them. Use soft-delete (`deleted_at = now()`) instead.
- **Never reuse a deleted org's name.** The UNIQUE constraint on `orgs.name` prevents it as long as the row exists. If a hard-delete ever occurs, confirm no dependent data remains first.
- **Never store plain-text passwords.** Always hash with `passlib` (e.g., `bcrypt` scheme) before setting `password_hash`. The column stores the hash string, never the raw credential.
- **Never bypass `is_active`** when authenticating users. Always check `is_active = true` alongside `deleted_at IS NULL` before issuing tokens.
- **Never skip the `deleted_at IS NULL` filter** in application queries. Deleted orgs and users must remain invisible to normal operations without requiring physical removal.
