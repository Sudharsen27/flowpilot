from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ProviderError, ProviderNotConfiguredError
from app.email.provider import EmailMessage, EmailProvider, EmailSendResult
from app.email.resend_provider import ResendEmailProvider


def test_resend_implements_email_provider() -> None:
    assert isinstance(ResendEmailProvider(api_key="re_test"), EmailProvider)


def test_resend_missing_api_key() -> None:
    provider = ResendEmailProvider(api_key="")
    with pytest.raises(ProviderNotConfiguredError):
        provider.send(
            EmailMessage(
                to="lead@example.com",
                from_email="noreply@example.com",
                subject="Re: Your enquiry",
                body_text="Hello",
            )
        )


def test_resend_success_maps_message_and_idempotency() -> None:
    response = SimpleNamespace(read=lambda: b'{"id": "msg_123"}', status=200)
    context = MagicMock()
    context.__enter__.return_value = response
    context.__exit__.return_value = False
    request_fn = MagicMock(return_value=context)
    provider = ResendEmailProvider(api_key="re_test", request=request_fn, timeout_seconds=12)
    result = provider.send(
        EmailMessage(
            to="lead@example.com",
            from_email="noreply@example.com",
            from_name="FlowPilot",
            subject="Re: Your enquiry",
            body_text="Approved body",
            idempotency_key="org:draft:1",
        )
    )
    assert result == EmailSendResult(provider="resend", message_id="msg_123")
    http_request = request_fn.call_args.args[0]
    assert request_fn.call_args.kwargs["timeout"] == 12
    headers = {key.lower(): value for key, value in http_request.header_items()}
    assert headers["authorization"] == "Bearer re_test"
    assert headers["idempotency-key"] == "org:draft:1"
    body = http_request.data
    assert b"Approved body" in body
    assert b"lead@example.com" in body
    assert b"FlowPilot <noreply@example.com>" in body
    assert b"re_test" not in body


def test_resend_http_error_redacts_invitation_tokens(caplog: pytest.LogCaptureFixture) -> None:
    import urllib.error

    def boom(_request: object, timeout: float) -> object:
        raise urllib.error.HTTPError(
            "https://api.resend.com/emails",
            422,
            "err",
            hdrs={},
            fp=BytesIO(
                b'{"message":"https://app.example.com/invitations/accept?token=super-secret-token"}'
            ),
        )

    provider = ResendEmailProvider(api_key="re_test", request=boom)
    with caplog.at_level("WARNING"), pytest.raises(ProviderError):
        provider.send(
            EmailMessage(
                to="lead@example.com",
                from_email="noreply@example.com",
                subject="Join",
                body_text="Hello",
            )
        )
    assert "super-secret-token" not in caplog.text
    assert "token=[redacted]" in caplog.text


def test_resend_http_error_is_provider_error() -> None:
    import urllib.error

    def boom(_request: object, timeout: float) -> object:
        raise urllib.error.HTTPError(
            "https://api.resend.com/emails",
            500,
            "err",
            hdrs={},
            fp=BytesIO(b'{"message":"secret-key"}'),
        )

    provider = ResendEmailProvider(api_key="re_test", request=boom)
    with pytest.raises(ProviderError, match="Email provider request failed"):
        provider.send(
            EmailMessage(
                to="lead@example.com",
                from_email="noreply@example.com",
                subject="Re: Your enquiry",
                body_text="Hello",
            )
        )


def test_resend_timeout_is_provider_error() -> None:
    def boom(_request: object, timeout: float) -> object:
        raise TimeoutError()

    provider = ResendEmailProvider(api_key="re_test", request=boom)
    with pytest.raises(ProviderError, match="timed out"):
        provider.send(
            EmailMessage(
                to="lead@example.com",
                from_email="noreply@example.com",
                subject="Re: Your enquiry",
                body_text="Hello",
            )
        )


def test_fetch_received_email_maps_text_and_html() -> None:
    response = SimpleNamespace(
        read=lambda: b'{"text":"Hello reply","html":"<p>Hello</p>","id":"email_1"}',
        status=200,
    )
    context = MagicMock()
    context.__enter__.return_value = response
    context.__exit__.return_value = False
    request_fn = MagicMock(return_value=context)
    provider = ResendEmailProvider(api_key="re_test", request=request_fn)
    content = provider.fetch_received_email("email_abc")
    assert content.text == "Hello reply"
    assert content.html == "<p>Hello</p>"
    http_request = request_fn.call_args.args[0]
    assert http_request.full_url.endswith("/emails/receiving/email_abc")
    assert http_request.get_method() == "GET"
    headers = {key.lower(): value for key, value in http_request.header_items()}
    assert headers["authorization"] == "Bearer re_test"


def test_fetch_received_email_http_error_is_provider_error() -> None:
    import urllib.error

    def boom(_request: object, timeout: float) -> object:
        raise urllib.error.HTTPError(
            "https://api.resend.com/emails/receiving/email_1",
            500,
            "err",
            hdrs={},
            fp=BytesIO(b'{"message":"boom"}'),
        )

    provider = ResendEmailProvider(api_key="re_test", request=boom)
    with pytest.raises(ProviderError, match="Email provider request failed"):
        provider.fetch_received_email("email_1")
