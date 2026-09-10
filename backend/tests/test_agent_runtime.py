import threading
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.provider import AIGenerateRequest, AIGenerateResult, TokenUsage
from app.api.deps import get_ai_provider
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ProviderError,
    ProviderNotConfiguredError,
    ValidationError,
)
from app.main import app
from app.models.agent import Agent, AgentStatus, AgentType
from app.models.agent_execution import (
    AgentExecution,
    AgentExecutionStatus,
    ExecutionFailureCategory,
)
from app.models.membership import MembershipRole
from app.models.tool_invocation import ToolInvocation
from app.services.agent_execution_service import AgentExecutionService
from app.services.agent_service import AgentService
from app.services.tool_execution_service import ToolExecutionError
from app.tools.base import Tool
from app.tools.echo import EchoTool
from app.tools.registry import ToolRegistry
from app.tools.schema import ToolCall, ToolContext, ToolRiskLevel
from tests.conftest import register_payload


class FakeAIProvider:
    def __init__(
        self,
        *,
        output: str = "Hello from the agent",
        fail: Exception | None = None,
    ) -> None:
        self.output = output
        self.fail = fail
        self.calls: list[AIGenerateRequest] = []

    def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
        self.calls.append(request)
        if self.fail is not None:
            raise self.fail
        return AIGenerateResult(
            output_text=self.output,
            provider="fake",
            model="fake-model",
            usage=TokenUsage(prompt_tokens=3, completion_tokens=5, total_tokens=8),
        )


class FailingRuntimeTool(Tool):
    name = "fail_tool"
    description = "Always fails after validation. Test only."
    risk_level = ToolRiskLevel.LOW
    input_model = EchoTool.input_model
    output_model = EchoTool.output_model

    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        raise ToolExecutionError("boom")


@pytest.fixture
def fake_provider() -> FakeAIProvider:
    return FakeAIProvider()


@pytest.fixture
def api_client(
    client: TestClient, fake_provider: FakeAIProvider
) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_ai_provider] = lambda: fake_provider
    yield client
    app.dependency_overrides.pop(get_ai_provider, None)


def _auth(client: TestClient, **kwargs: Any) -> dict[str, Any]:
    return client.post("/api/v1/auth/register", json=register_payload(**kwargs)).json()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_agent(
    db: Session,
    organization_id: str,
    *,
    status: AgentStatus = AgentStatus.ACTIVE,
    name: str = "Sales helper",
) -> Agent:
    return AgentService(db).create(
        organization_id=organization_id,
        role=MembershipRole.OWNER,
        name=name,
        agent_type=AgentType.SALES,
        description="Qualify inbound interest",
        system_instructions="You are a concise sales assistant.",
        status=status,
    )


def test_agent_creation_belongs_to_organization(db: Session, client: TestClient) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    assert agent.organization_id == created["organization"]["id"]
    assert agent.status == AgentStatus.ACTIVE
    loaded = AgentService(db).get(created["organization"]["id"], agent.id)
    assert loaded is not None
    assert loaded.id == agent.id


def test_agent_not_visible_cross_tenant(db: Session, client: TestClient) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    agent = _create_agent(db, first["organization"]["id"])
    assert AgentService(db).get(second["organization"]["id"], agent.id) is None


