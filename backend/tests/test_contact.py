import logging

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.core.rate_limit import contact_form_limiter
from app.email.provider import EmailMessage
from app.email.resend_provider import ResendEmailProvider
from app.services.contact_notification_service import CONTACT_NOTIFICATION_EMAIL

PATH = "/api/v1/public/contact"


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "company": "Analytical Engines",
        "job_title": "Founder",
        "reason": "demo",
        "message": "We would like to see qualification and approval.",
    }
    body.update(overrides)
    return body


def _configure(monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    sent: list[EmailMessage] = []

    def capture(self: ResendEmailProvider, message: EmailMessage) -> object:
        sent.append(message)
        return type("Result", (), {"provider": "resend", "message_id": "msg_test"})()

    monkeypatch.setattr(settings, "resend_api_key", "re_test_secret")
    monkeypatch.setattr(settings, "email_from_address", "notifications@example.com")
    monkeypatch.setattr(settings, "email_from_name", "FlowPilot")
    monkeypatch.setattr(ResendEmailProvider, "send", capture)
    return sent


def test_valid_contact_is_sent_to_the_fixed_inbox(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    response = client.post(PATH, json=_payload())
    assert response.status_code == 200
    assert response.json() == {"accepted": True, "confirmation_sent": True}
    assert len(sent) == 2
    message = sent[0]
    assert str(message.to) == CONTACT_NOTIFICATION_EMAIL
    assert str(message.from_email) == "notifications@example.com"
    assert message.from_name == "FlowPilot"
    assert str(message.reply_to) == "ada@example.com"
    assert message.subject == "FlowPilot Demo Request — Analytical Engines"
    assert "Ada Lovelace" in message.body_text
    assert "ada@example.com" in message.body_text
    assert "Analytical Engines" in message.body_text
    assert "Founder" in message.body_text
    assert "Request a demo" in message.body_text
    assert "qualification and approval" in message.body_text
    assert message.body_html is not None
    assert "re_test_secret" not in response.text
    assert "qualification and approval" not in response.text
    acknowledgement = sent[1]
    assert str(acknowledgement.to) == "ada@example.com"
    assert str(acknowledgement.reply_to) == CONTACT_NOTIFICATION_EMAIL
    assert acknowledgement.subject == "We received your FlowPilot message"
    assert "Thank you for contacting FlowPilot" in acknowledgement.body_text
    assert "You asked to see a FlowPilot demo." in acknowledgement.body_text
    assert "What happens next" in (acknowledgement.body_html or "")
    assert "qualification and approval" not in acknowledgement.body_text


def test_html_in_the_message_is_escaped(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    response = client.post(
        PATH,
        json=_payload(message='Hello <script>alert("x")</script>'),
    )
    assert response.status_code == 200
    html = sent[0].body_html or ""
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_header_injection_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    response = client.post(
        PATH,
        json=_payload(company="Acme\r\nBcc: attacker@example.com"),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "The contact form could not be accepted."
    assert sent == []
    assert "attacker@example.com" not in response.text


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "   "},
        {"email": "not-an-email"},
        {"company": ""},
        {"reason": "pricing"},
        {"message": ""},
        {"message": "x" * 4001},
        {"name": "n" * 121},
        {"extra": "no"},
    ],
)
def test_invalid_fields_are_rejected(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, object],
) -> None:
    sent = _configure(monkeypatch)
    response = client.post(PATH, json=_payload(**overrides))
    assert response.status_code == 400
    assert sent == []
    assert "re_test_secret" not in response.text


