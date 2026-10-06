from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.inbound_email_service import InboundEmailService

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/resend/inbound")
async def receive_resend_inbound(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    payload = await request.body()
    result = InboundEmailService(db).receive(payload, dict(request.headers))
    body: dict[str, str] = {"status": result.status}
    if result.reason is not None:
        body["reason"] = result.reason
    return body