def test_invalid_agent_status_rejected_on_execute(
    db: Session, client: TestClient, fake_provider: FakeAIProvider
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"], status=AgentStatus.DRAFT)
    service = AgentExecutionService(db, fake_provider)
    with pytest.raises(ValidationError, match="DRAFT"):
        service.execute(
            organization_id=created["organization"]["id"],
            agent_id=agent.id,
            user_input="Hello",
            initiated_by_user_id=created["user"]["id"],
        )
    assert db.query(AgentExecution).count() == 0
    assert fake_provider.calls == []


def test_paused_agent_rejected(
    db: Session, client: TestClient, fake_provider: FakeAIProvider
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"], status=AgentStatus.PAUSED)
    with pytest.raises(ValidationError, match="PAUSED"):
        AgentExecutionService(db, fake_provider).execute(
            organization_id=created["organization"]["id"],
            agent_id=agent.id,
            user_input="Hello",
        )


def test_successful_execution_records_completed_result(
    db: Session, client: TestClient, fake_provider: FakeAIProvider
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    result = AgentExecutionService(db, fake_provider).execute(
        organization_id=created["organization"]["id"],
        agent_id=agent.id,
        user_input="Summarize this lead",
        initiated_by_user_id=created["user"]["id"],
    )
    assert result.status == AgentExecutionStatus.COMPLETED
    assert result.output == "Hello from the agent"
    assert result.provider == "fake"
    assert result.model == "fake-model"
    assert result.usage is not None
    assert result.usage.total_tokens == 8

    execution = db.get(AgentExecution, result.execution_id)
    assert execution is not None
    assert execution.organization_id == created["organization"]["id"]
    assert execution.agent_id == agent.id
    assert execution.status == AgentExecutionStatus.COMPLETED
    assert execution.input == {"text": "Summarize this lead"}
    assert execution.output is not None
    assert execution.output["text"] == "Hello from the agent"
    assert execution.started_at is not None
    assert execution.completed_at is not None
    assert execution.failure_category is None
    assert execution.error is None
    assert fake_provider.calls[0].system_instructions == "You are a concise sales assistant."


def test_missing_api_key_records_failed_execution(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    provider = FakeAIProvider(
        fail=ProviderNotConfiguredError("OPENAI_API_KEY is not configured")
    )
    with pytest.raises(ProviderNotConfiguredError) as exc:
        AgentExecutionService(db, provider).execute(
            organization_id=created["organization"]["id"],
            agent_id=agent.id,
            user_input="Hello",
        )
    execution = db.get(AgentExecution, exc.value.content["execution_id"])
    assert execution is not None
    assert execution.status == AgentExecutionStatus.FAILED
    assert execution.error == "OPENAI_API_KEY is not configured"
    assert execution.failure_category == ExecutionFailureCategory.CONFIGURATION_ERROR


def test_failed_provider_call_is_recorded(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    provider = FakeAIProvider(fail=ProviderError("upstream timeout"))
    with pytest.raises(ProviderError) as exc:
        AgentExecutionService(db, provider).execute(
            organization_id=created["organization"]["id"],
            agent_id=agent.id,
            user_input="Hello",
        )
    execution_id = exc.value.content["execution_id"]
    execution = db.get(AgentExecution, execution_id)
    assert execution is not None
    assert execution.status == AgentExecutionStatus.FAILED
    assert execution.error == "upstream timeout"
    assert execution.failure_category == ExecutionFailureCategory.PROVIDER_ERROR
    assert execution.completed_at is not None
    assert execution.started_at is not None


def test_missing_agent_is_not_found(
    db: Session, client: TestClient, fake_provider: FakeAIProvider
) -> None:
    created = _auth(client)
    with pytest.raises(NotFoundError):
        AgentExecutionService(db, fake_provider).execute(
            organization_id=created["organization"]["id"],
            agent_id="00000000-0000-0000-0000-000000000000",
            user_input="Hello",
        )


def test_cross_tenant_execution_rejected(
    db: Session, client: TestClient, fake_provider: FakeAIProvider
) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    agent = _create_agent(db, first["organization"]["id"])
    with pytest.raises(NotFoundError):
        AgentExecutionService(db, fake_provider).execute(
            organization_id=second["organization"]["id"],
            agent_id=agent.id,
            user_input="Hello",
        )
    assert db.query(AgentExecution).count() == 0


def test_execute_requires_authentication(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/agents/not-a-real-id/execute",
        json={"input": "Hello"},
    )
    assert response.status_code == 401


def test_execute_api_success(
    db: Session, api_client: TestClient, fake_provider: FakeAIProvider
) -> None:
    created = _auth(api_client)
    agent = _create_agent(db, created["organization"]["id"])
    response = api_client.post(
        f"/api/v1/agents/{agent.id}/execute",
        json={"input": "Hello there"},
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["output"] == "Hello from the agent"
    assert body["provider"] == "fake"
    assert body["model"] == "fake-model"
    assert body["usage"]["total_tokens"] == 8
    assert body["execution_id"]
    assert fake_provider.calls


def test_execute_api_validation_error(api_client: TestClient) -> None:
    created = _auth(api_client)
    response = api_client.post(
        "/api/v1/agents/not-a-real-id/execute",
        json={"input": ""},
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 422


def test_execute_api_draft_agent(db: Session, api_client: TestClient) -> None:
    created = _auth(api_client)
    agent = _create_agent(db, created["organization"]["id"], status=AgentStatus.DRAFT)
    response = api_client.post(
        f"/api/v1/agents/{agent.id}/execute",
        json={"input": "Hello"},
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 400
    assert "DRAFT" in response.json()["detail"]


def test_execute_api_provider_failure(db: Session, client: TestClient) -> None:
    failing = FakeAIProvider(fail=ProviderError("model unavailable"))
    app.dependency_overrides[get_ai_provider] = lambda: failing
    try:
        created = _auth(client)
        agent = _create_agent(db, created["organization"]["id"])
        response = client.post(
            f"/api/v1/agents/{agent.id}/execute",
            json={"input": "Hello"},
            headers=_headers(created["access_token"]),
        )
        assert response.status_code == 502
        body = response.json()
        assert body["status"] == "FAILED"
        assert body["execution_id"]
        assert "model unavailable" in body["error"]
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)


def test_execute_api_cross_tenant(db: Session, api_client: TestClient) -> None:
    first = _auth(api_client, email="a@example.com", organization_name="Alpha")
    second = _auth(api_client, email="b@example.com", organization_name="Beta")
    agent = _create_agent(db, first["organization"]["id"])
    response = api_client.post(
        f"/api/v1/agents/{agent.id}/execute",
        json={"input": "Hello"},
        headers=_headers(second["access_token"]),
    )
    assert response.status_code == 404


class ScriptedAIProvider:
    def __init__(self, responses: list[AIGenerateResult]) -> None:
        self.responses = list(responses)
        self.calls: list[AIGenerateRequest] = []

    def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
        self.calls.append(request)
        if not self.responses:
            raise AssertionError("Unexpected extra provider call")
        return self.responses.pop(0)


def test_runtime_tool_call_round_trip(db: Session, client: TestClient) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    registry = ToolRegistry()
    registry.register(EchoTool())
    provider = ScriptedAIProvider(
        [
            AIGenerateResult(
                output_text="",
                provider="fake",
                model="fake-model",
                tool_calls=[
                    ToolCall(id="call-1", name="echo", arguments={"message": "hello"})
                ],
            ),
            AIGenerateResult(
                output_text="Echoed hello",
                provider="fake",
                model="fake-model",
            ),
        ]
    )
    result = AgentExecutionService(db, provider, registry=registry).execute(
        organization_id=created["organization"]["id"],
        agent_id=agent.id,
        user_input="Use echo",
        initiated_by_user_id=created["user"]["id"],
    )
    assert result.status == AgentExecutionStatus.COMPLETED
    assert result.output == "Echoed hello"
    assert len(provider.calls) == 2
    assert provider.calls[0].tools[0].name == "echo"
    assert provider.calls[1].history[0].tool_calls[0].name == "echo"
    assert "hello" in (provider.calls[1].history[1].content or "")
    invocation = db.query(ToolInvocation).one()
    assert invocation.status == "SUCCESS"
    assert invocation.organization_id == created["organization"]["id"]


def test_runtime_max_tool_iterations_enforced(db: Session, client: TestClient) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    registry = ToolRegistry()
    registry.register(EchoTool())
    repeating = AIGenerateResult(
        output_text="",
        provider="fake",
        model="fake-model",
        tool_calls=[ToolCall(id="call-loop", name="echo", arguments={"message": "hello"})],
    )
    provider = ScriptedAIProvider([repeating, repeating, repeating, repeating])
    with pytest.raises(ProviderError, match="Maximum tool-call iterations exceeded"):
        AgentExecutionService(
            db, provider, registry=registry, max_tool_iterations=2
        ).execute(
            organization_id=created["organization"]["id"],
            agent_id=agent.id,
            user_input="Loop",
        )
    execution = db.query(AgentExecution).one()
    assert execution.status == AgentExecutionStatus.FAILED
    assert execution.error == "Maximum tool-call iterations exceeded"
    assert execution.failure_category == ExecutionFailureCategory.EXECUTION_ERROR


def test_ready_agent_can_execute(
    db: Session, client: TestClient, fake_provider: FakeAIProvider
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"], status=AgentStatus.READY)
    result = AgentExecutionService(db, fake_provider).execute(
        organization_id=created["organization"]["id"],
        agent_id=agent.id,
        user_input="Hello",
    )
    assert result.status == AgentExecutionStatus.COMPLETED
    assert db.query(AgentExecution).count() == 1
    assert db.query(AgentExecution).one().status == AgentExecutionStatus.COMPLETED
    assert db.query(AgentExecution).one().error is None


def test_unexpected_exception_records_failed_execution(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    provider = FakeAIProvider(fail=RuntimeError("boom with sk-secretvalue123"))
    with pytest.raises(ProviderError) as exc:
        AgentExecutionService(db, provider).execute(
            organization_id=created["organization"]["id"],
            agent_id=agent.id,
            user_input="Hello",
        )
    assert "sk-secretvalue123" not in str(exc.value.content)
    assert exc.value.content["error"] == "AI provider request failed"
    assert db.query(AgentExecution).count() == 1
    execution = db.query(AgentExecution).one()
    assert execution.status == AgentExecutionStatus.FAILED
    assert execution.status != AgentExecutionStatus.RUNNING
    assert execution.error == "AI provider request failed"
    assert execution.failure_category == ExecutionFailureCategory.EXECUTION_ERROR
    assert execution.output is None
    assert execution.completed_at is not None
    assert "sk-secretvalue123" not in (execution.error or "")


def test_tool_failure_fails_parent_and_finalizes_invocation(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    registry = ToolRegistry()
    registry.register(FailingRuntimeTool())
    provider = ScriptedAIProvider(
        [
            AIGenerateResult(
                output_text="",
                provider="fake",
                model="fake-model",
                tool_calls=[
                    ToolCall(id="call-1", name="fail_tool", arguments={"message": "hello"})
                ],
            )
        ]
    )
    with pytest.raises(ProviderError, match="boom"):
        AgentExecutionService(db, provider, registry=registry).execute(
            organization_id=created["organization"]["id"],
            agent_id=agent.id,
            user_input="Use fail_tool",
        )
    assert db.query(AgentExecution).count() == 1
    execution = db.query(AgentExecution).one()
    assert execution.status == AgentExecutionStatus.FAILED
    assert execution.error == "boom"
    assert execution.failure_category == ExecutionFailureCategory.TOOL_ERROR
    invocation = db.query(ToolInvocation).one()
    assert invocation.status == "FAILED"
    assert invocation.error == "boom"
    assert invocation.completed_at is not None


def test_provider_failure_creates_one_failed_record(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    provider = FakeAIProvider(fail=ProviderError("upstream timeout"))
    with pytest.raises(ProviderError):
        AgentExecutionService(db, provider).execute(
            organization_id=created["organization"]["id"],
            agent_id=agent.id,
            user_input="Hello",
        )
    assert db.query(AgentExecution).count() == 1


def test_execute_api_unexpected_exception_hides_secrets(
    db: Session, client: TestClient
) -> None:
    failing = FakeAIProvider(fail=RuntimeError("trace sk-abc Bearer secret.token"))
    app.dependency_overrides[get_ai_provider] = lambda: failing
    try:
        created = _auth(client)
        agent = _create_agent(db, created["organization"]["id"])
        response = client.post(
            f"/api/v1/agents/{agent.id}/execute",
            json={"input": "Hello"},
            headers=_headers(created["access_token"]),
        )
        assert response.status_code == 502
        body = response.json()
        assert body["status"] == "FAILED"
        assert body["error"] == "AI provider request failed"
        serialized = str(body)
        assert "sk-abc" not in serialized
        assert "secret.token" not in serialized
        assert "Traceback" not in serialized
        execution = db.get(AgentExecution, body["execution_id"])
        assert execution is not None
        assert execution.status == AgentExecutionStatus.FAILED
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)


def test_start_commits_running_visible_to_another_session(
    db: Session, client: TestClient, fake_provider: FakeAIProvider
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    started = AgentExecutionService(db, fake_provider).start_execution(
        organization_id=created["organization"]["id"],
        agent_id=agent.id,
        user_input="Hello",
        initiated_by_user_id=created["user"]["id"],
    )
    assert started.status == AgentExecutionStatus.RUNNING
    assert started.execution_id
    from tests.conftest import TestingSessionLocal

    other = TestingSessionLocal()
    try:
        row = other.get(AgentExecution, started.execution_id)
        assert row is not None
        assert row.status == AgentExecutionStatus.RUNNING
        assert row.completed_at is None
        assert row.failure_category is None
        assert row.started_at is not None
    finally:
        other.close()
    assert fake_provider.calls == []


def test_start_then_run_completes(
    db: Session, client: TestClient, fake_provider: FakeAIProvider
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    service = AgentExecutionService(db, fake_provider)
    started = service.start_execution(
        organization_id=org_id,
        agent_id=agent.id,
        user_input="Hello",
        initiated_by_user_id=created["user"]["id"],
    )
    result = service.run_execution(
        organization_id=org_id,
        agent_id=agent.id,
        execution_id=started.execution_id,
    )
    assert result.status == AgentExecutionStatus.COMPLETED
    assert result.execution_id == started.execution_id
    execution = db.get(AgentExecution, started.execution_id)
    assert execution is not None
    assert execution.status == AgentExecutionStatus.COMPLETED
    assert execution.completed_at is not None
    assert execution.failure_category is None


def test_run_provider_failure_persists_failed(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    service = AgentExecutionService(db, FakeAIProvider())
    started = service.start_execution(
        organization_id=org_id, agent_id=agent.id, user_input="Hello"
    )
    failing = AgentExecutionService(db, FakeAIProvider(fail=ProviderError("upstream")))
    with pytest.raises(ProviderError):
        failing.run_execution(
            organization_id=org_id,
            agent_id=agent.id,
            execution_id=started.execution_id,
        )
    execution = db.get(AgentExecution, started.execution_id)
    assert execution is not None
    assert execution.status == AgentExecutionStatus.FAILED
    assert execution.failure_category == ExecutionFailureCategory.PROVIDER_ERROR
    assert execution.completed_at is not None


def test_completed_execution_cannot_run_again(
    db: Session, client: TestClient, fake_provider: FakeAIProvider
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    service = AgentExecutionService(db, fake_provider)
    started = service.start_execution(
        organization_id=org_id, agent_id=agent.id, user_input="Hello"
    )
    service.run_execution(
        organization_id=org_id, agent_id=agent.id, execution_id=started.execution_id
    )
    with pytest.raises(ConflictError, match="current status"):
        service.run_execution(
            organization_id=org_id, agent_id=agent.id, execution_id=started.execution_id
        )
    assert db.query(AgentExecution).count() == 1
    assert len(fake_provider.calls) == 1


def test_failed_execution_cannot_run_again(db: Session, client: TestClient) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    service = AgentExecutionService(db, FakeAIProvider())
    started = service.start_execution(
        organization_id=org_id, agent_id=agent.id, user_input="Hello"
    )
    with pytest.raises(ProviderError):
        AgentExecutionService(db, FakeAIProvider(fail=ProviderError("nope"))).run_execution(
            organization_id=org_id,
            agent_id=agent.id,
            execution_id=started.execution_id,
        )
    with pytest.raises(ConflictError):
        AgentExecutionService(db, FakeAIProvider()).run_execution(
            organization_id=org_id,
            agent_id=agent.id,
            execution_id=started.execution_id,
        )


def test_claimed_running_execution_cannot_run_twice(
    db: Session, client: TestClient, fake_provider: FakeAIProvider
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    service = AgentExecutionService(db, fake_provider)
    started = service.start_execution(
        organization_id=org_id, agent_id=agent.id, user_input="Hello"
    )
    execution = db.get(AgentExecution, started.execution_id)
    assert execution is not None
    execution.output = {"claimed": True}
    db.commit()
    with pytest.raises(ConflictError):
        service.run_execution(
            organization_id=org_id,
            agent_id=agent.id,
            execution_id=started.execution_id,
        )
    assert fake_provider.calls == []


def test_concurrent_run_executes_provider_once(
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

    blocking = BlockingProvider()
    outcomes: list[object] = []

    def runner() -> None:
        from tests.conftest import TestingSessionLocal

        session = TestingSessionLocal()
        try:
            outcomes.append(
                AgentExecutionService(session, blocking).run_execution(
                    organization_id=org_id,
                    agent_id=agent.id,
                    execution_id=started.execution_id,
                )
            )
        except Exception as exc:
            outcomes.append(exc)
        finally:
            session.close()

    first = threading.Thread(target=runner)
    first.start()
    assert entered.wait(timeout=5)
    second = threading.Thread(target=runner)
    second.start()
    second.join(timeout=5)
    release.set()
    first.join(timeout=5)
    completed = [
        item
        for item in outcomes
        if getattr(item, "status", None) == AgentExecutionStatus.COMPLETED
    ]
    conflicts = [item for item in outcomes if isinstance(item, ConflictError)]
    assert len(completed) == 1
    assert len(conflicts) == 1
    assert len(blocking.calls) == 1


def test_run_wrong_agent_returns_not_found(
    db: Session, client: TestClient, fake_provider: FakeAIProvider
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    first = _create_agent(db, org_id, name="One")
    second = _create_agent(db, org_id, name="Two")
    service = AgentExecutionService(db, fake_provider)
    started = service.start_execution(
        organization_id=org_id, agent_id=first.id, user_input="Hello"
    )
    with pytest.raises(NotFoundError):
        service.run_execution(
            organization_id=org_id,
            agent_id=second.id,
            execution_id=started.execution_id,
        )


def test_start_run_api_and_history_running(
    db: Session, api_client: TestClient, fake_provider: FakeAIProvider
) -> None:
    created = _auth(api_client)
    agent = _create_agent(db, created["organization"]["id"])
    headers = _headers(created["access_token"])
    started = api_client.post(
        f"/api/v1/agents/{agent.id}/executions",
        json={"input": "Hello there"},
        headers=headers,
    )
    assert started.status_code == 200
    body = started.json()
    assert body["status"] == "RUNNING"
    assert body["execution_id"]
    assert fake_provider.calls == []
    listed = api_client.get(f"/api/v1/agents/{agent.id}/executions", headers=headers)
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert item["id"] == body["execution_id"]
    assert item["status"] == "RUNNING"
    assert item["duration_ms"] is None
    assert item["failure_category"] is None
    assert "tool_results" not in item
    detail = api_client.get(
        f"/api/v1/agents/{agent.id}/executions/{body['execution_id']}",
        headers=headers,
    )
    assert detail.json()["output"] is None
    assert "claimed" not in str(detail.json())
    ran = api_client.post(
        f"/api/v1/agents/{agent.id}/executions/{body['execution_id']}/run",
        headers=headers,
    )
    assert ran.status_code == 200
    assert ran.json()["status"] == "COMPLETED"
    assert ran.json()["execution_id"] == body["execution_id"]
    again = api_client.post(
        f"/api/v1/agents/{agent.id}/executions/{body['execution_id']}/run",
        headers=headers,
    )
    assert again.status_code == 409


def test_run_api_cross_tenant_and_unauthenticated(
    db: Session, api_client: TestClient, fake_provider: FakeAIProvider
) -> None:
    first = _auth(api_client, email="a@example.com", organization_name="Alpha")
    second = _auth(api_client, email="b@example.com", organization_name="Beta")
    agent = _create_agent(db, first["organization"]["id"])
    headers = _headers(first["access_token"])
    started = api_client.post(
        f"/api/v1/agents/{agent.id}/executions",
        json={"input": "Hello"},
        headers=headers,
    ).json()
    cross = api_client.post(
        f"/api/v1/agents/{agent.id}/executions/{started['execution_id']}/run",
        headers=_headers(second["access_token"]),
    )
    assert cross.status_code == 404
    unauth = api_client.post(
        f"/api/v1/agents/{agent.id}/executions/{started['execution_id']}/run"
    )
    assert unauth.status_code == 401
    assert fake_provider.calls == []


def test_execute_wrapper_creates_one_execution(
    db: Session, client: TestClient, fake_provider: FakeAIProvider
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    result = AgentExecutionService(db, fake_provider).execute(
        organization_id=created["organization"]["id"],
        agent_id=agent.id,
        user_input="Hello",
    )
    assert result.status == AgentExecutionStatus.COMPLETED
    assert db.query(AgentExecution).count() == 1
