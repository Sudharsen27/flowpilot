import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import pytest

from app.company_data.data_gov_in_provider import (
    ROC_DATASET_ATTRIBUTION,
    DataGovInRocCompanyDataProvider,
    get_roc_company_data_provider,
)
from app.company_data.provider import (
    CompanyDataProviderError,
    CompanyDataProviderNotConfigured,
)
from app.core.config import Settings, settings

API_KEY = "server-only-test-key"


class MockResponse:
    def __init__(self, payload: object, *, status: int = 200) -> None:
        self.status = status
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "MockResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self.body[:size]


def _provider(request: Any | None = None) -> DataGovInRocCompanyDataProvider:
    return DataGovInRocCompanyDataProvider(
        api_key=API_KEY,
        timeout_seconds=3,
        max_page_size=20,
        max_offset=500,
        request=request,
    )


def test_provider_sends_verified_filter_and_bounded_offset_limit() -> None:
    requests: list[urllib.request.Request] = []
    timeouts: list[float] = []

    def request(http_request: urllib.request.Request, *, timeout: float) -> MockResponse:
        requests.append(http_request)
        timeouts.append(timeout)
        return MockResponse(
            {
                "total": 5,
                "records": [{"CIN": "U12345", "CompanyStateCode": "DL"}],
            }
        )

    page = _provider(request).search(state_code=" DL ", offset=20, limit=10)

    assert len(requests) == 1
    parsed_url = urllib.parse.urlparse(requests[0].full_url)
    query = urllib.parse.parse_qs(parsed_url.query)
    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "api.data.gov.in"
    assert parsed_url.path == f"/resource/{ROC_DATASET_ATTRIBUTION.resource_uuid}"
    assert requests[0].get_method() == "GET"
    assert query == {
        "api-key": [API_KEY],
        "format": ["json"],
        "offset": ["20"],
        "limit": ["10"],
        "filters[CompanyStateCode]": ["DL"],
    }
    assert timeouts == [3]
    assert page.records == ({"CIN": "U12345", "CompanyStateCode": "DL"},)
    assert page.total == 5
    assert page.offset == 20
    assert page.limit == 10
    assert page.attribution == ROC_DATASET_ATTRIBUTION
    assert page.attribution.licensing_status == "PENDING_WRITTEN_CLARIFICATION"


@pytest.mark.parametrize(
    ("state_code", "offset", "limit"),
    [
        (" ", 0, 1),
        ("x" * 11, 0, 1),
        ("DL", -1, 1),
        ("DL", 501, 1),
        ("DL", True, 1),
        ("DL", 0, 0),
        ("DL", 0, 21),
        ("DL", 0, True),
    ],
)
def test_provider_rejects_invalid_filter_and_pagination_without_http(
    state_code: str, offset: int, limit: int
) -> None:
    def unexpected_request(*_args: object, **_kwargs: object) -> MockResponse:
        pytest.fail("Invalid input must not trigger an HTTP request")

    with pytest.raises(ValueError):
        _provider(unexpected_request).search(state_code=state_code, offset=offset, limit=limit)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"records": "not-a-list"},
        {"records": [{"nested": {"invalid": True}}]},
        {"records": [{"bad": float("inf")}]},
        {"records": [{"long": "x" * 10_001}]},
        {"records": [{}] * 2, "total": 2},
        {"records": [], "total": -1},
        {"records": [], "total": True},
    ],
)
def test_provider_rejects_malformed_or_unbounded_responses(payload: object) -> None:
    provider = _provider(lambda *_args, **_kwargs: MockResponse(payload))

    with pytest.raises(CompanyDataProviderError):
        provider.search(state_code="DL", offset=0, limit=1)


def test_provider_rejects_response_larger_than_configured_bound() -> None:
    payload = {"records": [], "unused": "x" * (2 * 1024 * 1024)}
    provider = _provider(lambda *_args, **_kwargs: MockResponse(payload))

    with pytest.raises(CompanyDataProviderError, match="size limit"):
        provider.search(state_code="DL", offset=0, limit=1)


def test_provider_returns_safe_errors_for_http_and_invalid_json() -> None:
    def upstream_failure(*_args: object, **_kwargs: object) -> MockResponse:
        raise OSError(f"upstream URL contained {API_KEY}")

    with pytest.raises(CompanyDataProviderError) as failure:
        _provider(upstream_failure).search(state_code="DL", offset=0, limit=1)
    assert API_KEY not in str(failure.value)

    def upstream_http_error(*_args: object, **_kwargs: object) -> MockResponse:
        raise urllib.error.HTTPError(
            f"{ROC_DATASET_ATTRIBUTION.endpoint}?api-key={API_KEY}",
            503,
            f"failure {API_KEY}",
            {},
            None,
        )

    with pytest.raises(CompanyDataProviderError) as failure:
        _provider(upstream_http_error).search(state_code="DL", offset=0, limit=1)
    assert API_KEY not in str(failure.value)
    assert failure.value.__cause__ is None

    with pytest.raises(CompanyDataProviderError, match="invalid JSON"):
        _provider(lambda *_args, **_kwargs: _InvalidJsonResponse()).search(
            state_code="DL", offset=0, limit=1
        )


def test_provider_returns_timeout_error_without_upstream_details() -> None:
    def timed_out(*_args: object, **_kwargs: object) -> MockResponse:
        raise TimeoutError(f"request timed out for {API_KEY}")

    with pytest.raises(CompanyDataProviderError, match="timed out") as failure:
        _provider(timed_out).search(state_code="DL", offset=0, limit=1)
    assert API_KEY not in str(failure.value)


class _InvalidJsonResponse:
    status = 200

    def __enter__(self) -> "_InvalidJsonResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _size: int = -1) -> bytes:
        return b"not json"


def test_live_provider_factory_is_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "roc_data_gov_in_provider_enabled", False)
    monkeypatch.setattr(settings, "roc_data_gov_in_api_key", None)

    with pytest.raises(CompanyDataProviderNotConfigured, match="disabled"):
        get_roc_company_data_provider()


def test_live_provider_factory_requires_key_and_uses_server_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "roc_data_gov_in_provider_enabled", True)
    monkeypatch.setattr(settings, "roc_data_gov_in_api_key", None)
    with pytest.raises(CompanyDataProviderNotConfigured, match="API_KEY"):
        get_roc_company_data_provider()

    configured = Settings(
        environment="test",
        roc_data_gov_in_api_key=API_KEY,
        roc_data_gov_in_provider_enabled=True,
        _env_file=None,
    )
    monkeypatch.setattr(settings, "roc_data_gov_in_api_key", configured.roc_data_gov_in_api_key)
    provider = get_roc_company_data_provider()
    assert provider._api_key == API_KEY
    assert API_KEY not in repr(configured)


def test_api_key_is_loaded_from_server_environment_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROC_DATA_GOV_IN_API_KEY", API_KEY)
    configured = Settings(environment="test", _env_file=None)

    assert configured.roc_data_gov_in_api_key is not None
    assert configured.roc_data_gov_in_api_key.get_secret_value() == API_KEY
    assert API_KEY not in repr(configured)
