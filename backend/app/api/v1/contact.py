from fastapi import APIRouter, Request
from pydantic import ValidationError as ModelValidationError

from app.core.exceptions import ValidationError
from app.schemas.contact import ContactAccepted, ContactSubmission
from app.services.contact_notification_service import ContactNotificationService

router = APIRouter(prefix="/api/v1/public", tags=["contact"])

_MAX_BODY_BYTES = 16_384
_REJECTED = "The contact form could not be accepted."


def _client_key(request: Request) -> str:
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


@router.post("/contact", response_model=ContactAccepted)
async def submit_contact(request: Request) -> ContactAccepted:
    media = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media != "application/json":
        raise ValidationError(_REJECTED)
    raw = await request.body()
    if not raw or len(raw) > _MAX_BODY_BYTES:
        raise ValidationError(_REJECTED)
    try:
        payload = ContactSubmission.model_validate_json(raw)
    except ModelValidationError:
        raise ValidationError(_REJECTED) from None
    confirmation_sent = ContactNotificationService().submit(
        payload, client_key=_client_key(request)
    )
    return ContactAccepted(confirmation_sent=confirmation_sent)
