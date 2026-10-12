import hashlib
import hmac
import json
import socket
from collections.abc import Generator, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations import webhook_sender
from app.integrations.webhook_sender import (
    WebhookResponse,
    WebhookTargetError,
    parse_webhook_url,
    resolve_public_addresses,
    send_webhook,
)
from app.models.activity_event import ActivityEvent
from app.models.membership import MembershipRole
from app.models.webhook import WebhookDelivery, WebhookDeliveryStatus, WebhookEndpoint
from app.services.webhook_service import signing_secret
from app.worker.webhook_worker import WebhookWorker
from tests.conftest import TestingSessionLocal
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import _headers
from tests.test_lead_email_send import (
    FakeEmailProvider,
    _approve,
    _email_settings,
    _override_email,
    _send_path,
)
from tests.test_lead_qualification import ENQUIRY, _override_provider
from tests.test_lead_qualification import FakeStructuredProvider as FakeQualifyProvider
from tests.test_lead_response_draft import DRAFT
from tests.test_lead_response_review import _generate
from tests.test_leads import _auth

BASE = "/api/v1/integrations/webhooks"
URL = "https://hooks.example.com/flowpilot"


class FakeSender:
    def __init__(self, *responses: int | Exception) -> None:
        self.responses = list(responses) or [200]
        self.calls: list[tuple[str, bytes, dict[str, str]]] = []

    def __call__(self, url: str, body: bytes, headers: Mapping[str, str]) -> WebhookResponse:
        self.calls.append((url, body, dict(headers)))
        outcome = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(outcome, Exception):
            raise outcome
        return WebhookResponse(status_code=outcome)


@pytest.fixture
def sender(client: TestClient) -> Generator[FakeSender, None, None]:
    from app.api.v1.integrations import get_webhook_sender
    from app.main import app

    fake = FakeSender()
    app.dependency_overrides[get_webhook_sender] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_webhook_sender, None)


def _endpoint(client: TestClient, token: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": "CRM sync", "url": URL, "events": ["lead.created"]}
    payload.update(overrides)
    response = client.post(BASE, json=payload, headers=_headers(token))
    assert response.status_code == 201, response.text
    return dict(response.json())


def _lead(client: TestClient, token: str, **fields: Any) -> dict[str, Any]:
    response = client.post(
        "/api/v1/leads", json={"name": "Ada Prospect", **fields}, headers=_headers(token)
    )
    assert response.status_code == 200
    return dict(response.json())


def _deliveries(db: Session, organization_id: str) -> list[WebhookDelivery]:
    db.expire_all()
    return list(
        db.scalars(
            select(WebhookDelivery)
            .where(WebhookDelivery.organization_id == organization_id)
            .order_by(WebhookDelivery.created_at)
        )
    )


def _worker(fake: FakeSender) -> WebhookWorker:
    return WebhookWorker(session_factory=TestingSessionLocal, sender=fake)


# URL safety ------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example.com/x",
        "ftp://hooks.example.com/x",
        "https://user:pass@hooks.example.com/x",
        "https://localhost/x",
        "https://api.localhost/x",
        "https://printer.local/x",
        "https://service.internal/x",
        "https://intranet/x",
        "https://127.0.0.1/x",
        "https://10.0.0.5/x",
        "https://192.168.1.1/x",
        "https://169.254.169.254/latest/meta-data",
        "https://100.64.0.1/x",
        "https://[::1]/x",
        "https://[fd00::1]/x",
        "https://[::ffff:127.0.0.1]/x",
        "https://0.0.0.0/x",
        "https://hooks.example.com/x#frag",
        "https://hooks.example.com:99999/x",
        "https:///x",
    ],
)
def test_unsafe_urls_are_rejected(url: str) -> None:
    with pytest.raises(WebhookTargetError):
        parse_webhook_url(url)


def test_public_url_is_accepted() -> None:
    target = parse_webhook_url("https://Hooks.Example.com:8443/in?team=1")
    assert (target.hostname, target.port, target.path) == ("hooks.example.com", 8443, "/in?team=1")


def test_hostnames_resolving_to_private_addresses_are_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_getaddrinfo(host: str, port: int, **_kwargs: Any) -> list[Any]:
        answers = {
            "rebind.example.com": ["93.184.216.34", "127.0.0.1"],
            "metadata.example.com": ["169.254.169.254"],
            "public.example.com": ["93.184.216.34"],
        }[host]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in answers]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(WebhookTargetError, match="private or internal"):
        resolve_public_addresses("rebind.example.com", 443)
    with pytest.raises(WebhookTargetError, match="private or internal"):
        resolve_public_addresses("metadata.example.com", 443)
    assert resolve_public_addresses("public.example.com", 443) == ["93.184.216.34"]


