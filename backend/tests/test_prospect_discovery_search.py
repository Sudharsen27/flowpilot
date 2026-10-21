from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.activity_event import ActivityEvent
from app.models.agent_execution import AgentExecution
from app.models.company_prospect import CompanyProspect
from app.models.lead import Lead
from app.models.lead_email_send import LeadEmailSend
from app.models.membership import Membership
from app.models.sales_run import SalesRun
from app.models.webhook import WebhookDelivery
from app.models.workflow import WorkflowRun
from app.schemas.prospect_discovery import ProspectDiscoverySearchRequest
from app.services.prospect_discovery_service import (
    DiscoveryCursorError,
    DiscoveryProviderError,
    ProspectDiscoveryService,
    SyntheticDiscoveryProvider,
)
from tests.test_agent_runtime import _headers
from tests.test_leads import _auth


def _search(
    client: TestClient, token: str | None, payload: dict[str, Any] | None = None
):
    headers = _headers(token) if token is not None else {}
    return client.post(
        "/api/v1/prospect-discovery/search",
        json=payload or {},
        headers=headers,
    )


def _service(*, max_page_size: int = 25, cursor_ttl_seconds: int = 900):
    return ProspectDiscoveryService(
        SyntheticDiscoveryProvider(),
        secret_key=settings.secret_key,
        max_page_size=max_page_size,
        cursor_ttl_seconds=cursor_ttl_seconds,
    )


def test_search_request_normalizes_supported_filters() -> None:
    request = ProspectDiscoverySearchRequest(
        industry="  software ",
        country=" united states ",
        region=" texas ",
        minimum_employees=20,
        maximum_employees=200,
    )

    assert request.industry == "Software"
    assert request.country == "United States"
    assert request.region == "Texas"
    assert request.minimum_employees == 20
    assert request.maximum_employees == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"industry": "  "},
        {"industry": "unlisted industry"},
        {"country": "Atlantis"},
        {"region": "Texas"},
        {"country": "Canada", "region": "Texas"},
        {"minimum_employees": 100, "maximum_employees": 10},
        {"minimum_employees": -1},
        {"maximum_employees": 1_000_001},
        {"page_size": 0},
        {"page_size": 101},
        {"page_size": True},
        {"offset": 1},
        {"provider": "external"},
    ],
)
def test_search_request_rejects_invalid_filters_and_pagination(
    payload: dict[str, Any],
) -> None:
    with pytest.raises(PydanticValidationError):
        ProspectDiscoverySearchRequest.model_validate(payload)


def test_synthetic_service_is_deterministic_and_paginates_stably() -> None:
    service = _service()
    request = ProspectDiscoverySearchRequest(page_size=3)
    first = service.search("organization-a", request)
    repeated = service.search("organization-a", request)

    assert [item.name for item in first.items] == [item.name for item in repeated.items]
    assert first.source == "SYNTHETIC"
    assert all(item.synthetic is True for item in first.items)
    assert all(item.verification_status == "SYNTHETIC_UNVERIFIED" for item in first.items)
    assert first.has_more is True
    assert first.next_cursor is not None

    second = service.search(
        "organization-a",
        ProspectDiscoverySearchRequest(page_size=3, cursor=first.next_cursor),
    )
    assert set(item.name for item in first.items).isdisjoint(item.name for item in second.items)
    assert second.items[0].name == "Cloudberry Metrics"


def test_synthetic_service_filters_and_explains_matches() -> None:
    response = _service().search(
        "organization-a",
        ProspectDiscoverySearchRequest(
            industry="Manufacturing",
            country="United States",
            region="Texas",
            minimum_employees=100,
            maximum_employees=200,
        ),
    )

    assert [item.name for item in response.items] == ["Aster Forge Systems"]
    assert response.items[0].match_explanations == [
        "Industry matches Manufacturing.",
        "Geography matches Texas, United States.",
        "Employee count (180) is within the requested range.",
    ]


def test_synthetic_service_rejects_bad_cursors_and_page_size() -> None:
    service = _service(max_page_size=1)
    with pytest.raises(ValueError, match="configured maximum"):
        service.search("organization-a", ProspectDiscoverySearchRequest(page_size=2))

    first = _service().search(
        "organization-a", ProspectDiscoverySearchRequest(page_size=1)
    )
    assert first.next_cursor is not None
    with pytest.raises(DiscoveryCursorError):
        _service().search(
            "organization-a",
            ProspectDiscoverySearchRequest(page_size=1, cursor=f"{first.next_cursor}x"),
        )
    with pytest.raises(DiscoveryCursorError):
        _service().search(
            "organization-b",
            ProspectDiscoverySearchRequest(page_size=1, cursor=first.next_cursor),
        )
    with pytest.raises(DiscoveryCursorError):
        _service().search(
            "organization-a",
            ProspectDiscoverySearchRequest(
                page_size=1, industry="Software", cursor=first.next_cursor
            ),
        )
    with pytest.raises(DiscoveryCursorError):
        _service().search(
            "organization-a",
            ProspectDiscoverySearchRequest(page_size=2, cursor=first.next_cursor),
        )


