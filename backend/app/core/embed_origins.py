"""Parse and validate customer website embed origins."""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

_ORIGIN_RE = re.compile(
    r"^https://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?::\d{1,5})?$"
)


def normalize_origin(value: str) -> str | None:
    raw = value.strip()
    if not raw:
        return None
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"}:
        return None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None
    origin = f"https://{parsed.netloc.lower()}"
    if not _ORIGIN_RE.match(origin):
        return None
    return origin


def parse_allowed_origins(stored: str | None) -> list[str]:
    if not stored or not stored.strip():
        return []
    text = stored.strip()
    try:
        loaded = json.loads(text)
        if isinstance(loaded, list):
            values = [str(item) for item in loaded]
        else:
            values = []
    except json.JSONDecodeError:
        values = [part for part in re.split(r"[\n,]+", text) if part.strip()]
    origins: list[str] = []
    seen: set[str] = set()
    for value in values:
        origin = normalize_origin(value)
        if origin and origin not in seen:
            seen.add(origin)
            origins.append(origin)
    return origins


def serialize_allowed_origins(origins: list[str]) -> str | None:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in origins:
        origin = normalize_origin(value)
        if origin and origin not in seen:
            seen.add(origin)
            normalized.append(origin)
    if not normalized:
        return None
    return json.dumps(normalized)


def origin_is_allowed(stored: str | None, origin: str | None) -> bool:
    if not origin:
        return False
    candidate = normalize_origin(origin)
    if candidate is None:
        # Browser Origin header is already a full origin; accept exact https match.
        candidate = origin.strip().lower().rstrip("/")
    return candidate in parse_allowed_origins(stored)
