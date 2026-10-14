from __future__ import annotations

import hashlib
import html
import logging

from app.core.config import settings
from app.core.exceptions import (
    ProviderError,
    ProviderNotConfiguredError,
    RateLimitError,
    ValidationError,
)
from app.core.rate_limit import contact_form_limiter
from app.email.headers import safe_header, safe_optional_name
from app.email.provider import EmailMessage, EmailProvider
from app.email.resend_provider import ResendEmailProvider
from app.schemas.contact import ContactReason, ContactSubmission

logger = logging.getLogger(__name__)

CONTACT_NOTIFICATION_EMAIL = "sundarlingam272000@gmail.com"
_SUBJECT_PREFIX = "FlowPilot Demo Request — "
_DELIVERY_ERROR = "We could not send your message. Please try again later."
_REJECTED = "The contact form could not be accepted."
_REASON_LABELS = {
    ContactReason.DEMO: "Request a demo",
    ContactReason.PRODUCT: "Ask about the product",
    ContactReason.OTHER: "Another enquiry",
}
_ACK_DETAIL = {
    ContactReason.DEMO: "You asked to see a FlowPilot demo.",
    ContactReason.PRODUCT: "You asked about the product.",
    ContactReason.OTHER: "You sent a general enquiry.",
}


class ContactNotificationService:
    def submit(self, payload: ContactSubmission, *, client_key: str) -> bool:
        if not contact_form_limiter.allow(
            client_key,
            max_requests=settings.contact_rate_limit_max,
            window_seconds=settings.contact_rate_limit_window_seconds,
        ):
            raise RateLimitError()
        if payload.company_website:
            logger.info("Contact form honeypot discarded")
            return False

        name = _header_value(payload.name)
        email = _header_value(str(payload.email))
        company = _header_value(payload.company)
        job_title = _header_value(payload.job_title) if payload.job_title else None
        message = _message_text(payload.message)
        reason = _REASON_LABELS[payload.reason]
        sender = _configured_sender()
        subject = f"{_SUBJECT_PREFIX}{company}"
        if len(subject) > 200:
            raise ValidationError(_REJECTED)

        fields = [
            ("Name", name),
            ("Email", email),
            ("Company", company),
            ("Job title", job_title or "Not provided"),
            ("Reason", reason),
            ("Message", message),
        ]
        body_text = "\n".join(f"{label}: {value}" for label, value in fields)
        body_html = "".join(
            "<p><strong>"
            + html.escape(label)
            + "</strong><br>"
            + html.escape(value)
            + "</p>"
            for label, value in fields
        )
        digest = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
        provider: EmailProvider = ResendEmailProvider()
        from_name = safe_optional_name(settings.email_from_name) or "FlowPilot"
        _send(
            provider,
            EmailMessage(
                to=CONTACT_NOTIFICATION_EMAIL,
                from_email=sender,
                from_name=from_name,
                reply_to=email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                idempotency_key=f"contact:{digest}",
            ),
        )
        logger.info("Contact notification accepted")
        confirmation_sent = _send_acknowledgement(
            provider,
            sender=sender,
            from_name=from_name,
            visitor_name=name,
            visitor_email=email,
            company=company,
            detail=_ACK_DETAIL[payload.reason],
            digest=digest,
        )
        return confirmation_sent


def _send(provider: EmailProvider, message: EmailMessage) -> None:
    try:
        provider.send(message)
    except ProviderNotConfiguredError:
        logger.warning("Contact notification is not configured")
        raise ProviderNotConfiguredError(_DELIVERY_ERROR) from None
    except ProviderError:
        logger.warning("Contact notification was not delivered")
        raise ProviderError(_DELIVERY_ERROR) from None


