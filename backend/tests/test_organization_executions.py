from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.agent import Agent
from app.models.agent_execution import AgentExecution, AgentExecutionStatus
from app.models.lead import Lead
from app.models.membership import MembershipRole
from tests.test_agent_api import _add_org_member, _auth, _headers
from tests.test_agent_execution_history import _execution
from tests.test_agent_runtime import _create_agent

PATH = "/api/v1/agent-executions"
ALL_STATUSES = {status.value for status in AgentExecutionStatus}


def _lead(db: Session, organization_id: str, name: str = "Ada Prospect") -> Lead:
    lead = Lead(organization_id=organization_id, name=name, email="ada@example.com")
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _with_lead(db: Session, execution: AgentExecution, lead: Lead) -> AgentExecution:
    execution.lead_id = lead.id
    db.commit()
    db.refresh(execution)
    return execution


def _list(client: TestClient, token: str, **params: Any) -> Any:
    return client.get(PATH, params=params, headers=_headers(token))


def _org(client: TestClient, **kwargs: Any) -> tuple[str, str, str]:
    created = _auth(client, **kwargs)
    return created["access_token"], created["organization"]["id"], created["user"]["id"]


# 1. Authentication


def test_unauthenticated_request_is_rejected(client: TestClient) -> None:
    assert client.get(PATH).status_code == 401


# 2. Organization-wide listing across agents, with agent and lead context


def test_lists_executions_across_agents_with_agent_and_lead_names(
    client: TestClient, db: Session
) -> None:
    token, org_id, user_id = _org(client)
    sales = _create_agent(db, org_id, name="Sales helper")
    support = _create_agent(db, org_id, name="Support helper")
    lead = _lead(db, org_id, name="Ada Prospect")
    now = datetime.now(UTC)
    with_lead = _with_lead(
        db,
        _execution(db, org_id, sales, created_at=now, initiated_by_user_id=user_id),
        lead,
    )
    without_lead = _execution(db, org_id, support, created_at=now - timedelta(minutes=1))

    response = _list(client, token)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    first, second = body["items"]
    assert first["id"] == with_lead.id
    assert first["agent_id"] == sales.id
    assert first["agent_name"] == "Sales helper"
    assert first["lead_id"] == lead.id
    assert first["lead_name"] == "Ada Prospect"
    assert first["initiated_by_user_id"] == user_id
    assert first["status"] == "COMPLETED"
    assert first["is_stale"] is False
    assert second["id"] == without_lead.id
    assert second["agent_name"] == "Support helper"
    assert second["lead_id"] is None
    assert second["lead_name"] is None


# 3. Deterministic ordering and bounded pagination


def test_newest_first_with_id_tie_break_and_pagination(
    client: TestClient, db: Session
) -> None:
    token, org_id, _ = _org(client)
    agent = _create_agent(db, org_id)
    now = datetime.now(UTC)
    tied = now - timedelta(minutes=5)
    _execution(db, org_id, agent, created_at=now, execution_id="exec-newest")
    _execution(db, org_id, agent, created_at=tied, execution_id="exec-tied-a")
    _execution(db, org_id, agent, created_at=tied, execution_id="exec-tied-b")
    _execution(db, org_id, agent, created_at=now - timedelta(hours=1), execution_id="exec-old")

    full = _list(client, token).json()
    assert [item["id"] for item in full["items"]] == [
        "exec-newest",
        "exec-tied-b",
        "exec-tied-a",
        "exec-old",
    ]

    first_page = _list(client, token, limit=2, offset=0).json()
    second_page = _list(client, token, limit=2, offset=2).json()
    past_end = _list(client, token, limit=2, offset=10).json()
    assert [item["id"] for item in first_page["items"]] == ["exec-newest", "exec-tied-b"]
    assert [item["id"] for item in second_page["items"]] == ["exec-tied-a", "exec-old"]
    assert past_end["items"] == []
    for page in (first_page, second_page, past_end):
        assert page["total"] == 4
        assert page["limit"] == 2
    assert second_page["offset"] == 2


# 4. Query validation


def test_query_validation(client: TestClient) -> None:
    token, _, _ = _org(client)
    assert _list(client, token, limit=0).status_code == 422
    assert _list(client, token, limit=51).status_code == 422
    assert _list(client, token, offset=-1).status_code == 422
    assert _list(client, token, status="UNKNOWN").status_code == 422
    assert _list(client, token, agent_id="a" * 37).status_code == 422
    assert _list(client, token, lead_id="l" * 37).status_code == 422
    assert _list(client, token, limit=50).status_code == 200


# 5. Filters


