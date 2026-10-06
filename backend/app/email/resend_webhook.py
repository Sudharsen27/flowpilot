"""Resend inbound webhooks are signed with the Svix scheme.

https://resend.com/docs/dashboard/webhooks/verify-webhooks-requests
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from collections.abc import Mapping

from app.core.exceptions import UnauthorizedError

_TOLERANCE_SECONDS = 300


def verify_resend_signature(
    *,
    secret: str,
    payload: bytes,
    headers: Mapping[str, str],
    now: float | None = None,
) -> None:
    message_id = _header(headers, "svix-id")
    timestamp = _header(headers, "svix-timestamp")
    signature = _header(headers, "svix-signature")
    if not message_id or not timestamp or not signature:
        raise UnauthorizedError("Missing webhook signature")
    try:
        stamp = int(timestamp)
    except ValueError as exc:
        raise UnauthorizedError("Invalid webhook signature") from exc
    current = time.time() if now is None else now
    if abs(current - stamp) > _TOLERANCE_SECONDS:
        raise UnauthorizedError("Invalid webhook signature")
    try:
        secret_bytes = _secret_bytes(secret)
    except Exception as exc:
        raise UnauthorizedError("Invalid webhook signature") from exc
    signed = f"{message_id}.{timestamp}.".encode() + payload
    expected = base64.b64encode(
        hmac.new(secret_bytes, signed, hashlib.sha256).digest()
    ).decode()
    candidates = [
        part.removeprefix("v1,")
        for part in signature.split(" ")
        if part.startswith("v1,")
    ]
    matched = False
    for item in candidates:
        if len(item) == len(expected) and hmac.compare_digest(expected, item):
            matched = True
            break
    if not matched:
        raise UnauthorizedError("Invalid webhook signature")


def _header(headers: Mapping[str, str], name: str) -> str:
    for key, value in headers.items():
        if key.lower() == name:
            return value.strip()
    return ""


def _secret_bytes(secret: str) -> bytes:
    encoded = secret.removeprefix("whsec_")
    padded = encoded + "=" * (-len(encoded) % 4)
    return base64.b64decode(padded, validate=True)
