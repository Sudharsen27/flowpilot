"""Accept a verified Resend inbound event and store it for one organization.

The message body is untrusted customer content. It is stored as data and is
never treated as an instruction, approval, or permission to send.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    ProviderNotConfiguredError,
)
from app.core.exceptions import (
    ValidationError as AppValidationError,
)
from app.email.resend_webhook import verify_resend_signature
from app.models.inbound_email import InboundEmail, InboundEmailStatus
from app.repositories.inbound_email_repository import InboundEmailRepository
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.inbound_email import InboundAttachmentMeta, ResendInboundEvent

logger = logging.getLogger(__name__)

_EMAIL = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
_BODY_LIMIT = 8000
_ADDRESS_LIMIT = 20
_ATTACHMENT_LIMIT = 20
_NAME_LIMIT = 200

InboundResultStatus = Literal["accepted", "duplicate", "ignored"]


@dataclass(frozen=True)
class InboundEmailResult:
    status: InboundResultStatus
    reason: str | None = None


class InboundEmailService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.emails = InboundEmailRepository(session)
        self.organizations = OrganizationRepository(session)

    def receive(
        self,
        payload: bytes,
        headers: dict[str, str],
    ) -> InboundEmailResult:
        secret = _secret_value(settings.resend_webhook_secret)
        if secret is None:
            logger.info("inbound email webhook rejected reason=not_configured")
            raise ProviderNotConfiguredError("Inbound email webhook is not configured")
        verify_resend_signature(secret=secret, payload=payload, headers=headers)
        event_type = _event_type(payload)
        logger.info("inbound email webhook received event_type=%s", _safe_event_type(event_type))
        if event_type != "email.received":
            logger.info("inbound email webhook ignored reason=unsupported_event")
            return InboundEmailResult(status="ignored", reason="unsupported_event")
        try:
            event = ResendInboundEvent.model_validate_json(payload)
        except ValidationError:
            raise AppValidationError("Inbound email event is invalid") from None
        organization_id = self._organization_id(event.data.to)
        if organization_id is None:
            logger.info("inbound email webhook ignored reason=unresolved_tenant")
            return InboundEmailResult(status="ignored", reason="unresolved_tenant")
        return self._store(organization_id, event)

    def _organization_id(self, recipients: list[str]) -> str | None:
        domain = (settings.resend_inbound_domain or "").strip().lower()
        if not domain:
            return None
        matched: set[str] = set()
        for recipient in recipients:
            address = _email_address(recipient)
            if address is None:
                continue
            local_part, separator, host = address.partition("@")
            if separator != "@" or host != domain:
                continue
            organization = self.organizations.get_by_slug(local_part)
            if organization is not None:
                matched.add(organization.id)
        if len(matched) != 1:
            return None
        return next(iter(matched))

    def _store(self, organization_id: str, event: ResendInboundEvent) -> InboundEmailResult:
        data = event.data
        if "\x00" in data.email_id:
            raise AppValidationError("Inbound email event is invalid")
        message_id = _clean(data.message_id, 500)
        existing = self.emails.get_by_provider_email_id(
            organization_id,
            "resend",
            data.email_id,
        )
        if existing is None and message_id is not None:
            existing = self.emails.get_by_message_id(organization_id, message_id)
        if existing is not None:
            logger.info(
                "inbound email duplicate provider_email_id=%s",
                data.email_id,
            )
            return InboundEmailResult(status="duplicate")
        received_at = data.created_at or event.created_at or datetime.now(UTC)
        row = InboundEmail(
            organization_id=organization_id,
            lead_id=None,
            provider="resend",
            provider_email_id=data.email_id,
            message_id=message_id,
            from_email=_sender(data.from_address),
            to_addresses=_address_json(data.to),
            cc_addresses=_address_json(data.cc),
            bcc_addresses=_address_json(data.bcc),
            subject=_clean(data.subject, 200),
            body_text=_clean(data.text, _BODY_LIMIT),
            body_html=_clean(data.html, _BODY_LIMIT),
            attachment_metadata=_attachment_json(data.attachments),
            status=InboundEmailStatus.RECEIVED,
            received_at=received_at,
        )
        try:
            with self.session.begin_nested():
                self.emails.add(row)
                self.session.flush()
        except IntegrityError:
            self.session.rollback()
            logger.info(
                "inbound email duplicate provider_email_id=%s",
                data.email_id,
            )
            return InboundEmailResult(status="duplicate")
        self.session.commit()
        logger.info(
            "inbound email stored organization_id=%s provider_email_id=%s",
            organization_id,
            data.email_id,
        )
        return InboundEmailResult(status="accepted")


def _secret_value(secret: SecretStr | None) -> str | None:
    if secret is None:
        return None
    value = secret.get_secret_value().strip()
    return value or None


def _safe_event_type(event_type: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", event_type):
        return event_type
    return "unrecognized"


def _event_type(payload: bytes) -> str:
    try:
        parsed: Any = json.loads(payload)
    except json.JSONDecodeError:
        raise AppValidationError("Inbound email event is invalid") from None
    if not isinstance(parsed, dict):
        raise AppValidationError("Inbound email event is invalid")
    event_type = parsed.get("type")
    if not isinstance(event_type, str) or not event_type:
        raise AppValidationError("Inbound email event is invalid")
    return event_type


def _sender(value: str) -> str:
    sender = _email_address(value) or _clean(value, 320)
    if sender is None:
        raise AppValidationError("Inbound email event is invalid")
    return sender


def _email_address(value: str) -> str | None:
    """Return one mailbox, never an address embedded in a display name."""
    candidate = value.strip()
    if "<" in candidate:
        start = candidate.find("<")
        end = candidate.find(">", start + 1)
        if end == -1:
            return None
        candidate = candidate[start + 1 : end]
    candidate = candidate.strip().lower()
    if _EMAIL.fullmatch(candidate) is None:
        return None
    return candidate


def _address_json(values: list[str]) -> str:
    addresses: list[str] = []
    for value in values[:_ADDRESS_LIMIT]:
        address = _email_address(value)
        if address is not None and address not in addresses:
            addresses.append(address)
    return json.dumps(addresses)


def _attachment_json(attachments: list[InboundAttachmentMeta]) -> str | None:
    safe: list[dict[str, str]] = []
    for item in attachments[:_ATTACHMENT_LIMIT]:
        record: dict[str, str] = {}
        filename = _clean(item.filename, _NAME_LIMIT)
        content_type = _clean(item.content_type, 200)
        disposition = _clean(item.content_disposition, 50)
        if filename is not None:
            record["filename"] = filename
        if content_type is not None:
            record["content_type"] = content_type
        if disposition is not None:
            record["content_disposition"] = disposition
        if record:
            safe.append(record)
    if not safe:
        return None
    return json.dumps(safe)


def _clean(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = value.replace("\x00", "").strip()
    if not cleaned:
        return None
    return cleaned[:limit]
