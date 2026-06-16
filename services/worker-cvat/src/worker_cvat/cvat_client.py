"""CVAT-side queries — list deployed Nuclio functions."""
from __future__ import annotations

import json
import os

from cvat_sdk import Client


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} env var is not set")
    return value


CVAT_HOST     = os.environ.get("CVAT_HOST", "http://cvat_server:8080")
CVAT_USERNAME = _require_env("CVAT_USERNAME")
CVAT_PASSWORD = _require_env("CVAT_PASSWORD")


def _client() -> Client:
    import urllib3
    c = Client(url=CVAT_HOST, check_server_version=False)
    c.api_client.configuration.retries = urllib3.Retry(total=0)
    c.api_client.set_default_header("X-Forwarded-Host", "localhost")
    c.api_client.set_default_header("X-Forwarded-Proto", "http")
    c.login((CVAT_USERNAME, CVAT_PASSWORD))
    return c


def list_deployed_models() -> list[dict]:
    """Return all Nuclio functions currently registered in CVAT."""
    from cvat_sdk.api_client.apis import LambdaApi
    client = _client()
    lambda_api = LambdaApi(client.api_client)
    _, resp = lambda_api.list_functions()
    functions = json.loads(resp.data)
    return [
        {
            "id":          fn["id"],
            "name":        fn.get("name", fn["id"]),
            "kind":        fn.get("kind", ""),
            "description": fn.get("description", ""),
        }
        for fn in functions
    ]