def test_missing_provider_configuration_does_not_report_success(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    monkeypatch.setattr(settings, "resend_api_key", None)
    response = client.post(PATH, json=_payload())
    assert response.status_code == 503
    assert response.json()["detail"] == "We could not send your message. Please try again later."
    assert sent == []
    assert "RESEND" not in response.text


def test_missing_sender_does_not_report_success(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    monkeypatch.setattr(settings, "email_from_address", None)
    response = client.post(PATH, json=_payload())
    assert response.status_code == 503
    assert sent == []


def test_provider_failure_is_a_safe_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail(self: ResendEmailProvider, message: EmailMessage) -> object:
        raise ProviderError("provider secret and the visitor message")

    monkeypatch.setattr(settings, "resend_api_key", "re_test_secret")
    monkeypatch.setattr(settings, "email_from_address", "notifications@example.com")
    monkeypatch.setattr(ResendEmailProvider, "send", fail)
    with caplog.at_level(logging.WARNING):
        response = client.post(PATH, json=_payload(message="Private enquiry text"))
    assert response.status_code == 502
    assert response.json()["detail"] == "We could not send your message. Please try again later."
    assert "Private enquiry text" not in response.text
    assert "provider secret" not in response.text
    combined = " ".join(caplog.messages)
    assert "Private enquiry text" not in combined
    assert "re_test_secret" not in combined
    assert "provider secret" not in combined


def test_acknowledgement_failure_keeps_the_team_notification(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sent: list[EmailMessage] = []

    def capture(self: ResendEmailProvider, message: EmailMessage) -> object:
        if str(message.to) != CONTACT_NOTIFICATION_EMAIL:
            raise ProviderError("cannot send to this recipient")
        sent.append(message)
        return type("Result", (), {"provider": "resend", "message_id": "msg_team"})()

    monkeypatch.setattr(settings, "resend_api_key", "re_test_secret")
    monkeypatch.setattr(settings, "email_from_address", "notifications@example.com")
    monkeypatch.setattr(ResendEmailProvider, "send", capture)
    with caplog.at_level(logging.WARNING):
        response = client.post(PATH, json=_payload())
    assert response.status_code == 200
    assert response.json()["confirmation_sent"] is False
    assert len(sent) == 1
    assert "ada@example.com" not in " ".join(caplog.messages)
    assert "cannot send to this recipient" not in " ".join(caplog.messages)


def test_honeypot_does_not_send(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    response = client.post(PATH, json=_payload(company_website="https://spam.example"))
    assert response.status_code == 200
    assert response.json() == {"accepted": True, "confirmation_sent": False}
    assert sent == []


def test_rate_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    contact_form_limiter.reset()
    monkeypatch.setattr(settings, "contact_rate_limit_max", 1)
    first = client.post(PATH, json=_payload())
    second = client.post(PATH, json=_payload(email="second@example.com"))
    assert first.status_code == 200
    assert second.status_code == 429
    assert "wait" in second.json()["detail"].lower()


def test_unsupported_content_type_and_oversized_body(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    plain = client.post(PATH, content="name=ada", headers={"Content-Type": "text/plain"})
    assert plain.status_code == 400
    oversized = client.post(
        PATH,
        content=b'{"message":"' + (b"a" * 20_000) + b'"}',
        headers={"Content-Type": "application/json"},
    )
    assert oversized.status_code == 400
    assert sent == []


def test_get_is_not_allowed(client: TestClient) -> None:
    response = client.get(PATH)
    assert response.status_code == 405


def test_disallowed_origin_is_not_reflected(client: TestClient) -> None:
    response = client.options(
        PATH,
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") != "https://evil.example"


def test_job_title_is_optional(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _configure(monkeypatch)
    body = _payload()
    del body["job_title"]
    response = client.post(PATH, json=body)
    assert response.status_code == 200
    assert "Not provided" in sent[0].body_text


def test_success_log_omits_message_body(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _configure(monkeypatch)
    with caplog.at_level(logging.INFO):
        response = client.post(PATH, json=_payload(message="Do not log this sentence"))
    assert response.status_code == 200
    combined = " ".join(record.getMessage() for record in caplog.records)
    assert "Do not log this sentence" not in combined
    assert "ada@example.com" not in combined
    assert "re_test_secret" not in combined
