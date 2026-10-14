from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import certifi

from app.core.config import settings
from app.core.exceptions import ProviderError, ProviderNotConfiguredError, ValidationError

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_DELIVERY_ERROR = "Google sign-in is unavailable. Please try again later."
_REJECTED = "Google sign-in could not be completed."


@dataclass(frozen=True)
class GoogleProfile:
    sub: str
    email: str
    name: str
    email_verified: bool


class GoogleOAuthService:
    def __init__(self, *, request: Any | None = None) -> None:
        if request is not None:
            self._request = request
        else:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            self._request = lambda http_request, timeout: urllib.request.urlopen(
                http_request,
                timeout=timeout,
                context=ssl_context,
            )

    def exchange_authorization_code(self, code: str) -> GoogleProfile:
        client_id = (settings.google_oauth_client_id or "").strip()
        secret = settings.google_oauth_client_secret
        client_secret = secret.get_secret_value().strip() if secret is not None else ""
        if not client_id or not client_secret:
            raise ProviderNotConfiguredError("Google sign-in is not configured")

        cleaned = code.strip()
        if not cleaned or len(cleaned) > 2048:
            raise ValidationError(_REJECTED)

        body = urllib.parse.urlencode(
            {
                "code": cleaned,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": "postmessage",
                "grant_type": "authorization_code",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            GOOGLE_TOKEN_URL,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "FlowPilot/0.1",
            },
            method="POST",
        )
        token_payload = self._json_request(request)
        access_token = token_payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ProviderError(_DELIVERY_ERROR)

        info_request = urllib.request.Request(
            GOOGLE_USERINFO_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "FlowPilot/0.1",
            },
            method="GET",
        )
        profile = self._json_request(info_request)
        return self._parse_profile(profile)

    def _json_request(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with self._request(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
                status = getattr(response, "status", 200)
        except urllib.error.HTTPError as exc:
            logger.warning("Google OAuth request failed with HTTP %s", exc.code)
            raise ProviderError(_DELIVERY_ERROR) from exc
        except TimeoutError as exc:
            raise ProviderError(_DELIVERY_ERROR) from exc
        except Exception as exc:
            logger.warning("Google OAuth request failed unexpectedly")
            raise ProviderError(_DELIVERY_ERROR) from exc

        if status >= 400:
            raise ProviderError(_DELIVERY_ERROR)
        try:
            parsed: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise ProviderError(_DELIVERY_ERROR) from exc
        if not isinstance(parsed, dict):
            raise ProviderError(_DELIVERY_ERROR)
        return parsed

    def _parse_profile(self, payload: dict[str, Any]) -> GoogleProfile:
        sub = payload.get("sub")
        email = payload.get("email")
        name = payload.get("name") or payload.get("given_name") or ""
        verified = payload.get("email_verified")
        if not isinstance(sub, str) or not sub.strip() or len(sub) > 255:
            raise ValidationError(_REJECTED)
        if not isinstance(email, str) or "@" not in email or len(email) > 320:
            raise ValidationError(_REJECTED)
        if verified is not True and verified != "true":
            raise ValidationError(_REJECTED)
        display = name.strip() if isinstance(name, str) else ""
        if not display:
            display = email.split("@", 1)[0]
        display = display[:200]
        return GoogleProfile(
            sub=sub.strip(),
            email=email.strip().lower(),
            name=display,
            email_verified=True,
        )
