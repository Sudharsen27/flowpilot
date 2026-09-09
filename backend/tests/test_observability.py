from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.agent_execution import AgentExecutionStatus, ExecutionFailureCategory
from app.services.observability import duration_ms
from tests.test_agent_api import _auth, _headers
from tests.test_agent_execution_history import _execution
from tests.test_agent_runtime import _create_agent
from tests.test_tool_invocation_history import _invocation


def test_duration_ms_from_timestamps() -> None:
    started = datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC)
    completed = started + timedelta(milliseconds=1800)
    assert duration_ms(started, completed) == 1800


def test_duration_ms_same_timestamp_is_zero() -> None:
    started = datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC)
    assert duration_ms(started, started) == 0


def test_duration_ms_missing_timestamps() -> None:
    started = datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC)
    assert duration_ms(None, started) is None
    assert duration_ms(started, None) is None
    assert duration_ms(None, None) is None


def test_duration_ms_rejects_negative_span() -> None:
    started = datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC)
    completed = started - timedelta(seconds=2)
    assert duration_ms(started, completed) is None


def test_history_exposes_duration_and_null_failure_category(
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
        started_at=now,
        completed_at=now + timedelta(seconds=2),
    )
    headers = _headers(created["access_token"])
    listed = client.get(f"/api/v1/agents/{agent.id}/executions", headers=headers).json()
    item = listed["items"][0]
    assert item["id"] == execution.id
    assert item["duration_ms"] == 2000
    assert item["failure_category"] is None
    detail = client.get(
        f"/api/v1/agents/{agent.id}/executions/{execution.id}",
        headers=headers,
    ).json()
    assert detail["duration_ms"] == 2000
    assert detail["failure_category"] is None
    assert "tool_results" not in detail
    assert "do-not-leak" not in str(detail)


def test_history_omits_duration_without_completed_at(
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
        status=AgentExecutionStatus.RUNNING,
        started_at=now,
        completed_at=None,
        output_text="",
    )
    body = client.get(
        f"/api/v1/agents/{agent.id}/executions/{execution.id}",
        headers=_headers(created["access_token"]),
    ).json()
    assert body["duration_ms"] is None
    assert body["failure_category"] is None


def test_history_omits_negative_duration(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    now = datetime.now(UTC)
    execution = _execution(
        db,
        org_id,
        agent,
        created_at=now,
        started_at=now,
        completed_at=now - timedelta(seconds=5),
    )
    body = client.get(
        f"/api/v1/agents/{agent.id}/executions/{execution.id}",
        headers=_headers(created["access_token"]),
    ).json()
    assert body["duration_ms"] is None


def test_failed_history_includes_failure_category(
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
        status=AgentExecutionStatus.FAILED,
        error="upstream timeout",
        failure_category=ExecutionFailureCategory.PROVIDER_ERROR,
        started_at=now,
        completed_at=now + timedelta(seconds=2),
        output_text="",
    )
    body = client.get(
        f"/api/v1/agents/{agent.id}/executions/{execution.id}",
        headers=_headers(created["access_token"]),
    ).json()
    assert body["failure_category"] == "PROVIDER_ERROR"
    assert body["error"] == "upstream timeout"
    assert body["duration_ms"] == 2000
    listed = client.get(
        f"/api/v1/agents/{agent.id}/executions",
        headers=_headers(created["access_token"]),
    ).json()
    assert listed["items"][0]["failure_category"] == "PROVIDER_ERROR"


def test_tool_invocation_duration_is_derived(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    now = datetime.now(UTC)
    execution = _execution(db, org_id, agent, created_at=now)
    invocation = _invocation(
        db,
        execution,
        started_at=now,
        completed_at=now + timedelta(seconds=2),
        invocation_id="inv-1",
        call_id="c1",
    )
    body = client.get(
        f"/api/v1/agents/{agent.id}/executions/{execution.id}/tool-invocations",
        headers=_headers(created["access_token"]),
    ).json()
    item = body["items"][0]
    assert item["id"] == invocation.id
    assert item["duration_ms"] == 2000
    assert item["tool_name"] == "echo"
    assert "arguments" not in item
    assert "output" not in item
    assert "hello secret" not in str(body)
