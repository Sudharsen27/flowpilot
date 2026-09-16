from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.website_capture import PublicEnquiryCreate, PublicEnquiryFormPublic
from app.services.website_capture_service import WebsiteCaptureService

router = APIRouter(prefix="/api/v1/public/organizations", tags=["public-enquiries"])


def _client_key(request: Request) -> str:
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


@router.get("/{slug}/enquiries", response_model=PublicEnquiryFormPublic)
def read_public_enquiry_form(
    slug: str,
    db: Session = Depends(get_db),
) -> PublicEnquiryFormPublic:
    organization = WebsiteCaptureService(db).public_form(slug)
    return PublicEnquiryFormPublic(organization_name=organization.name)


@router.post(
    "/{slug}/enquiries",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def create_public_enquiry(
    slug: str,
    payload: PublicEnquiryCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    WebsiteCaptureService(db).submit_public_enquiry(
        slug=slug,
        client_key=_client_key(request),
        name=payload.name,
        email=str(payload.email),
        company=payload.company,
        enquiry=payload.enquiry,
        honeypot=payload.website,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
