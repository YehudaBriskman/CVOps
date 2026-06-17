from __future__ import annotations

import base64
import binascii
import uuid

from fastapi import HTTPException

_INVALID_CURSOR_DETAIL = "Invalid pagination cursor"


def _decode_b64(cursor: str) -> str:
    """Base64-decode a cursor to its raw string, 400 on any malformed input."""
    try:
        return base64.b64decode(cursor).decode()
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail=_INVALID_CURSOR_DETAIL) from exc


def decode_cursor_uuid(cursor: str) -> uuid.UUID:
    """Decode a base64-encoded UUID cursor.

    Raises ``HTTPException(400)`` if the cursor is not valid base64, not valid
    UTF-8, or not a valid UUID — so a malformed cursor is a client error, not a 500.
    """
    raw = _decode_b64(cursor)
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_INVALID_CURSOR_DETAIL) from exc


def decode_cursor_parts(cursor: str, sep: str = "|") -> tuple[str, str]:
    """Decode a base64-encoded ``"<head><sep><tail>"`` cursor into its two parts.

    Uses ``str.partition`` so a missing separator yields ``(head, "")`` rather than
    raising. Raises ``HTTPException(400)`` only on a malformed base64/UTF-8 payload;
    interpreting the parts (e.g. parsing a UUID or timestamp) is the caller's job.
    """
    head, _, tail = _decode_b64(cursor).partition(sep)
    return head, tail


def encode_cursor(value: str) -> str:
    """Base64-encode a cursor payload string."""
    return base64.b64encode(value.encode()).decode()
