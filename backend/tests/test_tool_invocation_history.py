from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.agent_execution import AgentExecution
from app.models.membership import MembershipRole
from app.models.tool_invocation import ToolInvocation, ToolInvocationRecordStatus
from tests.test_agent_api import _add_org_member, _auth, _headers
from tests.test_agent_execution_history import _execution
from tests.test_agent_runtime import _create_agent


def _path(agent_id: str, execution_id: str) -> str:
    return f"/api/v1/agents/{agent_id}/executions/{execution_id}/tool-invocations"


def _invocation(
    db: Session,
    execution: AgentExecution,
    *,
    started_at: datetime,
    completed_at: datetime | None = None,
    invocation_id: str | None = None,
    call_id: str = "call-1",
    tool_name: str = "echo",
    status: ToolInvocationRecordStatus = ToolInvocationRecordStatus.SUCCESS,
    argument_keys: list[str] | None = None,
    error: str | None = None,
) -> ToolInvocation:
    row = ToolInvocation(
        organization_id=execution.organization_id,
        agent_id=execution.agent_id,
        execution_id=execution.id,
        call_id=call_id,
        tool_name=tool_name,
        risk_level="LOW",
        decision="ALLOW",
        status=status,
        argument_keys=argument_keys if argument_keys is not None else ["message"],
        error=error,
        started_at=started_at,
        completed_at=completed_at if completed_at is not None else started_at,
        created_at=started_at,
    )
    if invocation_id is not None:
        row.id = invocation_id
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_unauthenticated_tool_invocations_rejected(client: TestClient) -> None:
    assert client.get(_path("agent-1", "exec-1")).status_code == 401