def test_sender_connects_to_the_checked_address(monkeypatch: pytest.MonkeyPatch) -> None:
    connected: list[tuple[str, int]] = []

    def fake_connect(address: tuple[str, int], timeout: float) -> socket.socket:
        connected.append(address)
        raise ConnectionRefusedError

    monkeypatch.setattr(webhook_sender.socket, "create_connection", fake_connect)
    with pytest.raises(WebhookTargetError, match="Could not connect"):
        send_webhook(URL, b"{}", {}, resolver=lambda _host, _port: ["93.184.216.34"])
    assert connected == [("93.184.216.34", 443)]


def test_sender_validates_before_resolving() -> None:
    def resolver(_host: str, _port: int) -> list[str]:
        raise AssertionError("must not resolve an invalid URL")

    with pytest.raises(WebhookTargetError):
        send_webhook("http://hooks.example.com", b"{}", {}, resolver=resolver)


# Endpoint management ---------------------------------------------------------


def test_create_shows_secret_once_and_never_again(client: TestClient, db: Session) -> None:
    token = _auth(client)["access_token"]
    created = _endpoint(client, token, events=["lead.created", "email.sent", "lead.created"])
    secret = created["secret"]
    endpoint = created["endpoint"]
    assert secret.startswith("whsec_") and len(secret) == 70
    assert endpoint["secret_hint"] == secret[-4:]
    assert endpoint["events"] == ["lead.created", "email.sent"]
    assert endpoint["enabled"] is True
    for response in (
        client.get(BASE, headers=_headers(token)),
        client.get(f"{BASE}/{endpoint['id']}", headers=_headers(token)),
    ):
        assert secret not in response.text
    row = db.get(WebhookEndpoint, endpoint["id"])
    assert row is not None
    assert secret not in json.dumps(
        {column.name: str(getattr(row, column.name)) for column in WebhookEndpoint.__table__.c}
    )
    titles = set(db.scalars(select(ActivityEvent.title)))
    assert "Webhook added" in titles


def test_rotate_secret_replaces_it(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    created = _endpoint(client, token)
    rotated = client.post(
        f"{BASE}/{created['endpoint']['id']}/rotate-secret",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    assert rotated.status_code == 200
    assert rotated.json()["secret"] != created["secret"]
    assert rotated.json()["endpoint"]["revision"] == 2
    stale = client.post(
        f"{BASE}/{created['endpoint']['id']}/rotate-secret",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    assert stale.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "x", "url": "http://hooks.example.com", "events": ["lead.created"]},
        {"name": "x", "url": "https://10.1.2.3/hook", "events": ["lead.created"]},
        {"name": "x", "url": URL, "events": ["webhook.test"]},
    ],
)
def test_invalid_endpoints_are_rejected(client: TestClient, payload: dict[str, Any]) -> None:
    token = _auth(client)["access_token"]
    assert client.post(BASE, json=payload, headers=_headers(token)).status_code == 400


