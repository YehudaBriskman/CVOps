"""Tests for ``cvops_worker_common.config.WorkerSettings`` env-var resolution.

NOTE on timing: ``WorkerSettings`` resolves its values from ``os.environ`` in
the *class body* (the attributes are assigned via ``os.environ.get(...)`` when
the module is imported), NOT in ``__init__``. So re-instantiating
``WorkerSettings()`` after changing the env does NOT pick up the new values —
the only way to observe an override is to re-import the module with the env set.
Workers read this once at process start, so the import-time read matches how it
is used; these tests reload the module to drive that resolution path.
"""

from __future__ import annotations

import importlib

import pytest

import cvops_worker_common.config as config_mod


def _reload_with_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]):
    """Reload the config module with ``env`` applied, returning a fresh
    ``WorkerSettings`` instance whose class attributes reflect the env."""
    for var in (
        "REDIS_STREAM",
        "WORKER_TOKEN",
        "API_BASE_URL",
        "WORKER_CONCURRENCY",
        "ORPHAN_RECOVERY_INTERVAL",
        "ORPHAN_PENDING_AGE_SECONDS",
    ):
        monkeypatch.delenv(var, raising=False)
    for key, val in env.items():
        monkeypatch.setenv(key, val)
    reloaded = importlib.reload(config_mod)
    return reloaded.WorkerSettings()


def test_defaults_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    try:
        s = _reload_with_env(monkeypatch, {})

        assert s.REDIS_STREAM == ""
        assert s.WORKER_TOKEN == ""
        assert s.API_BASE_URL == "http://api:8000"
        assert s.WORKER_CONCURRENCY == 4
        assert s.ORPHAN_RECOVERY_INTERVAL == 60
        assert s.ORPHAN_PENDING_AGE_SECONDS == 30
    finally:
        importlib.reload(config_mod)  # restore module-global state for other tests


def test_env_overrides_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    try:
        s = _reload_with_env(
            monkeypatch,
            {
                "REDIS_STREAM": "cvat",
                "WORKER_TOKEN": "s3cr3t",
                "API_BASE_URL": "http://localhost:8000",
                "WORKER_CONCURRENCY": "8",
                "ORPHAN_RECOVERY_INTERVAL": "120",
                "ORPHAN_PENDING_AGE_SECONDS": "45",
            },
        )

        assert s.REDIS_STREAM == "cvat"
        assert s.WORKER_TOKEN == "s3cr3t"
        assert s.API_BASE_URL == "http://localhost:8000"
        assert s.WORKER_CONCURRENCY == 8
        assert s.ORPHAN_RECOVERY_INTERVAL == 120
        assert s.ORPHAN_PENDING_AGE_SECONDS == 45
    finally:
        importlib.reload(config_mod)


def test_int_knobs_are_typed_ints(monkeypatch: pytest.MonkeyPatch) -> None:
    try:
        s = _reload_with_env(
            monkeypatch,
            {
                "WORKER_CONCURRENCY": "2",
                "ORPHAN_RECOVERY_INTERVAL": "10",
                "ORPHAN_PENDING_AGE_SECONDS": "5",
            },
        )

        assert isinstance(s.WORKER_CONCURRENCY, int)
        assert isinstance(s.ORPHAN_RECOVERY_INTERVAL, int)
        assert isinstance(s.ORPHAN_PENDING_AGE_SECONDS, int)
    finally:
        importlib.reload(config_mod)
