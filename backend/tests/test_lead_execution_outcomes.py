"""Lead-scoped reads of existing AgentExecution outcomes (Phase 6E.3.2)."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.agent import Agent
from app.models.agent_execution import (
    AgentExecution,
    AgentExecutionStatus,
    ExecutionFailureCategory,
)
from app.models.membership import MembershipRole
from app.services.agent_orchestration_service import AgentOrchestrationService
from app.services.agent_planner_service import PlannerFailureReason, PlannerResult
from app.services.orchestration_outcome import OrchestrationOutcome
from app.tools.registry import ToolRegistry
from tests.test_agent_api import _add_org_member, _auth, _headers
from tests.test_agent_orchestration_service import (
    CountingPlanExecutor,
    CountingPlanner,
    _plan,
    _step,
)
from tests.test_agent_runtime import _create_agent
from tests.test_leads import _create


def _execution(
    db: Session,
    organization_id: str,
    agent: Agent,
    lead_id: str | None,
    *,
    created_at: datetime,
    status: AgentExecutionStatus,
    execution_id: str | None = None,
    outcome: str | None = None,
    error: str | None = None,
    failure_category: ExecutionFailureCategory | None = None,
    input_text: str = "Qualify this lead",
    extra_output: dict[str, Any] | None = None,
    orchestration: dict[str, Any] | None = None,
) -> AgentExecution:
    output: dict[str, Any] = {
        "tool_results": [{"output": {"secret": "do-not-leak"}}],
        "plan": {"steps": [{"arguments": {"secret": "do-not-leak"}}]},
        "step_results": [{"result": {"output": {"secret": "do-not-leak"}}}],
    }
    if orchestration is not None:
        output["orchestration"] = orchestration
    elif outcome is not None:
        output["orchestration"] = {
            "outcome": outcome,
            "plan_id": "plan-1",
            "approval_required": outcome == OrchestrationOutcome.APPROVAL_REQUIRED,
            "completed_step_count": 1 if status == AgentExecutionStatus.COMPLETED else 0,
            "total_step_count": 2,
            "stopped_at_step_id": None if status == AgentExecutionStatus.COMPLETED else "step-2",
        }
    if extra_output:
        output.update(extra_output)
    row = AgentExecution(
        organization_id=organization_id,
        agent_id=agent.id,
        lead_id=lead_id,
        status=status,
        input={"text": input_text},
        output=output,
        error=error,
        failure_category=failure_category,
        provider="fake",
        model="fake-model",
        started_at=created_at,
        completed_at=created_at,
        created_at=created_at,
    )
    if execution_id is not None:
        row.id = execution_id
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_unauthenticated_lead_execution_outcomes_are_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/leads/lead-1/executions").status_code == 401
    assert client.get("/api/v1/leads/lead-1/executions/exec-1").status_code == 401


def test_missing_lead_outcomes_are_not_found(client: TestClient) -> None:
    headers = _headers(_auth(client)["access_token"])
    listed = client.get("/api/v1/leads/missing-lead/executions", headers=headers)
    assert listed.status_code == 404
    assert listed.json()["detail"] == "Lead not found"
    detail = client.get(
        "/api/v1/leads/missing-lead/executions/missing-exec",
        headers=headers,
    )
    assert detail.status_code == 404
    assert detail.json()["detail"] == "Lead not found"


def test_lead_without_executions_is_empty(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    listed = client.get(
        f"/api/v1/leads/{lead['id']}/executions",
        headers=_headers(token),
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["limit"] == 20
    assert body["offset"] == 0


def test_lists_success_and_failure_without_tool_payloads(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    other_agent = _create_agent(db, org_id, name="Other")
    lead = _create(client, token, name="Ada").json()
    other_lead = _create(client, token, name="Bea").json()
    now = datetime.now(UTC)
    long_error = "provider failed " + ("x" * 200)
    long_input = "instruction " + ("y" * 200)
    failed = _execution(
        db,
        org_id,
        agent,
        lead["id"],
        created_at=now,
        status=AgentExecutionStatus.FAILED,
        outcome=OrchestrationOutcome.TOOL_FAILED,
        error=long_error,
        failure_category=ExecutionFailureCategory.TOOL_ERROR,
        input_text=long_input,
    )
    succeeded = _execution(
        db,
        org_id,
        other_agent,
        lead["id"],
        created_at=now + timedelta(seconds=5),
        status=AgentExecutionStatus.COMPLETED,
        outcome=OrchestrationOutcome.SUCCESS,
        input_text="Draft a reply",
    )
    _execution(
        db,
        org_id,
        agent,
        other_lead["id"],
        created_at=now + timedelta(seconds=10),
        status=AgentExecutionStatus.COMPLETED,
        outcome=OrchestrationOutcome.SUCCESS,
        execution_id="other-lead-exec",
    )
    _execution(
        db,
        org_id,
        agent,
        None,
        created_at=now + timedelta(seconds=15),
        status=AgentExecutionStatus.COMPLETED,
        outcome=OrchestrationOutcome.SUCCESS,
        execution_id="unlinked-exec",
    )

    listed = client.get(
        f"/api/v1/leads/{lead['id']}/executions",
        headers=_headers(token),
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [succeeded.id, failed.id]
    assert body["items"][0]["outcome"] == "SUCCESS"
    assert body["items"][0]["status"] == "COMPLETED"
    assert body["items"][0]["agent_id"] == other_agent.id
    assert body["items"][0]["lead_id"] == lead["id"]
    assert body["items"][0]["completed_step_count"] == 1
    assert body["items"][0]["total_step_count"] == 2
    assert body["items"][0]["plan_id"] == "plan-1"
    assert body["items"][0]["approval_required"] is False
    failure = body["items"][1]
    assert failure["outcome"] == "TOOL_FAILED"
    assert failure["failure_category"] == "TOOL_ERROR"
    assert failure["stopped_at_step_id"] == "step-2"
    assert failure["error_preview"] == long_error[:120]
    assert failure["input_preview"] == long_input[:120]
    blob = listed.text
    assert "do-not-leak" not in blob
    assert "step_results" not in blob
    assert "tool_results" not in blob

    page = client.get(
        f"/api/v1/leads/{lead['id']}/executions?limit=1&offset=1",
        headers=_headers(token),
    )
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert [item["id"] for item in page.json()["items"]] == [failed.id]

    other = client.get(
        f"/api/v1/leads/{other_lead['id']}/executions",
        headers=_headers(token),
    )
    assert [item["id"] for item in other.json()["items"]] == ["other-lead-exec"]


def test_gets_success_failure_and_hides_unlinked_or_other_lead(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    lead = _create(client, token).json()
    other_lead = _create(client, token, name="Other").json()
    now = datetime.now(UTC)
    succeeded = _execution(
        db,
        org_id,
        agent,
        lead["id"],
        created_at=now,
        status=AgentExecutionStatus.COMPLETED,
        outcome=OrchestrationOutcome.SUCCESS,
        input_text="Summarize the enquiry",
    )
    failed = _execution(
        db,
        org_id,
        agent,
        lead["id"],
        created_at=now,
        status=AgentExecutionStatus.FAILED,
        outcome=OrchestrationOutcome.PLANNING_FAILED,
        error="upstream timeout",
        failure_category=ExecutionFailureCategory.PROVIDER_ERROR,
    )
    waiting = _execution(
        db,
        org_id,
        agent,
        lead["id"],
        created_at=now,
        status=AgentExecutionStatus.FAILED,
        outcome=OrchestrationOutcome.APPROVAL_REQUIRED,
        failure_category=ExecutionFailureCategory.POLICY_ERROR,
    )
    other = _execution(
        db,
        org_id,
        agent,
        other_lead["id"],
        created_at=now,
        status=AgentExecutionStatus.COMPLETED,
        outcome=OrchestrationOutcome.SUCCESS,
    )
    unlinked = _execution(
        db,
        org_id,
        agent,
        None,
        created_at=now,
        status=AgentExecutionStatus.COMPLETED,
    )

    headers = _headers(token)
    detail = client.get(
        f"/api/v1/leads/{lead['id']}/executions/{succeeded.id}",
        headers=headers,
    )
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["outcome"] == "SUCCESS"
    assert payload["input"] == "Summarize the enquiry"
    assert payload["error"] is None
    assert "do-not-leak" not in detail.text
    assert "step_results" not in detail.text

    failed_detail = client.get(
        f"/api/v1/leads/{lead['id']}/executions/{failed.id}",
        headers=headers,
    )
    assert failed_detail.status_code == 200
    assert failed_detail.json()["outcome"] == "PLANNING_FAILED"
    assert failed_detail.json()["error"] == "upstream timeout"
    assert failed_detail.json()["failure_category"] == "PROVIDER_ERROR"

    approval = client.get(
        f"/api/v1/leads/{lead['id']}/executions/{waiting.id}",
        headers=headers,
    )
    assert approval.json()["approval_required"] is True
    assert approval.json()["outcome"] == "APPROVAL_REQUIRED"

    missing = client.get(
        f"/api/v1/leads/{lead['id']}/executions/missing-exec",
        headers=headers,
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Agent execution not found"
    wrong_lead = client.get(
        f"/api/v1/leads/{lead['id']}/executions/{other.id}",
        headers=headers,
    )
    assert wrong_lead.status_code == 404
    unlinked_get = client.get(
        f"/api/v1/leads/{lead['id']}/executions/{unlinked.id}",
        headers=headers,
    )
    assert unlinked_get.status_code == 404


def test_malformed_orchestration_payload_does_not_fail_the_read(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    lead = _create(client, token).json()
    row = _execution(
        db,
        org_id,
        agent,
        lead["id"],
        created_at=datetime.now(UTC),
        status=AgentExecutionStatus.COMPLETED,
        orchestration={
            "outcome": "NOT_A_REAL_OUTCOME",
            "approval_required": "yes",
            "completed_step_count": "1",
            "plan_id": "",
            "stopped_at_step_id": 4,
        },
    )
    detail = client.get(
        f"/api/v1/leads/{lead['id']}/executions/{row.id}",
        headers=_headers(token),
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "COMPLETED"
    assert body["outcome"] is None
    assert body["approval_required"] is False
    assert body["completed_step_count"] is None
    assert body["plan_id"] is None
    assert body["stopped_at_step_id"] is None


def test_cross_tenant_lead_executions_are_hidden(client: TestClient, db: Session) -> None:
    org_a = _auth(client, email="a@example.com", organization_name="Alpha")
    org_b = _auth(client, email="b@example.com", organization_name="Beta")
    agent = _create_agent(db, org_a["organization"]["id"])
    lead = _create(client, org_a["access_token"]).json()
    own_lead = _create(client, org_b["access_token"]).json()
    row = _execution(
        db,
        org_a["organization"]["id"],
        agent,
        lead["id"],
        created_at=datetime.now(UTC),
        status=AgentExecutionStatus.COMPLETED,
        outcome=OrchestrationOutcome.SUCCESS,
    )
    foreign_list = client.get(
        f"/api/v1/leads/{lead['id']}/executions",
        headers=_headers(org_b["access_token"]),
    )
    assert foreign_list.status_code == 404
    assert foreign_list.json()["detail"] == "Lead not found"
    foreign_get = client.get(
        f"/api/v1/leads/{lead['id']}/executions/{row.id}",
        headers=_headers(org_b["access_token"]),
    )
    assert foreign_get.status_code == 404
    own = client.get(
        f"/api/v1/leads/{own_lead['id']}/executions",
        headers=_headers(org_b["access_token"]),
    )
    assert own.status_code == 200
    assert own.json()["items"] == []


def test_member_can_read_lead_execution_outcomes(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    member = _add_org_member(db, org_id, email="member@example.com", role=MembershipRole.MEMBER)
    agent = _create_agent(db, org_id)
    lead = _create(client, created["access_token"]).json()
    row = _execution(
        db,
        org_id,
        agent,
        lead["id"],
        created_at=datetime.now(UTC),
        status=AgentExecutionStatus.CANCELLED,
        error="Execution was cancelled.",
    )
    headers = _headers(member)
    listed = client.get(f"/api/v1/leads/{lead['id']}/executions", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == row.id
    assert listed.json()["items"][0]["status"] == "CANCELLED"
    assert listed.json()["items"][0]["outcome"] is None
    detail = client.get(
        f"/api/v1/leads/{lead['id']}/executions/{row.id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["error"] == "Execution was cancelled."


def test_pagination_bounds_are_rejected(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    headers = _headers(token)
    assert (
        client.get(
            f"/api/v1/leads/{lead['id']}/executions?limit=0",
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.get(
            f"/api/v1/leads/{lead['id']}/executions?limit=51",
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.get(
            f"/api/v1/leads/{lead['id']}/executions?offset=-1",
            headers=headers,
        ).status_code
        == 422
    )


def test_orchestration_records_the_lead_on_activity_and_the_read_api(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    user_id = created["user"]["id"]
    token = created["access_token"]
    agent = _create_agent(db, org_id)
    lead = _create(client, token, name="Linked").json()
    other = _create(client, token, name="Unrelated").json()
    plan = _plan(_step("s1", "echo", {"message": "hello"}, 0))
    registry = ToolRegistry()
    success = AgentOrchestrationService(
        db,
        registry=registry,
        planner=CountingPlanner(
            PlannerResult(success=True, plan=plan, provider="fake", model="fake-model")
        ),
        plan_executor=CountingPlanExecutor(),
    )
    completed = success.orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=user_id,
        user_input="Echo hello",
        lead_id=lead["id"],
    )
    assert completed.outcome == OrchestrationOutcome.SUCCESS
    failed_service = AgentOrchestrationService(
        db,
        registry=registry,
        planner=CountingPlanner(
            PlannerResult(
                success=False,
                error="upstream timeout",
                failure_reason=PlannerFailureReason.PROVIDER_ERROR,
                provider="fake",
                model="fake-model",
            )
        ),
        plan_executor=CountingPlanExecutor(),
    )
    failed = failed_service.orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=user_id,
        user_input="Do the risky thing",
        lead_id=lead["id"],
    )
    assert failed.outcome == OrchestrationOutcome.PLANNING_FAILED

    listed = client.get(
        f"/api/v1/leads/{lead['id']}/executions",
        headers=_headers(token),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    outcomes = {item["id"]: item["outcome"] for item in listed.json()["items"]}
    assert outcomes[completed.execution_id] == "SUCCESS"
    assert outcomes[failed.execution_id] == "PLANNING_FAILED"

    events = list(
        db.scalars(
            select(ActivityEvent).where(
                ActivityEvent.organization_id == org_id,
                ActivityEvent.entity_type == "AGENT_EXECUTION",
            )
        )
    )
    by_execution = {event.entity_id: event for event in events}
    assert by_execution[completed.execution_id].lead_id == lead["id"]
    assert by_execution[failed.execution_id].lead_id == lead["id"]
    assert by_execution[completed.execution_id].status == "COMPLETED"
    assert by_execution[failed.execution_id].status == "FAILED"

    filtered = client.get(
        f"/api/v1/activity?lead_id={lead['id']}&entity_type=AGENT_EXECUTION",
        headers=_headers(token),
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 2
    unrelated = client.get(
        f"/api/v1/activity?lead_id={other['id']}&entity_type=AGENT_EXECUTION",
        headers=_headers(token),
    )
    assert unrelated.json()["total"] == 0
