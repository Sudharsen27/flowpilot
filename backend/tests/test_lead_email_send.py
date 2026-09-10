from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.email.provider import EmailMessage, EmailSendResult
from app.models.agent_execution import AgentExecution
from app.models.lead import Lead
from app.models.lead_email_send import LeadEmailSend, LeadEmailSendStatus
from app.models.membership import MembershipRole
from app.models.tool_invocation import ToolInvocation
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import _headers
from tests.test_lead_response_draft import (
    DRAFT,
    ENQUIRY,
    FakeStructuredProvider,
    _override_provider,
)
from tests.test_lead_response_review import _generate
from tests.test_leads import _auth, _create

EDITED = "Thanks for writing. This is the approved edited reply."


class FakeEmailProvider:
    def __init__(self, *, fail: Exception | None = None, message_id: str = "msg_1") -> None:
        self.fail = fail
        self.message_id = message_id
        self.messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> EmailSendResult:
        self.messages.append(message)
        if self.fail is not None:
            raise self.fail
        return EmailSendResult(provider="fake-email", message_id=self.message_id)


def _email_settings(monkeypatch: object) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    monkeypatch.setattr(settings, "email_from_name", "FlowPilot")
    monkeypatch.setattr(settings, "resend_api_key", None)


def _override_email(client: TestClient, provider: FakeEmailProvider) -> None:
    from app.api.deps import get_email_provider
    from app.main import app

    app.dependency_overrides[get_email_provider] = lambda: provider
    client.app = app


def _approve(
    client: TestClient, token: str, lead_id: str, draft_id: str, revision: int = 1
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/leads/{lead_id}/response-drafts/{draft_id}/approve",
        json={"expected_revision": revision},
        headers=_headers(token),
    )
    assert response.status_code == 200
    return response.json()


def _send_path(lead_id: str, draft_id: str) -> str:
    return f"/api/v1/leads/{lead_id}/response-drafts/{draft_id}/send"


def test_unauthenticated_send_is_rejected(client: TestClient) -> None:
    assert client.post(_send_path("lead-1", "draft-1"), json={}).status_code == 401


