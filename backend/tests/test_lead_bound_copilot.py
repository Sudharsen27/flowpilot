"""Lead-bound sales copilot: one selected lead, stored enquiry, human send."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.provider import AIGenerateRequest, AIGenerateResult, TokenUsage
from app.models.activity_event import ActivityEvent
from app.models.agent_execution import AgentExecution
from app.models.lead import Lead
from app.models.lead_email_send import LeadEmailSend
from app.models.lead_qualification import LeadQualification
from app.models.sales_run import SalesRun
from app.models.tool_invocation import ToolInvocation
from app.services.agent_orchestration_service import (
    AgentOrchestrationService,
    OrchestrationOutcome,
)
from app.services.agent_planner_service import PlannerContext, PlannerResult
from app.tools.plan import AgentPlan, AgentPlanStep
from app.tools.schema import ToolDefinition
from tests.test_agent_runtime import _create_agent, _headers
from tests.test_lead_email_send import FakeEmailProvider, _approve, _email_settings
from tests.test_leads import _auth, _create

ENQUIRY = "We need an automation platform and would like a demo next week."
DRAFT = "Thanks for writing. A specialist can arrange a demo."
INSTRUCTION = "Qualify this lead and draft a reply."


def _analysis() -> dict[str, Any]:
    return {
        "summary": "The sender is requesting a product demo.",
        "intent": "REQUEST_DEMO",
        "qualification": "NEEDS_MORE_INFORMATION",
        "qualification_reasons": ["Budget is not stated"],
        "confidence": 0.7,
        "extracted_contact": {"name": None, "email": None, "phone": None},
        "extracted_company": {"name": None},
        "buying_signals": ["Requested a demo"],
        "missing_information": ["Budget"],
    }


class ScriptedToolProvider:
    def __init__(self) -> None:
        self.requests: list[AIGenerateRequest] = []

    def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
        self.requests.append(request)
        if request.json_schema_name == "lead_qualification":
            payload = _analysis()
        elif request.json_schema_name == "lead_response_draft":
            payload = {"response": DRAFT}
        else:
            raise AssertionError(f"Unexpected provider call: {request.json_schema_name}")
        return AIGenerateResult(
            output_text=json.dumps(payload),
            provider="fake",
            model="fake-model",
            usage=TokenUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
        )


class FixedPlanner:
    def __init__(self, planned: AgentPlan) -> None:
        self.planned = planned
        self.contexts: list[PlannerContext | None] = []

    def plan(
        self,
        user_input: str,
        available_tools: list[ToolDefinition],
        context: PlannerContext | None = None,
    ) -> PlannerResult:
        del user_input, available_tools
        self.contexts.append(context)
        return PlannerResult(
            success=True,
            plan=self.planned,
            provider="fake",
            model="fake-model",
        )


def _plan(*steps: tuple[str, str, dict[str, Any]]) -> AgentPlan:
    return AgentPlan(
        plan_id="plan-bound",
        steps=[
            AgentPlanStep(
                step_id=step_id,
                tool_name=tool_name,
                arguments=arguments,
                sequence=index,
            )
            for index, (step_id, tool_name, arguments) in enumerate(steps)
        ],
    )


def test_unknown_and_cross_tenant_leads_are_not_found(
    db: Session, client: TestClient
) -> None:
    owner = _auth(client)
    other = _auth(
        client,
        email="other@example.com",
        organization_name="Other Co",
    )
    secret = "Private enquiry from the other organization."
    foreign_lead = _create(
        client,
        other["access_token"],
        name="Other prospect",
        enquiry=secret,
    ).json()
    agent = _create_agent(db, owner["organization"]["id"])

    missing = client.post(
        f"/api/v1/agents/{agent.id}/orchestrate",
        json={"instruction": INSTRUCTION, "lead_id": "missing-lead"},
        headers=_headers(owner["access_token"]),
    )
    assert missing.status_code == 404

    crossed = client.post(
        f"/api/v1/agents/{agent.id}/orchestrate",
        json={"instruction": INSTRUCTION, "lead_id": foreign_lead["id"]},
        headers=_headers(owner["access_token"]),
    )
    assert crossed.status_code == 404
    assert secret not in crossed.text
    assert (
        db.scalar(
            select(func.count())
            .select_from(AgentExecution)
            .where(AgentExecution.organization_id == owner["organization"]["id"])
        )
        == 0
    )


def test_bound_run_qualifies_and_drafts_stored_enquiry_without_sending(
    db: Session, client: TestClient, monkeypatch: object
) -> None:
    _email_settings(monkeypatch)
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    lead = _create(
        client,
        token,
        name="Ada Prospect",
        email="ada@example.com",
        notes="Internal note that must not be qualified.",
        enquiry=ENQUIRY,
    ).json()
    provider = ScriptedToolProvider()
    planner = FixedPlanner(
        _plan(
            ("qualify", "qualify_lead", {"lead_id": lead["id"]}),
            ("draft", "create_response_draft", {"lead_id": lead["id"]}),
        )
    )
    result = AgentOrchestrationService(db, provider, planner=planner).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input=INSTRUCTION,
        lead_id=lead["id"],
    )

    assert result.outcome == OrchestrationOutcome.SUCCESS
    assert result.execution_id is not None
    assert planner.contexts[0] is not None
    assert planner.contexts[0].lead_id == lead["id"]
    execution = db.get(AgentExecution, result.execution_id)
    assert execution is not None
    assert execution.lead_id == lead["id"]
    assert execution.organization_id == org_id
    assert ENQUIRY not in json.dumps(execution.input)
    assert "Internal note" not in json.dumps(execution.input)

    qualification = db.scalar(select(LeadQualification))
    assert qualification is not None
    assert qualification.lead_id == lead["id"]
    assert qualification.enquiry == ENQUIRY
    assert "Internal note" not in qualification.enquiry
    assert provider.requests[0].json_schema_name == "lead_qualification"
    assert f"<customer_enquiry>\n{ENQUIRY}" in provider.requests[0].user_input

    queue = client.get("/api/v1/approvals", headers=_headers(token))
    assert queue.status_code == 200
    items = queue.json()["items"]
    assert len(items) == 1
    assert items[0]["lead_id"] == lead["id"]
    assert items[0]["draft"]["response"] == DRAFT
    assert items[0]["can_approve"] is True
    assert items[0]["can_send"] is False
    assert items[0]["sales_run"] is None
    draft_id = items[0]["draft_id"]

    _approve(client, token, lead["id"], draft_id)
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 0

    email = FakeEmailProvider()
    from tests.test_lead_email_send import _override_email

    _override_email(client, email)
    sent = client.post(
        f"/api/v1/leads/{lead['id']}/response-drafts/{draft_id}/send",
        json={},
        headers=_headers(token),
    )
    assert sent.status_code == 200
    assert sent.json()["status"] == "SENT"
    assert sent.json()["recipient_email"] == "ada@example.com"
    assert sent.json()["body_text"] == DRAFT
    assert email.messages[0].to == "ada@example.com"
    assert email.messages[0].body_text == DRAFT

    stored = db.get(Lead, lead["id"])
    assert stored is not None
    assert stored.status == "NEW"
    _assert_activity_hides_customer_text(db, org_id)


def test_bound_run_rejects_a_tool_call_for_a_different_lead(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    selected = _create(client, created["access_token"], enquiry=ENQUIRY).json()
    other = _create(
        client,
        created["access_token"],
        name="Other prospect",
        email="other-prospect@example.com",
        enquiry="A different stored enquiry.",
    ).json()
    provider = ScriptedToolProvider()
    result = AgentOrchestrationService(
        db,
        provider,
        planner=FixedPlanner(
            _plan(("qualify", "qualify_lead", {"lead_id": other["id"]}))
        ),
    ).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input=INSTRUCTION,
        lead_id=selected["id"],
    )

    assert result.outcome == OrchestrationOutcome.PLAN_VALIDATION_FAILED
    assert result.execution_id is not None
    execution = db.get(AgentExecution, result.execution_id)
    assert execution is not None
    assert execution.lead_id == selected["id"]
    assert provider.requests == []
    assert db.scalar(select(func.count()).select_from(LeadQualification)) == 0
    assert db.scalar(select(func.count()).select_from(ToolInvocation)) == 0
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0


def test_bound_run_does_not_call_the_provider_when_enquiry_is_empty(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    lead = _create(
        client,
        created["access_token"],
        notes="Notes are not the enquiry.",
    ).json()
    provider = ScriptedToolProvider()
    result = AgentOrchestrationService(
        db,
        provider,
        planner=FixedPlanner(
            _plan(("qualify", "qualify_lead", {"lead_id": lead["id"]}))
        ),
    ).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input=INSTRUCTION,
        lead_id=lead["id"],
    )

    assert result.outcome == OrchestrationOutcome.PLAN_VALIDATION_FAILED
    assert provider.requests == []
    assert db.scalar(select(func.count()).select_from(LeadQualification)) == 0
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0
    execution = db.get(AgentExecution, result.execution_id)
    assert execution is not None
    assert execution.lead_id == lead["id"]
    _assert_activity_hides_customer_text(db, org_id)


def _assert_activity_hides_customer_text(db: Session, organization_id: str) -> None:
    events = db.scalars(
        select(ActivityEvent).where(ActivityEvent.organization_id == organization_id)
    ).all()
    assert events
    blob = " ".join(f"{event.title} {event.summary}" for event in events)
    assert ENQUIRY not in blob
    assert DRAFT not in blob
    assert "Internal note" not in blob
    assert "Notes are not the enquiry." not in blob
