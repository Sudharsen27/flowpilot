from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.company_data.data_gov_in_provider import ROC_DATASET_ATTRIBUTION
from app.company_data.provider import (
    CompanyDataPage,
    CompanyDataProviderError,
    CompanyDataRecord,
)
from app.core.config import settings
from app.models.activity_event import ActivityEvent
from app.models.company_prospect import CompanyProspect
from app.models.lead import Lead
from app.models.webhook import WebhookDelivery
from app.models.workflow import WorkflowRun
from tests.test_agent_runtime import _headers
from tests.test_leads import _auth

GOVERNMENT_SEARCH_PATH = "/api/v1/prospect-discovery/government/search"
GOVERNMENT_RECORD: CompanyDataRecord = {
    "CorporateIdentificationNumber": "U12345DL2001PLC123456",
    "CompanyName": "Example Registry Company",
    "CompanyStateCode": "DL",
}


class MockGovernmentProvider:
    def __init__(
        self,
        *,
        records: tuple[CompanyDataRecord, ...] = (GOVERNMENT_RECORD,),
        total: int | None = 5,
        error: Exception | None = None,
    ) -> None:
        self.records = records
        self.total = total
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def search(self, *, state_code: str, offset: int, limit: int) -> CompanyDataPage:
        self.calls.append({"state_code": state_code, "offset": offset, "limit": limit})
        if self.error is not None:
            raise self.error
        return CompanyDataPage(
            records=self.records[:limit],
            total=self.total,
            offset=offset,
            limit=limit,
            attribution=ROC_DATASET_ATTRIBUTION,
        )


def _government_search(
    client: TestClient,
    token: str | None,
    payload: dict[str, Any] | None = None,
):
    headers = _headers(token) if token is not None else {}
    return client.post(
        GOVERNMENT_SEARCH_PATH,
        json=payload or {},
        headers=headers,
    )


def test_government_route_selects_provider_and_returns_attributed_records(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1 import prospect_discovery

    provider = MockGovernmentProvider()
    monkeypatch.setattr(settings, "roc_data_gov_in_provider_enabled", True)
    monkeypatch.setattr(
        prospect_discovery,
        "get_roc_company_data_provider",
        lambda: provider,
    )
    token = _auth(client)["access_token"]

    response = _government_search(
        client,
        token,
        {"state_code": " DL ", "offset": 2, "page_size": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "GOVERNMENT"
    assert body["items"] == [GOVERNMENT_RECORD]
    assert body["offset"] == 2
    assert body["page_size"] == 1
    assert body["total"] == 5
    assert body["has_more"] is True
    assert body["next_offset"] == 3
    assert body["attribution"]["resource_uuid"] == ROC_DATASET_ATTRIBUTION.resource_uuid
    assert body["attribution"]["licensing_status"] == "PENDING_WRITTEN_CLARIFICATION"
    assert provider.calls == [{"state_code": "DL", "offset": 2, "limit": 1}]


def test_government_route_is_authenticated_and_disabled_by_default(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "roc_data_gov_in_provider_enabled", False)
    monkeypatch.setattr(settings, "roc_data_gov_in_api_key", None)

    assert _government_search(client, None, {"state_code": "DL"}).status_code == 401

    token = _auth(client)["access_token"]
    response = _government_search(client, token, {"state_code": "DL"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Government company discovery is unavailable."}


def test_government_route_handles_provider_failures_safely(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1 import prospect_discovery

    provider = MockGovernmentProvider(error=CompanyDataProviderError("secret upstream detail"))
    monkeypatch.setattr(
        prospect_discovery,
        "get_roc_company_data_provider",
        lambda: provider,
    )
    token = _auth(client)["access_token"]

    response = _government_search(client, token, {"state_code": "DL"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Government company discovery is temporarily unavailable."}
    assert "secret upstream detail" not in response.text


def test_government_route_enforces_configured_pagination_bounds(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1 import prospect_discovery

    provider = MockGovernmentProvider()
    monkeypatch.setattr(settings, "roc_data_gov_in_provider_enabled", True)
    monkeypatch.setattr(settings, "roc_data_gov_in_max_page_size", 1)
    monkeypatch.setattr(settings, "roc_data_gov_in_max_offset", 10)
    monkeypatch.setattr(
        prospect_discovery,
        "get_roc_company_data_provider",
        lambda: provider,
    )
    token = _auth(client)["access_token"]

    too_many = _government_search(client, token, {"state_code": "DL", "page_size": 2})
    too_far = _government_search(client, token, {"state_code": "DL", "offset": 11})

    assert too_many.status_code == 422
    assert too_far.status_code == 422
    assert provider.calls == []


def test_government_usage_budget_is_tenant_scoped(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1 import prospect_discovery

    provider = MockGovernmentProvider()
    monkeypatch.setattr(settings, "roc_data_gov_in_provider_enabled", True)
    monkeypatch.setattr(settings, "prospect_discovery_rate_limit_max", 1)
    monkeypatch.setattr(
        prospect_discovery,
        "get_roc_company_data_provider",
        lambda: provider,
    )
    first = _auth(client, email="gov-a@example.com", organization_name="Gov A")
    second = _auth(client, email="gov-b@example.com", organization_name="Gov B")

    first_response = _government_search(client, first["access_token"], {"state_code": "DL"})
    limited_response = _government_search(client, first["access_token"], {"state_code": "DL"})
    second_response = _government_search(client, second["access_token"], {"state_code": "DL"})

    assert first_response.status_code == 200
    assert limited_response.status_code == 429
    assert second_response.status_code == 200
    assert len(provider.calls) == 2


def test_government_results_are_not_persisted_or_automated(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1 import prospect_discovery

    provider = MockGovernmentProvider()
    monkeypatch.setattr(settings, "roc_data_gov_in_provider_enabled", True)
    monkeypatch.setattr(
        prospect_discovery,
        "get_roc_company_data_provider",
        lambda: provider,
    )
    token = _auth(client)["access_token"]
    models = (CompanyProspect, Lead, ActivityEvent, WorkflowRun, WebhookDelivery)
    before = {model: db.scalar(select(func.count()).select_from(model)) for model in models}

    response = _government_search(client, token, {"state_code": "DL"})

    assert response.status_code == 200
    assert {model: db.scalar(select(func.count()).select_from(model)) for model in models} == before


def test_existing_synthetic_search_remains_unchanged_when_government_is_enabled(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1 import prospect_discovery

    def unexpected_government_provider() -> Any:
        pytest.fail("Synthetic search must not select the government provider")

    monkeypatch.setattr(settings, "roc_data_gov_in_provider_enabled", True)
    monkeypatch.setattr(
        prospect_discovery,
        "get_roc_company_data_provider",
        unexpected_government_provider,
    )
    token = _auth(client)["access_token"]
    response = client.post(
        "/api/v1/prospect-discovery/search",
        json={"page_size": 1},
        headers=_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["source"] == "SYNTHETIC"
    assert response.json()["items"][0]["synthetic"] is True
    assert response.json()["items"][0]["verification_status"] == "SYNTHETIC_UNVERIFIED"