def test_schema_validation(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    for payload in (
        {"name": "x", "url": URL, "events": []},
        {"name": "x", "url": URL, "events": ["lead.deleted"]},
        {"name": " ", "url": URL, "events": ["lead.created"]},
        {"name": "x", "url": URL, "events": ["lead.created"], "secret": "mine"},
    ):
        assert client.post(BASE, json=payload, headers=_headers(token)).status_code == 422


def test_members_can_view_but_not_manage(client: TestClient, db: Session) -> None:
    created = _auth(client)
    owner = created["access_token"]
    endpoint = _endpoint(client, owner)["endpoint"]
    member = _add_org_member(
        db, created["organization"]["id"], email="member@example.com", role=MembershipRole.MEMBER
    )
    headers = _headers(member)
    assert client.get(BASE, headers=headers).status_code == 200
    assert client.get(f"{BASE}/{endpoint['id']}/deliveries", headers=headers).status_code == 200
    denied = [
        client.post(
            BASE, json={"name": "x", "url": URL, "events": ["lead.created"]}, headers=headers
        ),
        client.patch(
            f"{BASE}/{endpoint['id']}",
            json={"expected_revision": 1, "enabled": False},
            headers=headers,
        ),
        client.post(
            f"{BASE}/{endpoint['id']}/rotate-secret",
            json={"expected_revision": 1},
            headers=headers,
        ),
        client.post(f"{BASE}/{endpoint['id']}/test", headers=headers),
        client.delete(f"{BASE}/{endpoint['id']}", headers=headers),
    ]
    assert [response.status_code for response in denied] == [403] * 5


def test_other_workspace_cannot_reach_endpoints(client: TestClient, sender: FakeSender) -> None:
    owner = _auth(client)["access_token"]
    endpoint = _endpoint(client, owner)["endpoint"]
    other = _auth(client, email="other@example.com", organization_name="Other")["access_token"]
    headers = _headers(other)
    assert client.get(BASE, headers=headers).json() == []
    for response in (
        client.get(f"{BASE}/{endpoint['id']}", headers=headers),
        client.get(f"{BASE}/{endpoint['id']}/deliveries", headers=headers),
        client.patch(
            f"{BASE}/{endpoint['id']}", json={"expected_revision": 1}, headers=headers
        ),
        client.post(f"{BASE}/{endpoint['id']}/test", headers=headers),
        client.delete(f"{BASE}/{endpoint['id']}", headers=headers),
    ):
        assert response.status_code == 404
    assert sender.calls == []


# Delivery --------------------------------------------------------------------


def test_lead_created_is_queued_for_subscribed_endpoints_only(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    subscribed = _endpoint(client, token)["endpoint"]
    _endpoint(client, token, name="Email only", events=["email.sent"])
    off = _endpoint(client, token, name="Off")["endpoint"]
    client.patch(
        f"{BASE}/{off['id']}",
        json={"expected_revision": 1, "enabled": False},
        headers=_headers(token),
    )
    other = _auth(client, email="other@example.com", organization_name="Other")
    _endpoint(client, other["access_token"])

    lead = _lead(client, token, email="ada@example.com", company="Acme")
    rows = _deliveries(db, org_id)
    assert [(row.endpoint_id, row.event_type, row.status) for row in rows] == [
        (subscribed["id"], "lead.created", "PENDING")
    ]
    data = rows[0].payload["data"]["lead"]
    assert data == {
        "id": lead["id"],
        "name": "Ada Prospect",
        "email": "ada@example.com",
        "company": "Acme",
        "source": "MANUAL",
        "status": "NEW",
    }
    assert _deliveries(db, other["organization"]["id"]) == []


def test_worker_delivers_with_a_verifiable_signature(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    endpoint = _endpoint(client, token)
    _lead(client, token)
    fake = FakeSender(204)
    result = _worker(fake).run_once()
    assert (result.candidates, result.delivered) == (1, 1)
    [(url, body, headers)] = fake.calls
    assert url == URL
    assert headers["FlowPilot-Event"] == "lead.created"
    parts = headers["FlowPilot-Signature"].split(",")
    timestamp, signature = (part.split("=", 1)[1] for part in parts)
    expected = hmac.new(
        endpoint["secret"].encode(), f"{timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()
    assert hmac.compare_digest(signature, expected)
    payload = json.loads(body)
    assert payload["id"] == headers["FlowPilot-Delivery"]
    assert payload["type"] == "lead.created"
    [row] = _deliveries(db, created["organization"]["id"])
    assert row.status == WebhookDeliveryStatus.DELIVERED
    assert row.last_status_code == 204
    assert _worker(fake).run_once().candidates == 0


def test_failures_retry_with_backoff_then_stop(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    _endpoint(client, token)
    _lead(client, token)
    fake = FakeSender(500)
    worker = _worker(fake)
    now = datetime.now(UTC)
    for attempt in range(1, 6):
        result = worker.run_once(now=now)
        assert result.candidates == 1
        [row] = _deliveries(db, org_id)
        assert row.attempts == attempt
        assert row.last_error == "The endpoint responded with HTTP 500"
        if attempt < 5:
            assert row.status == WebhookDeliveryStatus.PENDING
            assert row.next_attempt_at is not None
            assert worker.run_once(now=now).candidates == 0
            next_at = row.next_attempt_at
            now = (next_at if next_at.tzinfo else next_at.replace(tzinfo=UTC)) + timedelta(
                seconds=1
            )
    assert row.status == WebhookDeliveryStatus.FAILED
    assert worker.run_once(now=now + timedelta(days=1)).candidates == 0
    assert len(fake.calls) == 5


def test_redirect_responses_are_not_followed(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    _endpoint(client, token)
    _lead(client, token)
    _worker(FakeSender(302)).run_once()
    [row] = _deliveries(db, created["organization"]["id"])
    assert row.last_error == "Redirects are not followed"
    assert row.status == WebhookDeliveryStatus.PENDING


def test_failed_delivery_can_be_retried_by_a_manager(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    endpoint = _endpoint(client, token)["endpoint"]
    _lead(client, token)
    [row] = _deliveries(db, created["organization"]["id"])
    row.status = WebhookDeliveryStatus.FAILED
    row.attempts = 5
    db.commit()
    response = client.post(
        f"{BASE}/{endpoint['id']}/deliveries/{row.id}/retry", headers=_headers(token)
    )
    assert response.status_code == 200
    assert response.json()["status"] == "PENDING"
    assert _worker(FakeSender(200)).run_once().delivered == 1
    again = client.post(
        f"{BASE}/{endpoint['id']}/deliveries/{row.id}/retry", headers=_headers(token)
    )
    assert again.status_code == 409


def test_turned_off_endpoint_does_not_send_queued_events(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    endpoint = _endpoint(client, token)["endpoint"]
    _lead(client, token)
    client.patch(
        f"{BASE}/{endpoint['id']}",
        json={"expected_revision": 1, "enabled": False},
        headers=_headers(token),
    )
    fake = FakeSender(200)
    _worker(fake).run_once()
    assert fake.calls == []
    [row] = _deliveries(db, created["organization"]["id"])
    assert row.status == WebhookDeliveryStatus.FAILED


def test_send_test_event_contains_no_customer_data(
    client: TestClient, db: Session, sender: FakeSender
) -> None:
    created = _auth(client)
    token = created["access_token"]
    endpoint = _endpoint(client, token)["endpoint"]
    _lead(client, token, email="secret-customer@example.com")
    response = client.post(f"{BASE}/{endpoint['id']}/test", headers=_headers(token))
    assert response.status_code == 200
    assert response.json()["status"] == "DELIVERED"
    assert response.json()["event_type"] == "webhook.test"
    [(_url, body, headers)] = sender.calls
    assert headers["FlowPilot-Event"] == "webhook.test"
    assert b"secret-customer" not in body and b"Ada" not in body

    sender.responses = [WebhookTargetError("Could not connect to the endpoint")]
    failed = client.post(f"{BASE}/{endpoint['id']}/test", headers=_headers(token))
    assert failed.json()["status"] == "FAILED"
    assert failed.json()["last_error"] == "Could not connect to the endpoint"
    log = client.get(f"{BASE}/{endpoint['id']}/deliveries", headers=_headers(token)).json()
    assert log["total"] == 3
    listed = client.get(f"{BASE}/{endpoint['id']}", headers=_headers(token)).json()
    assert listed["delivery_counts"] == {"pending": 1, "delivered": 1, "failed": 1}


def test_qualified_approved_and_sent_events_are_queued(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _email_settings(monkeypatch)
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    _endpoint(
        client, token, events=["lead.qualified", "draft.approved", "email.sent"]
    )
    lead = _lead(client, token, email="ada@example.com")
    _override_provider(client, FakeQualifyProvider())
    qualified = client.post(
        f"/api/v1/leads/{lead['id']}/qualify", json={"enquiry": ENQUIRY}, headers=_headers(token)
    )
    assert qualified.status_code == 200
    draft = _generate(client, token, lead["id"])
    _approve(client, token, lead["id"], str(draft["id"]))
    _override_email(client, FakeEmailProvider())
    sent = client.post(_send_path(lead["id"], str(draft["id"])), json={}, headers=_headers(token))
    assert sent.status_code == 200

    rows = _deliveries(db, org_id)
    assert [row.event_type for row in rows] == ["lead.qualified", "draft.approved", "email.sent"]
    qualified_data = rows[0].payload["data"]
    assert qualified_data["lead_id"] == lead["id"]
    assert qualified_data["qualification"] == "NEEDS_MORE_INFORMATION"
    serialized = json.dumps([row.payload for row in rows])
    assert ENQUIRY not in serialized
    assert DRAFT not in serialized


def test_enqueue_failure_never_breaks_the_event(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = _auth(client)["access_token"]
    _endpoint(client, token)

    def explode(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("app.services.webhook_service.WebhookDelivery", explode)
    assert client.post(
        "/api/v1/leads", json={"name": "Ada"}, headers=_headers(token)
    ).status_code == 200


def test_signing_secret_depends_on_server_key(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = _auth(client)["access_token"]
    created = _endpoint(client, token)
    row = db.get(WebhookEndpoint, created["endpoint"]["id"])
    assert row is not None
    assert signing_secret(row) == created["secret"]
    from app.core.config import settings

    monkeypatch.setattr(settings, "secret_key", "x" * 64)
    assert signing_secret(row) != created["secret"]


def test_webhook_worker_is_off_by_default() -> None:
    from app.core.config import Settings

    assert Settings.model_fields["webhook_worker_enabled"].default is False