def test_status_agent_and_lead_filters(client: TestClient, db: Session) -> None:
    token, org_id, _ = _org(client)
    sales = _create_agent(db, org_id, name="Sales helper")
    support = _create_agent(db, org_id, name="Support helper")
    lead = _lead(db, org_id)
    now = datetime.now(UTC)
    failed_sales_lead = _with_lead(
        db,
        _execution(
            db, org_id, sales, created_at=now, status=AgentExecutionStatus.FAILED,
            error="Provider timed out",
        ),
        lead,
    )
    completed_sales = _execution(db, org_id, sales, created_at=now - timedelta(minutes=1))
    failed_support = _execution(
        db, org_id, support, created_at=now - timedelta(minutes=2),
        status=AgentExecutionStatus.FAILED, error="Tool failed",
    )

    def ids(**params: Any) -> list[str]:
        response = _list(client, token, **params)
        assert response.status_code == 200
        return [item["id"] for item in response.json()["items"]]

    assert ids(status="FAILED") == [failed_sales_lead.id, failed_support.id]
    assert ids(agent_id=sales.id) == [failed_sales_lead.id, completed_sales.id]
    assert ids(lead_id=lead.id) == [failed_sales_lead.id]
    assert ids(status="FAILED", agent_id=support.id) == [failed_support.id]
    assert ids(status="COMPLETED", lead_id=lead.id) == []
    assert ids(status="CANCELLED") == []
    filtered = _list(client, token, status="FAILED").json()
    assert filtered["total"] == 2


# 6. Status counts are organization-wide and independent of filters


def test_status_counts_cover_all_statuses_and_ignore_filters(
    client: TestClient, db: Session
) -> None:
    token, org_id, _ = _org(client)
    agent = _create_agent(db, org_id)
    now = datetime.now(UTC)
    _execution(db, org_id, agent, created_at=now)
    _execution(db, org_id, agent, created_at=now, status=AgentExecutionStatus.COMPLETED)
    _execution(db, org_id, agent, created_at=now, status=AgentExecutionStatus.FAILED)
    _execution(db, org_id, agent, created_at=now, status=AgentExecutionStatus.RUNNING)

    expected = {
        "QUEUED": 0,
        "RUNNING": 1,
        "COMPLETED": 2,
        "FAILED": 1,
        "CANCELLED": 0,
    }
    unfiltered = _list(client, token).json()
    filtered = _list(client, token, status="FAILED", limit=1).json()
    assert set(unfiltered["status_counts"]) == ALL_STATUSES
    assert unfiltered["status_counts"] == expected
    assert filtered["status_counts"] == expected
    assert filtered["total"] == 1


# 7. Tenant isolation


def test_other_organization_executions_never_leak(client: TestClient, db: Session) -> None:
    token_a, org_a, _ = _org(client, email="a@example.com", organization_name="Org A")
    token_b, org_b, _ = _org(client, email="b@example.com", organization_name="Org B")
    agent_a = _create_agent(db, org_a, name="Agent A")
    agent_b = _create_agent(db, org_b, name="Agent B")
    lead_b = _lead(db, org_b, name="Lead B")
    now = datetime.now(UTC)
    own = _execution(db, org_a, agent_a, created_at=now)
    foreign = _with_lead(
        db,
        _execution(db, org_b, agent_b, created_at=now, status=AgentExecutionStatus.FAILED),
        lead_b,
    )

    body = _list(client, token_a).json()
    assert [item["id"] for item in body["items"]] == [own.id]
    assert body["total"] == 1
    assert body["status_counts"]["FAILED"] == 0
    assert body["status_counts"]["COMPLETED"] == 1

    for params in ({"agent_id": agent_b.id}, {"lead_id": lead_b.id}):
        response = _list(client, token_a, **params)
        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["total"] == 0

    body_b = _list(client, token_b).json()
    assert [item["id"] for item in body_b["items"]] == [foreign.id]
    assert own.id not in {item["id"] for item in body_b["items"]}


# 8. Roles


def test_owner_admin_and_member_can_list(client: TestClient, db: Session) -> None:
    owner_token, org_id, _ = _org(client)
    agent = _create_agent(db, org_id)
    execution = _execution(db, org_id, agent, created_at=datetime.now(UTC))
    tokens = {
        "OWNER": owner_token,
        "ADMIN": _add_org_member(db, org_id, email="admin@example.com", role=MembershipRole.ADMIN),
        "MEMBER": _add_org_member(
            db, org_id, email="member@example.com", role=MembershipRole.MEMBER
        ),
    }
    for role, token in tokens.items():
        response = _list(client, token)
        assert response.status_code == 200, role
        assert [item["id"] for item in response.json()["items"]] == [execution.id], role


# 9. Safe serialization