def test_missing_agent_tool_invocations_not_found(client: TestClient) -> None:
    created = _auth(client)
    response = client.get(
        _path("missing-agent", "missing-exec"),
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"


def test_missing_execution_tool_invocations_not_found(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    response = client.get(
        _path(agent.id, "missing-exec"),
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent execution not found"


def test_empty_tool_invocations_list(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    execution = _execution(db, org_id, agent, created_at=datetime.now(UTC))
    body = client.get(
        _path(agent.id, execution.id),
        headers=_headers(created["access_token"]),
    ).json()
    assert body == {"items": [], "limit": 20, "offset": 0, "total": 0}


def test_roles_can_list_tool_invocations(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    execution = _execution(db, org_id, agent, created_at=datetime.now(UTC))
    _invocation(db, execution, started_at=datetime.now(UTC))
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
        response = client.get(_path(agent.id, execution.id), headers=_headers(token))
        assert response.status_code == 200, role
        assert response.json()["total"] == 1


def test_tool_invocations_are_chronological(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    execution = _execution(db, org_id, agent, created_at=datetime.now(UTC))
    now = datetime.now(UTC)
    later = _invocation(
        db,
        execution,
        started_at=now + timedelta(seconds=2),
        invocation_id="inv-later",
        call_id="call-later",
    )
    earlier = _invocation(
        db,
        execution,
        started_at=now,
        invocation_id="inv-earlier",
        call_id="call-earlier",
    )
    same_time_b = _invocation(
        db,
        execution,
        started_at=now + timedelta(seconds=1),
        invocation_id="inv-b",
        call_id="call-b",
    )
    same_time_a = _invocation(
        db,
        execution,
        started_at=now + timedelta(seconds=1),
        invocation_id="inv-a",
        call_id="call-a",
    )
    ids = [
        item["id"]
        for item in client.get(
            _path(agent.id, execution.id),
            headers=_headers(created["access_token"]),
        ).json()["items"]
    ]
    assert ids == [earlier.id, same_time_a.id, same_time_b.id, later.id]


def test_tool_invocation_pagination(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    execution = _execution(db, org_id, agent, created_at=datetime.now(UTC))
    now = datetime.now(UTC)
    first = _invocation(
        db, execution, started_at=now, invocation_id="inv-1", call_id="c1"
    )
    second = _invocation(
        db,
        execution,
        started_at=now + timedelta(seconds=1),
        invocation_id="inv-2",
        call_id="c2",
    )
    third = _invocation(
        db,
        execution,
        started_at=now + timedelta(seconds=2),
        invocation_id="inv-3",
        call_id="c3",
    )
    headers = _headers(created["access_token"])
    page = client.get(
        _path(agent.id, execution.id), params={"limit": 2, "offset": 0}, headers=headers
    )
    body = page.json()
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert body["total"] == 3
    assert [item["id"] for item in body["items"]] == [first.id, second.id]
    next_page = client.get(
        _path(agent.id, execution.id), params={"limit": 2, "offset": 2}, headers=headers
    )
    assert [item["id"] for item in next_page.json()["items"]] == [third.id]
    default = client.get(_path(agent.id, execution.id), headers=headers)
    assert default.json()["limit"] == 20
    assert default.json()["total"] == 3
    max_ok = client.get(_path(agent.id, execution.id), params={"limit": 50}, headers=headers)
    assert max_ok.status_code == 200
    assert max_ok.json()["limit"] == 50


def test_tool_invocation_limit_and_offset_validation(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    execution = _execution(db, org_id, agent, created_at=datetime.now(UTC))
    headers = _headers(created["access_token"])
    assert (
        client.get(
            _path(agent.id, execution.id), params={"limit": 51}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.get(
            _path(agent.id, execution.id), params={"limit": 0}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.get(
            _path(agent.id, execution.id), params={"offset": -1}, headers=headers
        ).status_code
        == 422
    )


def test_tool_invocation_safe_fields_omit_payloads(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    execution = _execution(db, org_id, agent, created_at=datetime.now(UTC))
    invocation = _invocation(
        db,
        execution,
        started_at=datetime.now(UTC),
        argument_keys=["message"],
        error="Invalid tool arguments",
        status=ToolInvocationRecordStatus.FAILED,
    )
    body = client.get(
        _path(agent.id, execution.id),
        headers=_headers(created["access_token"]),
    ).json()
    item = body["items"][0]
    assert item["id"] == invocation.id
    assert item["execution_id"] == execution.id
    assert item["agent_id"] == agent.id
    assert item["call_id"] == "call-1"
    assert item["tool_name"] == "echo"
    assert item["risk_level"] == "LOW"
    assert item["decision"] == "ALLOW"
    assert item["status"] == "FAILED"
    assert item["argument_keys"] == ["message"]
    assert item["error"] == "Invalid tool arguments"
    assert item["started_at"]
    assert item["completed_at"]
    assert item["created_at"]
    serialized = str(body)
    assert "hello secret value" not in serialized
    assert "do-not-leak" not in serialized
    assert "tool_results" not in serialized
    assert "organization_id" not in item
    assert "output" not in item
    assert "arguments" not in item


def test_cross_tenant_tool_invocations_not_found(
    client: TestClient, db: Session
) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    agent = _create_agent(db, first["organization"]["id"])
    execution = _execution(
        db, first["organization"]["id"], agent, created_at=datetime.now(UTC)
    )
    _invocation(db, execution, started_at=datetime.now(UTC))
    foreign = _headers(second["access_token"])
    listed = client.get(_path(agent.id, execution.id), headers=foreign)
    assert listed.status_code == 404
    copied = client.get(_path("foreign-agent", execution.id), headers=foreign)
    assert copied.status_code == 404


def test_cross_agent_tool_invocations_not_found(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent_a = _create_agent(db, org_id, name="Agent A")
    agent_b = _create_agent(db, org_id, name="Agent B")
    execution = _execution(db, org_id, agent_a, created_at=datetime.now(UTC))
    _invocation(db, execution, started_at=datetime.now(UTC))
    response = client.get(
        _path(agent_b.id, execution.id),
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent execution not found"


def test_tool_invocations_are_scoped_to_the_requested_execution(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    now = datetime.now(UTC)
    execution_a = _execution(db, org_id, agent, created_at=now, execution_id="exec-a")
    execution_b = _execution(
        db, org_id, agent, created_at=now - timedelta(seconds=1), execution_id="exec-b"
    )
    keep = _invocation(
        db, execution_a, started_at=now, invocation_id="inv-keep", call_id="keep"
    )
    _invocation(db, execution_b, started_at=now, invocation_id="inv-other", call_id="other")
    body = client.get(
        _path(agent.id, execution_a.id),
        headers=_headers(created["access_token"]),
    ).json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [keep.id]


def test_tool_invocation_offset_beyond_total(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    execution = _execution(db, org_id, agent, created_at=datetime.now(UTC))
    _invocation(db, execution, started_at=datetime.now(UTC), invocation_id="inv-1", call_id="c1")
    body = client.get(
        _path(agent.id, execution.id),
        params={"limit": 20, "offset": 25},
        headers=_headers(created["access_token"]),
    ).json()
    assert body == {"items": [], "limit": 20, "offset": 25, "total": 1}