def test_synthetic_service_rejects_expired_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import prospect_discovery_service

    monkeypatch.setattr(prospect_discovery_service.time, "time", lambda: 1_000)
    service = _service(cursor_ttl_seconds=60)
    first = service.search(
        "organization-a", ProspectDiscoverySearchRequest(page_size=1)
    )
    assert first.next_cursor is not None

    monkeypatch.setattr(prospect_discovery_service.time, "time", lambda: 1_061)
    with pytest.raises(DiscoveryCursorError):
        service.search(
            "organization-a",
            ProspectDiscoverySearchRequest(page_size=1, cursor=first.next_cursor),
        )


def test_search_requires_membership_and_keeps_cursors_tenant_scoped(
    client: TestClient, db: Session
) -> None:
    assert _search(client, None).status_code == 401
    first = _auth(client, email="discovery-a@example.com", organization_name="Discovery A")
    second = _auth(client, email="discovery-b@example.com", organization_name="Discovery B")

    page = _search(client, first["access_token"], {"page_size": 1})
    assert page.status_code == 200
    assert _search(
        client, second["access_token"], {"page_size": 1, "cursor": page.json()["next_cursor"]}
    ).status_code == 400

    membership = db.scalar(
        select(Membership).where(Membership.organization_id == second["organization"]["id"])
    )
    assert membership is not None
    db.delete(membership)
    db.commit()
    assert _search(client, second["access_token"]).status_code == 401


def test_search_api_validates_limits_cursor_and_empty_results(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = _auth(client)["access_token"]

    monkeypatch.setattr(settings, "prospect_discovery_max_page_size", 1)
    assert _search(client, token, {"page_size": 2}).status_code == 422
    monkeypatch.setattr(settings, "prospect_discovery_max_page_size", 25)

    assert _search(client, token, {"cursor": "not-a-valid-cursor"}).status_code == 400
    assert _search(client, token, {"cursor": "x" * 1025}).status_code == 422
    empty = _search(
        client,
        token,
        {"industry": "Healthcare", "minimum_employees": 900, "page_size": 5},
    )
    assert empty.status_code == 200
    assert empty.json()["items"] == []
    assert empty.json()["has_more"] is False
    assert empty.json()["next_cursor"] is None


def test_search_usage_limits_are_isolated_by_organization(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "prospect_discovery_rate_limit_max", 1)
    first = _auth(client, email="usage-a@example.com", organization_name="Usage A")
    second = _auth(client, email="usage-b@example.com", organization_name="Usage B")

    assert _search(client, first["access_token"], {"page_size": 1}).status_code == 200
    limited = _search(client, first["access_token"], {"page_size": 1})
    assert limited.status_code == 429
    assert limited.json() == {"detail": "Discovery usage limit exceeded. Try again later."}
    assert _search(client, second["access_token"], {"page_size": 1}).status_code == 200


def test_search_enforces_per_organization_result_budget(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "prospect_discovery_result_limit", 1)
    token = _auth(client)["access_token"]

    assert _search(client, token, {"page_size": 1}).status_code == 200
    limited = _search(client, token, {"page_size": 1})
    assert limited.status_code == 429
    assert limited.json() == {"detail": "Discovery usage limit exceeded. Try again later."}


def test_provider_failure_returns_safe_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_search(*_args: Any, **_kwargs: Any) -> Any:
        raise DiscoveryProviderError("sensitive upstream detail")

    monkeypatch.setattr(SyntheticDiscoveryProvider, "search", fail_search)
    token = _auth(client)["access_token"]

    response = _search(client, token)

    assert response.status_code == 503
    assert response.json() == {"detail": "Synthetic discovery is temporarily unavailable."}
    assert "sensitive upstream detail" not in response.text


def test_discovery_never_persists_crm_data_or_triggers_side_effects(
    client: TestClient, db: Session
) -> None:
    token = _auth(client)["access_token"]
    models = (
        CompanyProspect,
        Lead,
        ActivityEvent,
        WorkflowRun,
        WebhookDelivery,
        LeadEmailSend,
        AgentExecution,
        SalesRun,
    )
    before = {
        model: db.scalar(select(func.count()).select_from(model))
        for model in models
    }

    response = _search(client, token, {"page_size": 4})

    assert response.status_code == 200
    assert {
        model: db.scalar(select(func.count()).select_from(model))
        for model in models
    } == before
