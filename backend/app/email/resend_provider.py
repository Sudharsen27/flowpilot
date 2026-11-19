from __future__ import annotations

import json
import logging
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import certifi

from app.ai.openai_provider import sanitize_provider_error
from app.core.config import settings
from app.core.exceptions import ProviderError, ProviderNotConfiguredError
from app.email.provider import EmailMessage, EmailSendResult

logger = logging.getLogger(__name__)

RESEND_EMAILS_URL = "https://api.resend.com/emails"
RESEND_RECEIVING_URL = "https://api.resend.com/emails/receiving"
_TOKEN_QUERY = re.compile(r"(?i)([?&#]token=)[^&#\s\"']+")


@dataclass(frozen=True)
class ReceivedEmailContent:
    text: str | None = None
    html: str | None = None


def redact_logged_provider_text(message: str) -> str:
    """Remove provider secrets and invitation tokens before a provider error is logged."""
    return _TOKEN_QUERY.sub(r"\1[redacted]", sanitize_provider_error(message))


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
        if request is not None:
            self._request = request
        else:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            self._request = lambda http_request, timeout: urllib.request.urlopen(
                http_request,
                timeout=timeout,
                context=ssl_context,
            )

    def send(self, message: EmailMessage) -> EmailSendResult:
        if not self._api_key:
            raise ProviderNotConfiguredError("RESEND_API_KEY is not configured")

        from_value = message.from_email
        if message.from_name:
            from_value = f"{message.from_name} <{message.from_email}>"
        payload: dict[str, Any] = {
            "from": from_value,
            "to": [str(message.to)],
            "subject": message.subject,
            "text": message.body_text,
        }
        if message.body_html:
            payload["html"] = message.body_html
        if message.reply_to:
            payload["reply_to"] = str(message.reply_to)
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "FlowPilot/0.1",
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
                redact_logged_provider_text(error_body or str(exc)),
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

    def fetch_received_email(self, email_id: str) -> ReceivedEmailContent:
        """Load text/html for a received inbound message (Resend Receiving API)."""
        if not self._api_key:
            raise ProviderNotConfiguredError("RESEND_API_KEY is not configured")
        cleaned_id = email_id.strip()
        if not cleaned_id or "\x00" in cleaned_id or "/" in cleaned_id:
            raise ProviderError("Email provider request failed")
        url = f"{RESEND_RECEIVING_URL}/{urllib.parse.quote(cleaned_id, safe='')}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": "FlowPilot/0.1",
        }
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with self._request(request, timeout=self._timeout) as response:
                raw = response.read().decode("utf-8")
                status = getattr(response, "status", 200)
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            logger.warning(
                "Resend receiving fetch failed: %s",
                redact_logged_provider_text(error_body or str(exc)),
            )
            raise ProviderError("Email provider request failed") from exc
        except TimeoutError as exc:
            raise ProviderError("Email provider request timed out") from exc
        except Exception as exc:
            logger.warning("Resend receiving fetch failed unexpectedly")
            raise ProviderError("Email provider request failed") from exc

        if status >= 400:
            raise ProviderError("Email provider request failed")
        try:
            parsed: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise ProviderError("Email provider returned invalid output") from exc
        if not isinstance(parsed, dict):
            raise ProviderError("Email provider returned invalid output")
        text = parsed.get("text")
        html = parsed.get("html")
        return ReceivedEmailContent(
            text=text if isinstance(text, str) else None,
            html=html if isinstance(html, str) else None,
        )
