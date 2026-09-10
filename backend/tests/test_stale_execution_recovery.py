import threading
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.provider import AIGenerateRequest, AIGenerateResult
from app.core.config import Settings, settings
from app.core.exceptions import ConflictError, ProviderError
from app.models.agent import Agent
from app.models.agent_execution import (
    AgentExecution,
    AgentExecutionStatus,
    ExecutionFailureCategory,
)
from app.models.membership import MembershipRole
from app.services.agent_execution_service import (
    STALE_EXECUTION_MESSAGE,
    AgentExecutionService,
)
from app.services.observability import duration_ms
from tests.conftest import TestingSessionLocal
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import (
    FakeAIProvider,
    _auth,
    _create_agent,
    _headers,
)


def _stale_service(db: Session, timeout: float = 1) -> AgentExecutionService:
    return AgentExecutionService(db, FakeAIProvider(), stale_timeout_seconds=timeout)


def _running(
    db: Session,
    organization_id: str,
    agent: Agent,
    *,
    started_at: datetime,
    output: dict | None = None,
) -> AgentExecution:
    row = AgentExecution(
        organization_id=organization_id,
        agent_id=agent.id,
        status=AgentExecutionStatus.RUNNING,
        input={"text": "hello"},
        output=output,
        started_at=started_at,
        created_at=started_at,
        completed_at=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_fresh_running_execution_is_not_recovered(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    row = _running(db, org_id, agent, started_at=datetime.now(UTC))
    recovered = _stale_service(db).recover_stale_running_executions(
        organization_id=org_id, agent_id=agent.id
    )
    db.refresh(row)
    assert recovered == 0
    assert row.status == AgentExecutionStatus.RUNNING
    assert row.completed_at is None
    assert row.failure_category is None


def test_stale_running_execution_is_recovered(db: Session, client: TestClient) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    started = datetime.now(UTC) - timedelta(seconds=5)
    row = _running(db, org_id, agent, started_at=started, output={"claimed": True})
    recovered = _stale_service(db).recover_stale_running_executions(
        organization_id=org_id, agent_id=agent.id
    )
    db.refresh(row)
    assert recovered == 1
    assert row.status == AgentExecutionStatus.FAILED
    assert row.error == STALE_EXECUTION_MESSAGE
    assert row.failure_category == ExecutionFailureCategory.EXECUTION_ERROR
    assert row.started_at is not None
    assert row.completed_at is not None
    assert row.output is None
    elapsed = duration_ms(row.started_at, row.completed_at)
    assert elapsed is not None
    assert elapsed >= 5000


def test_recovery_is_idempotent(db: Session, client: TestClient) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    row = _running(
        db, org_id, agent, started_at=datetime.now(UTC) - timedelta(seconds=5)
    )
    service = _stale_service(db)
    assert (
        service.recover_stale_running_executions(
            organization_id=org_id, agent_id=agent.id
        )
        == 1
    )
    db.refresh(row)
    completed_at = row.completed_at
    error = row.error
    assert (
        service.recover_stale_running_executions(
            organization_id=org_id, agent_id=agent.id
        )
        == 0
    )
    db.refresh(row)
    assert row.status == AgentExecutionStatus.FAILED
    assert row.completed_at == completed_at
    assert row.error == error


@pytest.mark.parametrize(
    "status,category",
    [
        (AgentExecutionStatus.COMPLETED, None),
        (AgentExecutionStatus.FAILED, ExecutionFailureCategory.PROVIDER_ERROR),
        (AgentExecutionStatus.CANCELLED, None),
    ],
)
def test_terminal_executions_are_not_recovered(
    db: Session,
    client: TestClient,
    status: AgentExecutionStatus,
    category: ExecutionFailureCategory | None,
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    old = datetime.now(UTC) - timedelta(hours=1)
    row = AgentExecution(
        organization_id=org_id,
        agent_id=agent.id,
        status=status,
        input={"text": "hello"},
        error="original",
        failure_category=category,
        started_at=old,
        completed_at=old,
        created_at=old,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    recovered = _stale_service(db).recover_stale_running_executions(
        organization_id=org_id, agent_id=agent.id
    )
    db.refresh(row)
    assert recovered == 0
    assert row.status == status
    assert row.error == "original"
    assert row.failure_category == category


def test_recovery_is_tenant_and_agent_scoped(db: Session, client: TestClient) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    org_a = first["organization"]["id"]
    org_b = second["organization"]["id"]
    agent_a = _create_agent(db, org_a, name="Agent A")
    agent_a2 = _create_agent(db, org_a, name="Agent A2")
    agent_b = _create_agent(db, org_b, name="Agent B")
    old = datetime.now(UTC) - timedelta(seconds=5)
    row_a = _running(db, org_a, agent_a, started_at=old)
    row_a2 = _running(db, org_a, agent_a2, started_at=old)
    row_b = _running(db, org_b, agent_b, started_at=old)
    recovered = _stale_service(db).recover_stale_running_executions(
        organization_id=org_a, agent_id=agent_a.id
    )
    db.refresh(row_a)
    db.refresh(row_a2)
    db.refresh(row_b)
    assert recovered == 1
    assert row_a.status == AgentExecutionStatus.FAILED
    assert row_a2.status == AgentExecutionStatus.RUNNING
    assert row_b.status == AgentExecutionStatus.RUNNING


def test_recovery_does_not_overwrite_completed(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    started = AgentExecutionService(db, FakeAIProvider()).start_execution(
        organization_id=org_id, agent_id=agent.id, user_input="Hello"
    )
    result = AgentExecutionService(db, FakeAIProvider()).run_execution(
        organization_id=org_id,
        agent_id=agent.id,
        execution_id=started.execution_id,
    )
    assert result.status == AgentExecutionStatus.COMPLETED
    recovered = _stale_service(db, timeout=0.001).recover_stale_running_executions(
        organization_id=org_id, agent_id=agent.id
    )
    row = db.get(AgentExecution, started.execution_id)
    assert recovered == 0
    assert row is not None
    assert row.status == AgentExecutionStatus.COMPLETED


def test_recovery_race_completed_wins(db: Session, client: TestClient) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    started = AgentExecutionService(db, FakeAIProvider()).start_execution(
        organization_id=org_id, agent_id=agent.id, user_input="Hello"
    )
    completed = AgentExecutionService(db, FakeAIProvider()).run_execution(
        organization_id=org_id,
        agent_id=agent.id,
        execution_id=started.execution_id,
    )
    assert completed.status == AgentExecutionStatus.COMPLETED
    recovered = _stale_service(db).recover_stale_running_executions(
        organization_id=org_id,
        agent_id=agent.id,
        execution_id=started.execution_id,
    )
    row = db.get(AgentExecution, started.execution_id)
    assert recovered == 0
    assert row is not None
    assert row.status == AgentExecutionStatus.COMPLETED


def test_recovery_race_failed_wins(db: Session, client: TestClient) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    started = AgentExecutionService(db, FakeAIProvider()).start_execution(
        organization_id=org_id, agent_id=agent.id, user_input="Hello"
    )
    with pytest.raises(ProviderError):
        AgentExecutionService(
            db, FakeAIProvider(fail=ProviderError("boom"))
        ).run_execution(
            organization_id=org_id,
            agent_id=agent.id,
            execution_id=started.execution_id,
        )
    recovered = _stale_service(db).recover_stale_running_executions(
        organization_id=org_id,
        agent_id=agent.id,
        execution_id=started.execution_id,
    )
    row = db.get(AgentExecution, started.execution_id)
    assert recovered == 0
    assert row is not None
    assert row.status == AgentExecutionStatus.FAILED
    assert row.error != STALE_EXECUTION_MESSAGE


def test_recovery_race_cancelled_wins(db: Session, client: TestClient) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    started = AgentExecutionService(db, FakeAIProvider()).start_execution(
        organization_id=org_id, agent_id=agent.id, user_input="Hello"
    )
    cancelled = AgentExecutionService(db).cancel_execution(
        organization_id=org_id,
        agent_id=agent.id,
        execution_id=started.execution_id,
    )
    assert cancelled.status == AgentExecutionStatus.CANCELLED
    recovered = _stale_service(db).recover_stale_running_executions(
        organization_id=org_id,
        agent_id=agent.id,
        execution_id=started.execution_id,
    )
    row = db.get(AgentExecution, started.execution_id)
    assert recovered == 0
    assert row is not None
    assert row.status == AgentExecutionStatus.CANCELLED
    assert row.error == "Execution was cancelled."


def test_recovery_then_complete_cannot_overwrite(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    row = _running(
        db, org_id, agent, started_at=datetime.now(UTC) - timedelta(seconds=5)
    )
    recovered = _stale_service(db).recover_stale_running_executions(
        organization_id=org_id, agent_id=agent.id, execution_id=row.id
    )
    assert recovered == 1
    updated = AgentExecutionService(db).executions.finalize_running(
        org_id,
        agent.id,
        row.id,
        {
            "status": AgentExecutionStatus.COMPLETED,
            "error": None,
            "failure_category": None,
            "completed_at": datetime.now(UTC),
        },
    )
    db.refresh(row)
    assert updated == 0
    assert row.status == AgentExecutionStatus.FAILED
    assert row.error == STALE_EXECUTION_MESSAGE


def test_multiple_stale_executions_are_recovered(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    old = datetime.now(UTC) - timedelta(seconds=5)
    first = _running(db, org_id, agent, started_at=old)
    second = _running(db, org_id, agent, started_at=old)
    fresh = _running(db, org_id, agent, started_at=datetime.now(UTC))
    recovered = _stale_service(db).recover_stale_running_executions(
        organization_id=org_id, agent_id=agent.id
    )
    db.refresh(first)
    db.refresh(second)
    db.refresh(fresh)
    assert recovered == 2
    assert first.status == AgentExecutionStatus.FAILED
    assert second.status == AgentExecutionStatus.FAILED
    assert fresh.status == AgentExecutionStatus.RUNNING


def test_long_running_legitimate_execution_is_not_recovered(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    started = AgentExecutionService(db, FakeAIProvider()).start_execution(
        organization_id=org_id, agent_id=agent.id, user_input="Hello"
    )
    entered = threading.Event()
    release = threading.Event()

    class BlockingProvider(FakeAIProvider):
        def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
            entered.set()
            assert release.wait(timeout=5)
            return super().generate(request)

    outcomes: list[object] = []

    def runner() -> None:
        session = TestingSessionLocal()
        try:
            outcomes.append(
                AgentExecutionService(session, BlockingProvider()).run_execution(
                    organization_id=org_id,
                    agent_id=agent.id,
                    execution_id=started.execution_id,
                )
            )
        except Exception as exc:
            outcomes.append(exc)
        finally:
            session.close()

    thread = threading.Thread(target=runner)
    thread.start()
    assert entered.wait(timeout=5)
    other = TestingSessionLocal()
    try:
        recovered = AgentExecutionService(
            other, stale_timeout_seconds=3600
        ).recover_stale_running_executions(
            organization_id=org_id,
            agent_id=agent.id,
            execution_id=started.execution_id,
        )
        assert recovered == 0
    finally:
        other.close()
    release.set()
    thread.join(timeout=5)
    assert outcomes[0].status == AgentExecutionStatus.COMPLETED  # type: ignore[union-attr]


def test_in_flight_recovery_wins_over_later_complete(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    started = AgentExecutionService(db, FakeAIProvider()).start_execution(
        organization_id=org_id, agent_id=agent.id, user_input="Hello"
    )
    entered = threading.Event()
    release = threading.Event()

    class BlockingProvider(FakeAIProvider):
        def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
            entered.set()
            assert release.wait(timeout=5)
            return super().generate(request)

    outcomes: list[object] = []

    def runner() -> None:
        session = TestingSessionLocal()
        try:
            outcomes.append(
                AgentExecutionService(session, BlockingProvider()).run_execution(
                    organization_id=org_id,
                    agent_id=agent.id,
                    execution_id=started.execution_id,
                )
            )
        except Exception as exc:
            outcomes.append(exc)
        finally:
            session.close()

    thread = threading.Thread(target=runner)
    thread.start()
    assert entered.wait(timeout=5)
    other = TestingSessionLocal()
    try:
        row = other.get(AgentExecution, started.execution_id)
        assert row is not None
        row.started_at = datetime.now(UTC) - timedelta(hours=1)
        other.commit()
        recovered = AgentExecutionService(
            other, stale_timeout_seconds=1
        ).recover_stale_running_executions(
            organization_id=org_id,
            agent_id=agent.id,
            execution_id=started.execution_id,
        )
        assert recovered == 1
    finally:
        other.close()
    release.set()
    thread.join(timeout=5)
    result = outcomes[0]
    assert not isinstance(result, Exception)
    assert result.status == AgentExecutionStatus.FAILED  # type: ignore[union-attr]
    assert result.error == STALE_EXECUTION_MESSAGE  # type: ignore[union-attr]
    persisted = db.get(AgentExecution, started.execution_id)
    assert persisted is not None
    db.refresh(persisted)
    assert persisted.status == AgentExecutionStatus.FAILED
    assert persisted.error == STALE_EXECUTION_MESSAGE


def test_in_flight_cancel_wins_over_recovery(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    started = AgentExecutionService(db, FakeAIProvider()).start_execution(
        organization_id=org_id, agent_id=agent.id, user_input="Hello"
    )
    cancelled = AgentExecutionService(db).cancel_execution(
        organization_id=org_id,
        agent_id=agent.id,
        execution_id=started.execution_id,
    )
    assert cancelled.status == AgentExecutionStatus.CANCELLED
    other = TestingSessionLocal()
    try:
        row = other.get(AgentExecution, started.execution_id)
        assert row is not None
        row.started_at = datetime.now(UTC) - timedelta(hours=1)
        other.commit()
        recovered = AgentExecutionService(
            other, stale_timeout_seconds=1
        ).recover_stale_running_executions(
            organization_id=org_id,
            agent_id=agent.id,
            execution_id=started.execution_id,
        )
        assert recovered == 0
    finally:
        other.close()
    persisted = db.get(AgentExecution, started.execution_id)
    assert persisted is not None
    db.refresh(persisted)
    assert persisted.status == AgentExecutionStatus.CANCELLED


def test_history_list_recovers_stale_running(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    old = datetime.now(UTC) - timedelta(hours=2)
    row = _running(db, org_id, agent, started_at=old)
    body = client.get(
        f"/api/v1/agents/{agent.id}/executions",
        headers=_headers(created["access_token"]),
    ).json()
    assert body["items"][0]["id"] == row.id
    assert body["items"][0]["status"] == "FAILED"
    assert body["items"][0]["error_preview"] == STALE_EXECUTION_MESSAGE
    assert body["items"][0]["completed_at"]
    assert body["items"][0]["duration_ms"] is not None
    db.refresh(row)
    assert row.status == AgentExecutionStatus.FAILED
    assert row.failure_category == ExecutionFailureCategory.EXECUTION_ERROR


def test_history_detail_recovers_stale_running(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    member_token = _add_org_member(
        db, org_id, email="member@example.com", role=MembershipRole.MEMBER
    )
    old = datetime.now(UTC) - timedelta(hours=2)
    row = _running(db, org_id, agent, started_at=old)
    body = client.get(
        f"/api/v1/agents/{agent.id}/executions/{row.id}",
        headers=_headers(member_token),
    ).json()
    assert body["status"] == "FAILED"
    assert body["error"] == STALE_EXECUTION_MESSAGE
    assert body["failure_category"] == "EXECUTION_ERROR"
    assert "traceback" not in body["error"].lower()
    assert "sql" not in body["error"].lower()
    assert body["completed_at"]
    assert body["duration_ms"] is not None


def test_run_of_recovered_execution_conflicts(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    row = _running(
        db, org_id, agent, started_at=datetime.now(UTC) - timedelta(seconds=5)
    )
    _stale_service(db).recover_stale_running_executions(
        organization_id=org_id, agent_id=agent.id, execution_id=row.id
    )
    with pytest.raises(ConflictError):
        AgentExecutionService(db, FakeAIProvider()).run_execution(
            organization_id=org_id,
            agent_id=agent.id,
            execution_id=row.id,
        )


def test_stale_timeout_uses_provider_loop_floor() -> None:
    configured = Settings(
        agent_execution_stale_timeout_seconds=10,
        openai_request_timeout_seconds=60,
        agent_max_tool_iterations=3,
        environment="test",
    )
    assert configured.agent_execution_stale_timeout_effective_seconds() == 240
    assert settings.agent_execution_stale_timeout_seconds == 300
    assert settings.agent_execution_stale_timeout_effective_seconds() >= 240