def test_approved_draft_sends_exact_current_response(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    _email_settings(monkeypatch)
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com").json()
    draft = _generate(client, token, lead["id"])
    edited = client.patch(
        f"/api/v1/leads/{lead['id']}/response-drafts/{draft['id']}",
        json={"response": EDITED, "expected_revision": 1},
        headers=_headers(token),
    ).json()
    _approve(client, token, lead["id"], draft["id"], edited["revision"])
    provider = FakeEmailProvider()
    _override_email(client, provider)
    response = client.post(_send_path(lead["id"], draft["id"]), json={}, headers=_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SENT"
    assert body["recipient_email"] == "ada@example.com"
    assert body["sender_email"] == "noreply@example.com"
    assert body["subject"] == "Re: Your enquiry"
    assert body["body_text"] == EDITED
    assert body["provider"] == "fake-email"
    assert body["provider_message_id"] == "msg_1"
    assert body["duration_ms"] is not None
    assert body["error"] is None
    assert "api_key" not in str(body).lower()
    assert provider.messages[0].to == "ada@example.com"
    assert provider.messages[0].from_email == "noreply@example.com"
    assert provider.messages[0].body_text == EDITED
    assert DRAFT not in provider.messages[0].body_text
    row = db.scalar(select(LeadEmailSend))
    assert row is not None
    assert row.status == LeadEmailSendStatus.SENT
    assert row.body_text == EDITED
    lead_row = db.get(Lead, lead["id"])
    assert lead_row is not None
    assert lead_row.status == "NEW"
    assert db.scalar(select(func.count()).select_from(AgentExecution)) == 0
    assert db.scalar(select(func.count()).select_from(ToolInvocation)) == 0


def test_unapproved_states_cannot_send(client: TestClient, monkeypatch: object) -> None:
    _email_settings(monkeypatch)
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com").json()
    generated = _generate(client, token, lead["id"])
    _override_email(client, FakeEmailProvider())
    headers = _headers(token)
    assert (
        client.post(_send_path(lead["id"], generated["id"]), json={}, headers=headers).status_code
        == 409
    )
    edited = client.patch(
        f"/api/v1/leads/{lead['id']}/response-drafts/{generated['id']}",
        json={"response": EDITED, "expected_revision": 1},
        headers=headers,
    ).json()
    assert (
        client.post(_send_path(lead["id"], generated["id"]), json={}, headers=headers).status_code
        == 409
    )
    rejected = client.post(
        f"/api/v1/leads/{lead['id']}/response-drafts/{generated['id']}/reject",
        json={"expected_revision": edited["revision"]},
        headers=headers,
    )
    assert rejected.status_code == 200
    assert (
        client.post(_send_path(lead["id"], generated["id"]), json={}, headers=headers).status_code
        == 409
    )


def test_failed_generation_cannot_send(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    _email_settings(monkeypatch)
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com").json()
    _override_provider(
        client,
        FakeStructuredProvider(fail=ProviderError("AI provider request failed")),
    )
    failed = client.post(
        f"/api/v1/leads/{lead['id']}/respond",
        json={"enquiry": ENQUIRY},
        headers=_headers(token),
    )
    assert failed.status_code == 502
    from app.models.lead_response_draft import LeadResponseDraft, LeadResponseDraftStatus

    stored = db.scalar(select(LeadResponseDraft).where(LeadResponseDraft.lead_id == lead["id"]))
    assert stored is not None
    assert stored.status == LeadResponseDraftStatus.FAILED
    _override_email(client, FakeEmailProvider())
    assert (
        client.post(
            _send_path(lead["id"], stored.id), json={}, headers=_headers(token)
        ).status_code
        == 409
    )


def test_missing_lead_email_is_unprocessable(client: TestClient, monkeypatch: object) -> None:
    _email_settings(monkeypatch)
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    draft = _generate(client, token, lead["id"])
    _approve(client, token, lead["id"], draft["id"])
    _override_email(client, FakeEmailProvider())
    response = client.post(_send_path(lead["id"], draft["id"]), json={}, headers=_headers(token))
    assert response.status_code == 422
    assert "email" in response.json()["detail"].lower()


def test_email_provider_not_configured(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    monkeypatch.setattr(settings, "email_from_address", None)
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com").json()
    draft = _generate(client, token, lead["id"])
    _approve(client, token, lead["id"], draft["id"])
    response = client.post(_send_path(lead["id"], draft["id"]), json={}, headers=_headers(token))
    assert response.status_code == 503
    assert response.json()["detail"] == "Email provider is not configured"
    row = db.scalar(select(LeadEmailSend))
    assert row is not None
    assert row.status == LeadEmailSendStatus.FAILED
    assert row.failure_category == "CONFIGURATION_ERROR"


def test_provider_failure_persists_failed(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    _email_settings(monkeypatch)
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com").json()
    draft = _generate(client, token, lead["id"])
    _approve(client, token, lead["id"], draft["id"])
    _override_email(client, FakeEmailProvider(fail=ProviderError("Email provider request failed")))
    response = client.post(_send_path(lead["id"], draft["id"]), json={}, headers=_headers(token))
    assert response.status_code == 502
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["failure_category"] == "PROVIDER_ERROR"
    assert "sk-" not in str(body)
    row = db.scalar(select(LeadEmailSend))
    assert row is not None
    assert row.status == LeadEmailSendStatus.FAILED
    assert row.error == "Email provider request failed"


def test_client_cannot_choose_recipient_or_sender(
    client: TestClient, monkeypatch: object
) -> None:
    _email_settings(monkeypatch)
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com").json()
    draft = _generate(client, token, lead["id"])
    _approve(client, token, lead["id"], draft["id"])
    _override_email(client, FakeEmailProvider())
    response = client.post(
        _send_path(lead["id"], draft["id"]),
        json={"to": "attacker@example.com", "from": "spoof@example.com"},
        headers=_headers(token),
    )
    assert response.status_code == 422


def test_duplicate_and_already_sent(client: TestClient, monkeypatch: object) -> None:
    _email_settings(monkeypatch)
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com").json()
    draft = _generate(client, token, lead["id"])
    _approve(client, token, lead["id"], draft["id"])
    _override_email(client, FakeEmailProvider())
    first = client.post(_send_path(lead["id"], draft["id"]), json={}, headers=_headers(token))
    assert first.status_code == 200
    second = client.post(_send_path(lead["id"], draft["id"]), json={}, headers=_headers(token))
    assert second.status_code == 409
    assert second.json()["status"] == "SENT"
    assert "already sent" in second.json()["detail"].lower()


def test_pending_send_conflicts(client: TestClient, db: Session, monkeypatch: object) -> None:
    _email_settings(monkeypatch)
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    lead = _create(client, token, email="ada@example.com").json()
    draft = _generate(client, token, lead["id"])
    approved = _approve(client, token, lead["id"], draft["id"])
    db.add(
        LeadEmailSend(
            organization_id=org_id,
            lead_id=lead["id"],
            response_draft_id=draft["id"],
            status=LeadEmailSendStatus.PENDING,
            recipient_email="ada@example.com",
            sender_email="noreply@example.com",
            subject="Re: Your enquiry",
            body_text=DRAFT,
            draft_revision=int(approved["revision"]),
            started_at=datetime.now(UTC),
        )
    )
    db.commit()
    _override_email(client, FakeEmailProvider())
    response = client.post(_send_path(lead["id"], draft["id"]), json={}, headers=_headers(token))
    assert response.status_code == 409
    detail = response.json()["detail"].lower()
    assert "already" in detail or "progress" in detail

def test_member_can_send(client: TestClient, db: Session, monkeypatch: object) -> None:
    _email_settings(monkeypatch)
    created = _auth(client)
    member = _add_org_member(
        db,
        created["organization"]["id"],
        email="member@example.com",
        role=MembershipRole.MEMBER,
    )
    lead = _create(client, created["access_token"], email="ada@example.com").json()
    draft = _generate(client, created["access_token"], lead["id"])
    _approve(client, created["access_token"], lead["id"], draft["id"])
    _override_email(client, FakeEmailProvider())
    response = client.post(
        _send_path(lead["id"], draft["id"]),
        json={},
        headers=_headers(member),
    )
    assert response.status_code == 200


def test_cross_tenant_send_is_not_found(client: TestClient, monkeypatch: object) -> None:
    _email_settings(monkeypatch)
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    lead = _create(client, first["access_token"], email="ada@example.com").json()
    draft = _generate(client, first["access_token"], lead["id"])
    _approve(client, first["access_token"], lead["id"], draft["id"])
    _override_email(client, FakeEmailProvider())
    assert (
        client.post(
            _send_path(lead["id"], draft["id"]),
            json={},
            headers=_headers(second["access_token"]),
        ).status_code
        == 404
    )


def test_edited_after_approve_cannot_send_stale(
    client: TestClient, monkeypatch: object
) -> None:
    _email_settings(monkeypatch)
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com").json()
    draft = _generate(client, token, lead["id"])
    approved = _approve(client, token, lead["id"], draft["id"])
    patched = client.patch(
        f"/api/v1/leads/{lead['id']}/response-drafts/{draft['id']}",
        json={"response": EDITED, "expected_revision": approved["revision"]},
        headers=_headers(token),
    )
    assert patched.status_code == 200
    assert patched.json()["review_status"] == "EDITED"
    _override_email(client, FakeEmailProvider())
    response = client.post(_send_path(lead["id"], draft["id"]), json={}, headers=_headers(token))
    assert response.status_code == 409
