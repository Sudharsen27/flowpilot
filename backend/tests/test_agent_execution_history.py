from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_execution import (
    AgentExecution,
    AgentExecutionStatus,
    ExecutionFailureCategory,
)
from app.models.membership import MembershipRole
from tests.test_agent_api import _add_org_member, _auth, _headers
from tests.test_agent_runtime import _create_agent


def _execution(
    db: Session,
    organization_id: str,
    agent: Agent,
    *,
    created_at: datetime,
    execution_id: str | None = None,
    status: AgentExecutionStatus = AgentExecutionStatus.COMPLETED,
    input_text: str = "Qualify this lead with confidential context",
    output_text: str = "The lead is qualified.",
    error: str | None = None,
    failure_category: ExecutionFailureCategory | None = None,
    initiated_by_user_id: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> AgentExecution:
    start = created_at if started_at is None else started_at
    end = created_at if completed_at is None and started_at is None else completed_at
    row = AgentExecution(
        organization_id=organization_id,
        agent_id=agent.id,
        initiated_by_user_id=initiated_by_user_id,
        status=status,
        input={"text": input_text},
        output={
            "text": output_text,
            "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
            "tool_results": [{"call_id": "call-1", "output": {"secret": "do-not-leak"}}],
        }
        if output_text
        else None,
        error=error,
        failure_category=failure_category,
        provider="fake",
        model="fake-model",
        started_at=start,
        completed_at=end,
        created_at=created_at,
    )
    if execution_id is not None:
        row.id = execution_id
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_unauthenticated_history_is_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/agents/agent-1/executions").status_code == 401
    assert client.get("/api/v1/agents/agent-1/executions/exec-1").status_code == 401


def test_missing_agent_history_is_not_found(client: TestClient) -> None:
    created = _auth(client)
    headers = _headers(created["access_token"])
    listed = client.get("/api/v1/agents/missing-agent/executions", headers=headers)
    assert listed.status_code == 404
    assert listed.json()["detail"] == "Agent not found"
    detail = client.get(
        "/api/v1/agents/missing-agent/executions/missing-exec",
        headers=headers,
    )
    assert detail.status_code == 404
    assert detail.json()["detail"] == "Agent not found"


def test_missing_execution_is_not_found(client: TestClient, db: Session) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    response = client.get(
        f"/api/v1/agents/{agent.id}/executions/missing-exec",
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent execution not found"


def test_roles_can_list_and_get_executions(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    now = datetime.now(UTC)
    execution = _execution(
        db,
        org_id,
        agent,
        created_at=now,
        initiated_by_user_id=created["user"]["id"],
    )
    tokens = {
        "OWNER": created["access_token"],
        "ADMIN": _add_org_member(
            db, org_id, email="admin@example.com", role=MembershipRole.ADMIN
        ),
        "MEMBER": _add_org_member(
            db, org_id, email="member@example.com", role=MembershipRole.MEMBER
        ),
    }
    for role, token in tokens.items():
        headers = _headers(token)
        listed = client.get(f"/api/v1/agents/{agent.id}/executions", headers=headers)
        assert listed.status_code == 200, role
        body = listed.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == execution.id
        detail = client.get(
            f"/api/v1/agents/{agent.id}/executions/{execution.id}",
            headers=headers,
        )
        assert detail.status_code == 200, role
        assert detail.json()["id"] == execution.id


def test_list_is_newest_first_and_paginated(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    now = datetime.now(UTC)
    older = _execution(
        db, org_id, agent, created_at=now - timedelta(seconds=3), execution_id="exec-old"
    )
    middle = _execution(
        db, org_id, agent, created_at=now - timedelta(seconds=2), execution_id="exec-mid"
    )
    newest = _execution(
        db, org_id, agent, created_at=now - timedelta(seconds=1), execution_id="exec-new"
    )
    headers = _headers(created["access_token"])

    first_page = client.get(
        f"/api/v1/agents/{agent.id}/executions",
        params={"limit": 2, "offset": 0},
        headers=headers,
    )
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert first_body["limit"] == 2
    assert first_body["offset"] == 0
    assert first_body["total"] == 3
    assert [item["id"] for item in first_body["items"]] == [newest.id, middle.id]

    second_page = client.get(
        f"/api/v1/agents/{agent.id}/executions",
        params={"limit": 2, "offset": 2},
        headers=headers,
    )
    assert [item["id"] for item in second_page.json()["items"]] == [older.id]


def test_list_rejects_oversize_limit(client: TestClient, db: Session) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    response = client.get(
        f"/api/v1/agents/{agent.id}/executions",
        params={"limit": 51},
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 422


def test_list_omits_full_input_output_and_tool_results(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    secret_input = "Qualify this lead with confidential context " + ("x" * 120)
    _execution(db, org_id, agent, created_at=datetime.now(UTC), input_text=secret_input)
    body = client.get(
        f"/api/v1/agents/{agent.id}/executions",
        headers=_headers(created["access_token"]),
    ).json()
    item = body["items"][0]
    assert "input" not in item
    assert "output" not in item
    assert "tool_results" not in item
    assert "usage" not in item
    assert item["input_preview"] == secret_input[:120]
    assert item["input_preview"] != secret_input
    assert "do-not-leak" not in str(body)
    assert item["status"] == "COMPLETED"


def test_detail_returns_safe_fields_without_tool_results(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    now = datetime.now(UTC)
    execution = _execution(
        db,
        org_id,
        agent,
        created_at=now,
        input_text="User task",
        output_text="Safe output text",
        error="Provider timeout",
        initiated_by_user_id=created["user"]["id"],
        status=AgentExecutionStatus.FAILED,
    )
    body = client.get(
        f"/api/v1/agents/{agent.id}/executions/{execution.id}",
        headers=_headers(created["access_token"]),
    ).json()
    assert body["id"] == execution.id
    assert body["agent_id"] == agent.id
    assert body["status"] == "FAILED"
    assert body["input"] == "User task"
    assert body["output"] == "Safe output text"
    assert body["provider"] == "fake"
    assert body["model"] == "fake-model"
    assert body["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 5,
        "total_tokens": 8,
    }
    assert body["error"] == "Provider timeout"
    assert body["initiated_by_user_id"] == created["user"]["id"]
    assert body["started_at"]
    assert body["completed_at"]
    assert body["created_at"]
    assert "tool_results" not in body
    assert "do-not-leak" not in str(body)


def test_cross_tenant_history_is_not_found(client: TestClient, db: Session) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    agent = _create_agent(db, first["organization"]["id"])
    execution = _execution(
        db,
        first["organization"]["id"],
        agent,
        created_at=datetime.now(UTC),
    )
    foreign = _headers(second["access_token"])
    listed = client.get(f"/api/v1/agents/{agent.id}/executions", headers=foreign)
    assert listed.status_code == 404
    copied = client.get(
        f"/api/v1/agents/{agent.id}/executions/{execution.id}",
        headers=foreign,
    )
    assert copied.status_code == 404


def test_cross_agent_execution_is_not_found(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent_a = _create_agent(db, org_id, name="Agent A")
    agent_b = _create_agent(db, org_id, name="Agent B")
    execution = _execution(db, org_id, agent_a, created_at=datetime.now(UTC))
    response = client.get(
        f"/api/v1/agents/{agent_b.id}/executions/{execution.id}",
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent execution not found"
    listed = client.get(
        f"/api/v1/agents/{agent_b.id}/executions",
        headers=_headers(created["access_token"]),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 0
    assert listed.json()["items"] == []


def test_list_pagination_boundaries_and_tie_break(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    now = datetime.now(UTC)
    first = _execution(db, org_id, agent, created_at=now, execution_id="exec-a")
    second = _execution(db, org_id, agent, created_at=now, execution_id="exec-b")
    third = _execution(
        db, org_id, agent, created_at=now - timedelta(seconds=1), execution_id="exec-c"
    )
    fourth = _execution(
        db, org_id, agent, created_at=now - timedelta(seconds=2), execution_id="exec-d"
    )
    fifth = _execution(
        db, org_id, agent, created_at=now - timedelta(seconds=3), execution_id="exec-e"
    )
    headers = _headers(created["access_token"])
    path = f"/api/v1/agents/{agent.id}/executions"

    default = client.get(path, headers=headers)
    assert default.status_code == 200
    assert default.json()["limit"] == 20
    assert default.json()["offset"] == 0
    assert default.json()["total"] == 5
    assert [item["id"] for item in default.json()["items"]] == [
        second.id,
        first.id,
        third.id,
        fourth.id,
        fifth.id,
    ]

    first_page = client.get(path, params={"limit": 2, "offset": 0}, headers=headers)
    assert [item["id"] for item in first_page.json()["items"]] == [second.id, first.id]
    middle = client.get(path, params={"limit": 2, "offset": 2}, headers=headers)
    assert middle.json()["total"] == 5
    assert [item["id"] for item in middle.json()["items"]] == [third.id, fourth.id]
    last = client.get(path, params={"limit": 2, "offset": 4}, headers=headers)
    assert [item["id"] for item in last.json()["items"]] == [fifth.id]
    beyond = client.get(path, params={"limit": 2, "offset": 50}, headers=headers)
    assert beyond.json() == {"items": [], "limit": 2, "offset": 50, "total": 5}

    one = client.get(path, params={"limit": 1, "offset": 0}, headers=headers)
    assert [item["id"] for item in one.json()["items"]] == [second.id]
    max_ok = client.get(path, params={"limit": 50}, headers=headers)
    assert max_ok.status_code == 200
    assert max_ok.json()["limit"] == 50
    assert len(max_ok.json()["items"]) == 5


def test_list_limit_and_offset_validation(client: TestClient, db: Session) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    headers = _headers(created["access_token"])
    path = f"/api/v1/agents/{agent.id}/executions"
    assert client.get(path, params={"limit": 0}, headers=headers).status_code == 422
    assert client.get(path, params={"limit": 51}, headers=headers).status_code == 422
    assert client.get(path, params={"offset": -1}, headers=headers).status_code == 422


def test_history_payloads_omit_organization_and_provider_secrets(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    now = datetime.now(UTC)
    execution = AgentExecution(
        organization_id=org_id,
        agent_id=agent.id,
        status=AgentExecutionStatus.COMPLETED,
        input={"text": "User task", "authorization": "secret-token"},
        output={
            "text": "Safe output text",
            "usage": {
                "prompt_tokens": 3,
                "completion_tokens": 5,
                "total_tokens": 8,
                "api_key": "sk-secret",
            },
            "tool_results": [{"output": {"secret": "do-not-leak"}}],
            "provider_request": {"messages": [{"role": "system", "content": "hidden"}]},
        },
        provider="fake",
        model="fake-model",
        started_at=now,
        completed_at=now,
        created_at=now,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    headers = _headers(created["access_token"])
    listed = client.get(f"/api/v1/agents/{agent.id}/executions", headers=headers).json()
    detail = client.get(
        f"/api/v1/agents/{agent.id}/executions/{execution.id}",
        headers=headers,
    ).json()
    serialized = str(listed) + str(detail)
    assert "organization_id" not in listed["items"][0]
    assert "organization_id" not in detail
    assert "secret-token" not in serialized
    assert "sk-secret" not in serialized
    assert "do-not-leak" not in serialized
    assert "provider_request" not in serialized
    assert "tool_results" not in serialized
    assert detail["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 5,
        "total_tokens": 8,
    }
    assert detail["input"] == "User task"
    assert detail["output"] == "Safe output text"
