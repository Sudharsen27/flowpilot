"""Lead timeline visibility for execution and auto-start activity."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProviderError
from app.models.activity_event import (
    ActivityActorType,
    ActivityEntityType,
    ActivityEvent,
    ActivityEventType,
)
from app.models.agent_execution import AgentExecution, AgentExecutionStatus
from app.services.activity_service import ActivityService
from app.services.agent_execution_service import AgentExecutionService
from app.services.agent_orchestration_service import AgentOrchestrationService
from app.services.agent_planner_service import PlannerFailureReason, PlannerResult
from app.services.orchestration_outcome import OrchestrationOutcome
from app.tools.registry import ToolRegistry
from tests.test_agent_orchestration_service import (
    CountingPlanExecutor,
    CountingPlanner,
    _plan,
    _step,
)
from tests.test_agent_runtime import FakeAIProvider, _create_agent, _headers
from tests.test_leads import _auth, _create

INBOX = "/api/v1/inbox"


def _kinds(client: TestClient, token: str, lead_id: str) -> list[str]:
    response = client.get(f"{INBOX}/{lead_id}", headers=_headers(token))
    assert response.status_code == 200
    return [item["kind"] for item in response.json()["items"]]


def _activity_for_execution(db: Session, execution_id: str) -> list[ActivityEvent]:
    return list(db.scalars(select(ActivityEvent).where(ActivityEvent.entity_id == execution_id)))


def test_execution_service_links_success_and_failure_to_the_lead(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    token = created["access_token"]
    agent = _create_agent(db, org_id)
    lead = _create(client, token, name="Bound").json()
    other = _create(client, token, name="Other").json()

    completed = AgentExecutionService(db, FakeAIProvider()).start_execution(
        organization_id=org_id,
        agent_id=agent.id,
        user_input="Say hello",
        initiated_by_user_id=created["user"]["id"],
        lead_id=lead["id"],
    )
    AgentExecutionService(db, FakeAIProvider()).run_execution(
        organization_id=org_id,
        agent_id=agent.id,
        execution_id=completed.execution_id,
    )
    success_events = _activity_for_execution(db, completed.execution_id)
    assert len(success_events) == 1
    assert success_events[0].lead_id == lead["id"]
    assert success_events[0].title == "Agent execution completed"
    assert "Hello from the agent" not in success_events[0].summary

    failed_start = AgentExecutionService(db, FakeAIProvider()).start_execution(
        organization_id=org_id,
        agent_id=agent.id,
        user_input="Say hello",
        initiated_by_user_id=created["user"]["id"],
        lead_id=lead["id"],
    )
    try:
        AgentExecutionService(
            db, FakeAIProvider(fail=ProviderError("provider down"))
        ).run_execution(
            organization_id=org_id,
            agent_id=agent.id,
            execution_id=failed_start.execution_id,
        )
    except ProviderError:
        pass
    failed_events = _activity_for_execution(db, failed_start.execution_id)
    assert len(failed_events) == 1
    assert failed_events[0].lead_id == lead["id"]
    assert failed_events[0].title == "Agent execution failed"
    assert "provider down" not in failed_events[0].summary

    listed = client.get(
        f"/api/v1/activity?lead_id={lead['id']}&entity_type=AGENT_EXECUTION",
        headers=_headers(token),
    )
    assert listed.status_code == 200
    titles = {item["title"] for item in listed.json()["items"]}
    assert titles == {"Agent execution completed", "Agent execution failed"}
    other_listed = client.get(
        f"/api/v1/activity?lead_id={other['id']}&entity_type=AGENT_EXECUTION",
        headers=_headers(token),
    )
    assert other_listed.json()["total"] == 0

    kinds = _kinds(client, token, lead["id"])
    assert "AGENT_EXECUTION_COMPLETED" in kinds
    assert "AGENT_EXECUTION_FAILED" in kinds
    assert "SALES_RUN_WAITING_APPROVAL" not in kinds
    timeline = client.get(f"{INBOX}/{lead['id']}", headers=_headers(token)).json()
    by_kind = {item["kind"]: item for item in timeline["items"]}
    assert by_kind["AGENT_EXECUTION_COMPLETED"]["body"] is None
    assert by_kind["AGENT_EXECUTION_FAILED"]["body"] is None
    assert timeline["lead"]["needs_approval"] is False


def test_orchestration_preserves_lead_and_deduplicates(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    lead = _create(client, created["access_token"]).json()
    agent = _create_agent(db, org_id)
    plan = _plan(_step("s1", "echo", {"message": "hello"}, 0))
    service = AgentOrchestrationService(
        db,
        registry=ToolRegistry(),
        planner=CountingPlanner(
            PlannerResult(success=True, plan=plan, provider="fake", model="fake-model")
        ),
        plan_executor=CountingPlanExecutor(),
    )
    result = service.orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input="Echo hello",
        lead_id=lead["id"],
    )
    assert result.outcome == OrchestrationOutcome.SUCCESS
    assert result.execution_id is not None
    execution = db.get(AgentExecution, result.execution_id)
    assert execution is not None
    service._record_activity(execution, AgentExecutionStatus.COMPLETED)
    count = db.scalar(
        select(func.count())
        .select_from(ActivityEvent)
        .where(ActivityEvent.entity_id == execution.id)
    )
    assert count == 1
    stored = _activity_for_execution(db, execution.id)[0]
    assert stored.lead_id == lead["id"]
    again = ActivityService(db).record(
        organization_id=org_id,
        event_type=ActivityEventType(stored.type),
        actor_type=ActivityActorType(stored.actor_type),
        title=stored.title,
        summary=stored.summary,
        entity_type=ActivityEntityType(stored.entity_type),
        entity_id=stored.entity_id,
        dedupe_key=stored.dedupe_key,
        lead_id=lead["id"],
    )
    assert again.id == stored.id
    assert (
        db.scalar(
            select(func.count())
            .select_from(ActivityEvent)
            .where(ActivityEvent.dedupe_key == stored.dedupe_key)
        )
        == 1
    )


def test_execution_without_a_lead_stays_organization_level(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    token = created["access_token"]
    agent = _create_agent(db, org_id)
    lead = _create(client, token).json()
    started = AgentExecutionService(db, FakeAIProvider()).start_execution(
        organization_id=org_id,
        agent_id=agent.id,
        user_input="Say hello",
        initiated_by_user_id=created["user"]["id"],
    )
    AgentExecutionService(db, FakeAIProvider()).run_execution(
        organization_id=org_id,
        agent_id=agent.id,
        execution_id=started.execution_id,
    )
    event = _activity_for_execution(db, started.execution_id)[0]
    assert event.lead_id is None
    assert "AGENT_EXECUTION_COMPLETED" not in _kinds(client, token, lead["id"])
    filtered = client.get(
        f"/api/v1/activity?lead_id={lead['id']}&entity_type=AGENT_EXECUTION",
        headers=_headers(token),
    )
    assert filtered.json()["total"] == 0


def test_cross_tenant_lead_id_is_not_attached(client: TestClient, db: Session) -> None:
    org_a = _auth(client, email="a@example.com", organization_name="Alpha")
    org_b = _auth(client, email="b@example.com", organization_name="Beta")
    agent = _create_agent(db, org_a["organization"]["id"])
    foreign_lead = _create(client, org_b["access_token"]).json()
    own_lead = _create(client, org_a["access_token"]).json()
    started = AgentExecutionService(db, FakeAIProvider()).start_execution(
        organization_id=org_a["organization"]["id"],
        agent_id=agent.id,
        user_input="Say hello",
        initiated_by_user_id=org_a["user"]["id"],
        lead_id=own_lead["id"],
    )
    execution = db.get(AgentExecution, started.execution_id)
    assert execution is not None
    execution.lead_id = foreign_lead["id"]
    db.commit()
    AgentExecutionService(db, FakeAIProvider()).run_execution(
        organization_id=org_a["organization"]["id"],
        agent_id=agent.id,
        execution_id=started.execution_id,
    )
    event = _activity_for_execution(db, started.execution_id)[0]
    assert event.lead_id is None
    foreign_timeline = client.get(
        f"{INBOX}/{foreign_lead['id']}",
        headers=_headers(org_b["access_token"]),
    )
    assert foreign_timeline.status_code == 200
    assert "AGENT_EXECUTION_COMPLETED" not in [
        item["kind"] for item in foreign_timeline.json()["items"]
    ]
    hidden = client.get(
        f"{INBOX}/{own_lead['id']}",
        headers=_headers(org_b["access_token"]),
    )
    assert hidden.status_code == 404


def test_auto_start_skipped_and_failed_appear_on_the_lead_timeline(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    token = created["access_token"]
    skipped_lead = _create(client, token, name="Skipped").json()
    failed_lead = _create(client, token, name="Failed").json()
    other_org = _auth(client, email="other@example.com", organization_name="Other")
    other_lead = _create(client, other_org["access_token"]).json()

    from app.models.lead import LeadSalesAgentAutoStartStatus
    from app.services.sales_agent_auto_start_service import (
        FAIL_SUMMARY,
        FAIL_TITLE,
        SKIP_SUMMARY,
        SKIP_TITLE,
    )

    activity = ActivityService(db)
    activity.record(
        organization_id=org_id,
        event_type=ActivityEventType.SYSTEM_EVENT,
        actor_type=ActivityActorType.SYSTEM,
        title=SKIP_TITLE,
        summary=SKIP_SUMMARY,
        entity_type=ActivityEntityType.LEAD,
        entity_id=skipped_lead["id"],
        lead_id=skipped_lead["id"],
        status=LeadSalesAgentAutoStartStatus.SKIPPED,
        dedupe_key=f"lead:{skipped_lead['id']}:AUTO_START:SKIPPED",
    )
    activity.record(
        organization_id=org_id,
        event_type=ActivityEventType.SYSTEM_EVENT,
        actor_type=ActivityActorType.SYSTEM,
        title=FAIL_TITLE,
        summary=FAIL_SUMMARY,
        entity_type=ActivityEntityType.LEAD,
        entity_id=failed_lead["id"],
        lead_id=failed_lead["id"],
        status=LeadSalesAgentAutoStartStatus.FAILED,
        dedupe_key=f"lead:{failed_lead['id']}:AUTO_START:FAILED",
    )
    db.commit()

    assert "SALES_AGENT_AUTO_START_SKIPPED" in _kinds(client, token, skipped_lead["id"])
    assert "SALES_AGENT_AUTO_START_FAILED" not in _kinds(client, token, skipped_lead["id"])
    assert "SALES_AGENT_AUTO_START_FAILED" in _kinds(client, token, failed_lead["id"])
    assert "SALES_AGENT_AUTO_START_SKIPPED" not in _kinds(client, token, failed_lead["id"])
    skipped = client.get(f"{INBOX}/{skipped_lead['id']}", headers=_headers(token)).json()
    failed = client.get(f"{INBOX}/{failed_lead['id']}", headers=_headers(token)).json()
    assert skipped["lead"]["needs_approval"] is False
    assert failed["lead"]["needs_approval"] is False
    assert all(item["kind"] != "SALES_RUN_WAITING_APPROVAL" for item in skipped["items"])
    assert all(item["kind"] != "SALES_RUN_WAITING_APPROVAL" for item in failed["items"])
    other = client.get(
        f"{INBOX}/{other_lead['id']}",
        headers=_headers(other_org["access_token"]),
    )
    assert "SALES_AGENT_AUTO_START_SKIPPED" not in [item["kind"] for item in other.json()["items"]]
    assert "SALES_AGENT_AUTO_START_FAILED" not in [item["kind"] for item in other.json()["items"]]


def test_orchestration_failure_also_keeps_the_lead(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    lead = _create(client, created["access_token"]).json()
    agent = _create_agent(db, org_id)
    service = AgentOrchestrationService(
        db,
        registry=ToolRegistry(),
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
    result = service.orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input="Do something",
        lead_id=lead["id"],
    )
    assert result.outcome == OrchestrationOutcome.PLANNING_FAILED
    assert result.execution_id is not None
    event = _activity_for_execution(db, result.execution_id)[0]
    assert event.lead_id == lead["id"]
    assert event.title == "Agent execution failed"
    kinds = _kinds(client, created["access_token"], lead["id"])
    assert "AGENT_EXECUTION_FAILED" in kinds
    assert "AGENT_EXECUTION_COMPLETED" not in kinds
