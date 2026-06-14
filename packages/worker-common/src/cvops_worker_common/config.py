from __future__ import annotations

import os


class WorkerSettings:
    """Worker-specific env vars. Shared infra vars (DATABASE_URL, S3_*, REDIS_URL)
    are read via cvops_api.config.settings — no duplication."""

    REDIS_STREAM: str = os.environ.get("REDIS_STREAM", "")
    WORKER_TOKEN: str = os.environ.get("WORKER_TOKEN", "")
    API_BASE_URL: str = os.environ.get("API_BASE_URL", "http://api:8000")
    WORKER_CONCURRENCY: int = int(os.environ.get("WORKER_CONCURRENCY", "4"))
    ORPHAN_RECOVERY_INTERVAL: int = int(os.environ.get("ORPHAN_RECOVERY_INTERVAL", "60"))
    ORPHAN_PENDING_AGE_SECONDS: int = int(os.environ.get("ORPHAN_PENDING_AGE_SECONDS", "30"))


worker_settings = WorkerSettings()
