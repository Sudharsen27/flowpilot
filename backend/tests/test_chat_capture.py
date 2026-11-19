from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadSource
from tests.test_agent_runtime import _headers
from tests.test_leads import _auth
from tests.test_website_capture import _payload, _settings_payload

CHAT_PATH = "/api/v1/public/organizations/{slug}/chat-enquiries"
SETTINGS = "/api/v1/organizations/current/website-capture"


def test_chat_enquiry_creates_chat_lead(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    slug = created["organization"]["slug"]
    assert (
        client.patch(
            SETTINGS,
            json=_settings_payload(chat_capture_enabled=True),
            headers=_headers(token),
        ).status_code
        == 200
    )
    form = client.get(CHAT_PATH.format(slug=slug))
    assert form.status_code == 200
    response = client.post(CHAT_PATH.format(slug=slug), json=_payload())
    assert response.status_code == 204
    lead = db.scalar(select(Lead).where(Lead.source == LeadSource.CHAT))
    assert lead is not None
    assert lead.source == LeadSource.CHAT


def test_chat_enquiry_disabled_is_unavailable(client: TestClient) -> None:
    created = _auth(client)
    slug = created["organization"]["slug"]
    assert client.get(CHAT_PATH.format(slug=slug)).status_code == 404
