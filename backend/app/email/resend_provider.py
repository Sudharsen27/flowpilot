from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from app.ai.openai_provider import sanitize_provider_error
from app.core.config import settings
from app.core.exceptions import ProviderError, ProviderNotConfiguredError
from app.email.provider import EmailMessage, EmailSendResult

logger = logging.getLogger(__name__)

RESEND_EMAILS_URL = "https://api.resend.com/emails"


class ResendEmailProvider:
    provider_name = "resend"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        request: Any | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.resend_api_key
        self._timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.email_request_timeout_seconds
        )
        self._request = request or urllib.request.urlopen

    def send(self, message: EmailMessage) -> EmailSendResult:
        if not self._api_key:
            raise ProviderNotConfiguredError("RESEND_API_KEY is not configured")

        from_value = message.from_email
        if message.from_name:
            from_value = f"{message.from_name} <{message.from_email}>"
        payload = {
            "from": from_value,
            "to": [str(message.to)],
            "subject": message.subject,
            "text": message.body_text,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if message.idempotency_key:
            headers["Idempotency-Key"] = message.idempotency_key
        request = urllib.request.Request(
            RESEND_EMAILS_URL,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with self._request(request, timeout=self._timeout) as response:
                raw = response.read().decode("utf-8")
                status = getattr(response, "status", 200)
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            logger.warning(
                "Resend request failed: %s",
                sanitize_provider_error(error_body or str(exc)),
            )
            raise ProviderError("Email provider request failed") from exc
        except TimeoutError as exc:
            raise ProviderError("Email provider request timed out") from exc
        except Exception as exc:
            logger.warning("Resend request failed unexpectedly")
            raise ProviderError("Email provider request failed") from exc

        if status >= 400:
            raise ProviderError("Email provider request failed")
        try:
            parsed: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise ProviderError("Email provider returned invalid output") from exc
        message_id = None
        if isinstance(parsed, dict) and isinstance(parsed.get("id"), str):
            message_id = parsed["id"][:200]
        return EmailSendResult(provider=self.provider_name, message_id=message_id)