def test_payload_omits_output_tool_results_and_secrets(
    client: TestClient, db: Session
) -> None:
    token, org_id, _ = _org(client)
    agent = _create_agent(db, org_id)
    now = datetime.now(UTC)
    db.add(
        AgentExecution(
            organization_id=org_id,
            agent_id=agent.id,
            status=AgentExecutionStatus.COMPLETED,
            input={"text": "User task", "authorization": "secret-token"},
            output={
                "text": "Sensitive output text",
                "usage": {"total_tokens": 8, "api_key": "sk-secret"},
                "tool_results": [{"output": {"secret": "do-not-leak"}}],
                "provider_request": {"messages": [{"role": "system", "content": "hidden"}]},
            },
            provider="fake",
            model="fake-model",
            started_at=now,
            completed_at=now,
            created_at=now,
        )
    )
    db.commit()

    response = _list(client, token)
    raw = response.text
    item = response.json()["items"][0]
    for leaked in (
        "Sensitive output text",
        "tool_results",
        "do-not-leak",
        "sk-secret",
        "secret-token",
        "provider_request",
        "hidden",
        org_id,
    ):
        assert leaked not in raw
    assert "organization_id" not in item
    assert "output" not in item
    assert "input" not in item
    assert "usage" not in item
    assert item["input_preview"] == "User task"


# 10. Read-only: stale runs are flagged, never recovered


def test_get_is_read_only_and_flags_stale_running_without_recovering(
    client: TestClient, db: Session
) -> None:
    token, org_id, _ = _org(client)
    agent = _create_agent(db, org_id)
    now = datetime.now(UTC)
    long_ago = now - timedelta(days=1)
    stale = _execution(
        db, org_id, agent, created_at=long_ago, started_at=long_ago,
        status=AgentExecutionStatus.RUNNING, output_text="",
    )
    fresh = _execution(
        db, org_id, agent, created_at=now, started_at=now,
        status=AgentExecutionStatus.RUNNING, output_text="",
    )
    stale_failed = _execution(
        db, org_id, agent, created_at=long_ago - timedelta(minutes=1),
        status=AgentExecutionStatus.FAILED,
    )
    executions_before = db.scalar(select(func.count()).select_from(AgentExecution))
    activity_before = db.scalar(select(func.count()).select_from(ActivityEvent))

    response = _list(client, token)

    assert response.status_code == 200
    flags = {item["id"]: (item["status"], item["is_stale"]) for item in response.json()["items"]}
    assert flags[stale.id] == ("RUNNING", True)
    assert flags[fresh.id] == ("RUNNING", False)
    assert flags[stale_failed.id] == ("FAILED", False)

    db.expire_all()
    assert db.get(AgentExecution, stale.id).status == AgentExecutionStatus.RUNNING
    assert db.get(AgentExecution, stale.id).completed_at is None
    assert db.scalar(select(func.count()).select_from(AgentExecution)) == executions_before
    assert db.scalar(select(func.count()).select_from(ActivityEvent)) == activity_before


# 11. Missing agent or lead rows degrade to null names


def test_missing_agent_or_lead_rows_return_null_names(
    client: TestClient, db: Session
) -> None:
    """SQLite tests do not enforce FKs; Postgres cascades agents and nulls lead_id."""
    token, org_id, _ = _org(client)
    agent = _create_agent(db, org_id)
    lead = _lead(db, org_id)
    execution = _with_lead(
        db, _execution(db, org_id, agent, created_at=datetime.now(UTC)), lead
    )
    db.execute(delete(Lead).where(Lead.id == lead.id))
    db.execute(delete(Agent).where(Agent.id == agent.id))
    db.commit()

    response = _list(client, token)

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == execution.id
    assert item["agent_name"] is None
    assert item["lead_name"] is None


# 12. Regression: per-agent history still recovers stale runs as before


def test_per_agent_history_behavior_is_unchanged(client: TestClient, db: Session) -> None:
    token, org_id, _ = _org(client)
    agent = _create_agent(db, org_id)
    long_ago = datetime.now(UTC) - timedelta(days=1)
    stale = _execution(
        db, org_id, agent, created_at=long_ago, started_at=long_ago,
        status=AgentExecutionStatus.RUNNING, output_text="",
    )

    org_item = _list(client, token).json()["items"][0]
    assert (org_item["status"], org_item["is_stale"]) == ("RUNNING", True)

    per_agent = client.get(f"/api/v1/agents/{agent.id}/executions", headers=_headers(token))
    assert per_agent.status_code == 200
    per_agent_item = per_agent.json()["items"][0]
    assert per_agent_item["id"] == stale.id
    assert per_agent_item["status"] == "FAILED"
    assert "agent_name" not in per_agent_item
    assert "is_stale" not in per_agent_item

    org_after = _list(client, token).json()["items"][0]
    assert (org_after["status"], org_after["is_stale"]) == ("FAILED", False)