def _send_acknowledgement(
    provider: EmailProvider,
    *,
    sender: str,
    from_name: str,
    visitor_name: str,
    visitor_email: str,
    company: str,
    detail: str,
    digest: str,
) -> bool:
    safe_name = html.escape(visitor_name)
    safe_company = html.escape(company)
    safe_detail = html.escape(detail)
    text = (
        f"Hello {visitor_name},\n\n"
        "Thank you for contacting FlowPilot.\n\n"
        f"We received your message from {company}.\n"
        f"{detail}\n\n"
        "What happens next\n"
        "A person from FlowPilot will reply to this email. "
        "There is no need to send it again.\n\n"
        "This confirmation does not create an account, "
        "and nothing is sent to your customers.\n\n"
        "FlowPilot"
    )
    html_body = "".join(
        [
            "<!DOCTYPE html><html lang='en'><body style='margin:0;background:#f4f4f5;'>",
            "<table role='presentation' width='100%' cellpadding='0' cellspacing='0'>",
            "<tr><td align='center' style='padding:32px 16px;'>",
            "<table role='presentation' width='560' cellpadding='0' cellspacing='0' ",
            "style='max-width:560px;background:#ffffff;border:1px solid #e4e4e7;'>",
            "<tr><td style='padding:28px 32px;border-bottom:1px solid #e4e4e7;'>",
            "<p style='margin:0;font-family:Georgia,serif;font-size:22px;color:#18181b;'>",
            "FlowPilot</p>",
            "<p style='margin:8px 0 0;font-family:Arial,sans-serif;font-size:12px;",
            "letter-spacing:1px;text-transform:uppercase;color:#71717a;'>",
            "Message received</p></td></tr>",
            "<tr><td style='padding:28px 32px 8px;font-family:Arial,sans-serif;",
            "font-size:16px;line-height:26px;color:#18181b;'>",
            f"Hello {safe_name},</td></tr>",
            "<tr><td style='padding:8px 32px;font-family:Arial,sans-serif;",
            "font-size:15px;line-height:24px;color:#3f3f46;'>",
            "Thank you for contacting FlowPilot. We received your message from ",
            f"{safe_company}.</td></tr>",
            "<tr><td style='padding:0 32px 20px;font-family:Arial,sans-serif;",
            "font-size:15px;line-height:24px;color:#3f3f46;'>",
            f"{safe_detail}</td></tr>",
            "<tr><td style='padding:0 32px 28px;'>",
            "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' ",
            "style='background:#fafafa;border-left:3px solid #18181b;'>",
            "<tr><td style='padding:16px 18px;font-family:Arial,sans-serif;'>",
            "<p style='margin:0 0 6px;font-size:12px;letter-spacing:1px;",
            "text-transform:uppercase;color:#71717a;'>What happens next</p>",
            "<p style='margin:0;font-size:15px;line-height:24px;color:#18181b;'>",
            "A person from FlowPilot will reply to this email. ",
            "There is no need to send it again.</p>",
            "</td></tr></table></td></tr>",
            "<tr><td style='padding:0 32px 28px;font-family:Arial,sans-serif;",
            "font-size:13px;line-height:20px;color:#71717a;'>",
            "This confirmation does not create an account, ",
            "and nothing is sent to your customers.</td></tr>",
            "</table>",
            "<p style='margin:16px 0 0;font-family:Arial,sans-serif;",
            "font-size:12px;color:#a1a1aa;'>FlowPilot</p>",
            "</td></tr></table></body></html>",
        ]
    )
    try:
        provider.send(
            EmailMessage(
                to=visitor_email,
                from_email=sender,
                from_name=from_name,
                reply_to=CONTACT_NOTIFICATION_EMAIL,
                subject="We received your FlowPilot message",
                body_text=text,
                body_html=html_body,
                idempotency_key=f"contact-ack-v2:{digest}",
            )
        )
    except (ProviderNotConfiguredError, ProviderError):
        logger.warning("Contact acknowledgement was not delivered")
        return False
    logger.info("Contact acknowledgement accepted")
    return True


def _configured_sender() -> str:
    raw = settings.email_from_address or ""
    sender = safe_header(raw)
    if not sender or not settings.resend_api_key:
        logger.warning("Contact notification is not configured")
        raise ProviderNotConfiguredError(_DELIVERY_ERROR)
    return sender


def _header_value(value: str) -> str:
    if any(char in value for char in ("\r", "\n", "\x00")):
        raise ValidationError(_REJECTED)
    cleaned = safe_header(value)
    if not cleaned:
        raise ValidationError(_REJECTED)
    return cleaned


def _message_text(value: str) -> str:
    if "\x00" in value or "\r" in value:
        raise ValidationError(_REJECTED)
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(_REJECTED)
    return cleaned
