from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import settings
from app.core.runtime_configuration import build_runtime_configuration
from tests.conftest import register_payload

SECRET_KEY = "sk-test-secret-value"
GROQ_KEY = "gsk_test_secret_value"
TYPESAFE_KEY = "ts_test_secret_value"
RESEND_KEY = "re_test_secret_value"


def _token(client: TestClient) -> str:
    response = client.post("/api/v1/auth/register", json=register_payload())
    assert response.status_code == 200
    return str(response.json()["access_token"])


def test_runtime_configuration_reports_status_without_secrets(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", SECRET_KEY)
    monkeypatch.setattr(settings, "openai_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "typesafe_api_key", SecretStr(TYPESAFE_KEY))
    monkeypatch.setattr(settings, "resend_api_key", RESEND_KEY)
    monkeypatch.setattr(settings, "email_from_address", "sales@example.com")
    token = _token(client)
    response = client.get(
        "/api/v1/runtime/configuration?organization_id=other-org",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "environment"
    assert body["ai_provider"] == "openai"
    assert body["ai_provider_label"] == "OpenAI"
    assert body["ai_model"] == "gpt-4o-mini"
    assert body["ai_status"] == "configured"
    assert body["human_decision_status"] == "configured"
    assert body["email_provider_label"] == "Resend"
    assert body["email_status"] == "configured"
    assert body["sender_address"] == "sales@example.com"
    assert body["sender_status"] == "configured"
    assert "organization_id" not in body
    for secret in (SECRET_KEY, TYPESAFE_KEY, RESEND_KEY):
        assert secret not in response.text


def test_runtime_configuration_reports_missing_providers(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "ai_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", None)
    monkeypatch.setattr(settings, "groq_model", "openai/gpt-oss-20b")
    monkeypatch.setattr(settings, "typesafe_api_key", None)
    monkeypatch.setattr(settings, "resend_api_key", None)
    monkeypatch.setattr(settings, "email_from_address", None)
    token = _token(client)
    response = client.get(
        "/api/v1/runtime/configuration",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ai_provider_label"] == "Groq"
    assert body["ai_model"] == "openai/gpt-oss-20b"
    assert body["ai_status"] == "not_configured"
    assert body["human_decision_status"] == "not_configured"
    assert body["email_status"] == "not_configured"
    assert body["sender_address"] is None
    assert body["sender_status"] == "not_configured"


def test_runtime_configuration_normalizes_inbound_domain(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "resend_inbound_domain", " USTAAZILAI.RESEND.APP ")
    monkeypatch.setattr(settings, "resend_webhook_secret", SecretStr("whsec_test_secret"))
    monkeypatch.setattr(settings, "resend_api_key", RESEND_KEY)
    token = _token(client)
    response = client.get(
        "/api/v1/runtime/configuration",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["resend_inbound_domain"] == "ustaazilai.resend.app"
    assert "whsec_test_secret" not in response.text
    assert RESEND_KEY not in response.text


def test_runtime_configuration_omits_empty_inbound_domain(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "resend_inbound_domain", "   ")
    token = _token(client)
    response = client.get(
        "/api/v1/runtime/configuration",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["resend_inbound_domain"] is None

    monkeypatch.setattr(settings, "resend_inbound_domain", None)
    missing = client.get(
        "/api/v1/runtime/configuration",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing.status_code == 200
    assert missing.json()["resend_inbound_domain"] is None


def test_runtime_configuration_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/runtime/configuration")
    assert response.status_code == 401


def test_runtime_projection_ignores_secret_shaped_sender() -> None:
    from app.core.config import Settings

    configured = Settings(
        environment="test",
        openai_api_key="sk-live-secret",
        email_from_address="not an email sk-live-secret",
        _env_file=None,
    )
    public = build_runtime_configuration(configured)
    dumped = public.model_dump()
    assert dumped["sender_address"] is None
    assert dumped["ai_status"] == "configured"
    assert "sk-live-secret" not in str(dumped)
    assert "api_key" not in dumped
