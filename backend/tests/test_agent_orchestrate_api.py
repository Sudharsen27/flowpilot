"""Phase 6D.7 — authenticated POST /agents/{id}/orchestrate."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_agent_orchestration_service
from app.main import app
from app.models.agent_execution import AgentExecutionStatus, ExecutionFailureCategory
from app.models.membership import MembershipRole
from app.services.agent_orchestration_service import (
    OrchestrationOutcome,
    OrchestrationResult,
)
from tests.test_agent_api import _add_org_member, _auth, _headers
from tests.test_agent_runtime import _create_agent


def _override_orchestration(fake: MagicMock) -> None:
    app.dependency_overrides[get_agent_orchestration_service] = lambda: fake


def _clear_orchestration_override() -> None:
    app.dependency_overrides.pop(get_agent_orchestration_service, None)


def _fake_success(**overrides: Any) -> OrchestrationResult:
    payload = {
        "execution_id": "exec-1",
        "outcome": OrchestrationOutcome.SUCCESS,
        "execution_status": AgentExecutionStatus.COMPLETED,
        "plan_id": "plan-1",
        "approval_required": False,
        "completed_step_count": 1,
        "total_step_count": 1,
        "provider": "fake",
        "model": "fake-model",
    }
    payload.update(overrides)
    return OrchestrationResult(**payload)


def test_orchestrate_authenticated_success(db: Session, client: TestClient) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    fake = MagicMock()
    fake.orchestrate.return_value = _fake_success()
    _override_orchestration(fake)
    try:
        instruction = "Find new website leads from today and qualify them."
        response = client.post(
            f"/api/v1/agents/{agent.id}/orchestrate",
            json={"instruction": instruction},
            headers=_headers(created["access_token"]),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "SUCCESS"
        assert body["execution_id"] == "exec-1"
        assert body["approval_required"] is False
        fake.orchestrate.assert_called_once_with(
            organization_id=created["organization"]["id"],
            agent_id=agent.id,
            initiated_by_user_id=created["user"]["id"],
            user_input=instruction,
        )
    finally:
        _clear_orchestration_override()


def test_orchestrate_trims_instruction(db: Session, client: TestClient) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    fake = MagicMock()
    fake.orchestrate.return_value = _fake_success()
    _override_orchestration(fake)
    try:
        response = client.post(
            f"/api/v1/agents/{agent.id}/orchestrate",
            json={"instruction": "  hello world  "},
            headers=_headers(created["access_token"]),
        )
        assert response.status_code == 200
        assert fake.orchestrate.call_args.kwargs["user_input"] == "hello world"
    finally:
        _clear_orchestration_override()


def test_orchestrate_anonymous_401(db: Session, client: TestClient) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    fake = MagicMock()
    _override_orchestration(fake)
    try:
        response = client.post(
            f"/api/v1/agents/{agent.id}/orchestrate",
            json={"instruction": "hello"},
        )
        assert response.status_code == 401
        fake.orchestrate.assert_not_called()
    finally:
        _clear_orchestration_override()


def test_orchestrate_outsider_token_cannot_use_other_org_agent(
    db: Session, client: TestClient
) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    agent = _create_agent(db, first["organization"]["id"])
    fake = MagicMock()
    _override_orchestration(fake)
    try:
        response = client.post(
            f"/api/v1/agents/{agent.id}/orchestrate",
            json={"instruction": "hello"},
            headers=_headers(second["access_token"]),
        )
        assert response.status_code == 404
        fake.orchestrate.assert_not_called()
    finally:
        _clear_orchestration_override()


def test_orchestrate_unknown_agent_404(db: Session, client: TestClient) -> None:
    created = _auth(client)
    fake = MagicMock()
    _override_orchestration(fake)
    try:
        response = client.post(
            "/api/v1/agents/missing-agent-id/orchestrate",
            json={"instruction": "hello"},
            headers=_headers(created["access_token"]),
        )
        assert response.status_code == 404
        fake.orchestrate.assert_not_called()
    finally:
        _clear_orchestration_override()


def test_orchestrate_member_allowed(db: Session, client: TestClient) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    token = _add_org_member(
        db, org_id, email="member@example.com", role=MembershipRole.MEMBER
    )
    fake = MagicMock()
    fake.orchestrate.return_value = _fake_success()
    _override_orchestration(fake)
    try:
        response = client.post(
            f"/api/v1/agents/{agent.id}/orchestrate",
            json={"instruction": "search leads"},
            headers=_headers(token),
        )
        assert response.status_code == 200
        assert fake.orchestrate.called
        assert fake.orchestrate.call_args.kwargs["organization_id"] == org_id
        assert fake.orchestrate.call_args.kwargs["agent_id"] == agent.id
    finally:
        _clear_orchestration_override()


def test_orchestrate_empty_instruction_422(db: Session, client: TestClient) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    fake = MagicMock()
    _override_orchestration(fake)
    try:
        for payload in ({"instruction": ""}, {"instruction": "   "}):
            response = client.post(
                f"/api/v1/agents/{agent.id}/orchestrate",
                json=payload,
                headers=_headers(created["access_token"]),
            )
            assert response.status_code == 422
        fake.orchestrate.assert_not_called()
    finally:
        _clear_orchestration_override()


def test_orchestrate_oversized_instruction_422(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    fake = MagicMock()
    _override_orchestration(fake)
    try:
        response = client.post(
            f"/api/v1/agents/{agent.id}/orchestrate",
            json={"instruction": "x" * 8001},
            headers=_headers(created["access_token"]),
        )
        assert response.status_code == 422
        fake.orchestrate.assert_not_called()
    finally:
        _clear_orchestration_override()


def test_orchestrate_rejects_extra_authorization_fields(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    fake = MagicMock()
    _override_orchestration(fake)
    try:
        for extra in (
            {"organization_id": "attacker"},
            {"user_id": "u"},
            {"role": "OWNER"},
            {"permissions": ["*"]},
            {"execution_id": "exec"},
            {"agent_id": "other"},
            {"plan": {}},
            {"tools": ["echo"]},
        ):
            body = {"instruction": "hello", **extra}
            response = client.post(
                f"/api/v1/agents/{agent.id}/orchestrate",
                json=body,
                headers=_headers(created["access_token"]),
            )
            assert response.status_code == 422, extra
        fake.orchestrate.assert_not_called()
    finally:
        _clear_orchestration_override()


def test_orchestrate_approval_required_returns_200(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    fake = MagicMock()
    fake.orchestrate.return_value = _fake_success(
        outcome=OrchestrationOutcome.APPROVAL_REQUIRED,
        execution_status=AgentExecutionStatus.FAILED,
        approval_required=True,
        failure_category=ExecutionFailureCategory.POLICY_ERROR,
        error="Tool 'draft_note' requires human approval",
        stopped_at_step_id="s1",
        completed_step_count=0,
    )
    _override_orchestration(fake)
    try:
        response = client.post(
            f"/api/v1/agents/{agent.id}/orchestrate",
            json={"instruction": "draft a note"},
            headers=_headers(created["access_token"]),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "APPROVAL_REQUIRED"
        assert body["approval_required"] is True
        assert body["stopped_at_step_id"] == "s1"
    finally:
        _clear_orchestration_override()


def test_orchestrate_planner_failure_sanitized(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    fake = MagicMock()
    fake.orchestrate.return_value = OrchestrationResult(
        execution_id="exec-fail",
        outcome=OrchestrationOutcome.PLANNING_FAILED,
        execution_status=AgentExecutionStatus.FAILED,
        failure_category=ExecutionFailureCategory.PROVIDER_ERROR,
        error="AI provider request failed",
        provider="fake",
        model="fake-model",
    )
    _override_orchestration(fake)
    try:
        response = client.post(
            f"/api/v1/agents/{agent.id}/orchestrate",
            json={"instruction": "plan something"},
            headers=_headers(created["access_token"]),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "PLANNING_FAILED"
        assert body["error"] == "AI provider request failed"
        assert "sk-" not in (body.get("error") or "")
        assert "traceback" not in str(body).lower()
    finally:
        _clear_orchestration_override()


def test_orchestrate_does_not_call_lower_layers_directly(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"])
    fake = MagicMock()
    fake.orchestrate.return_value = _fake_success()
    _override_orchestration(fake)
    try:
        from unittest.mock import patch

        with (
            patch("app.services.agent_planner_service.AgentPlanner.plan") as plan,
            patch(
                "app.services.plan_execution_service.PlanExecutionService.execute"
            ) as execute_plan,
            patch(
                "app.services.tool_execution_service.ToolExecutionService.execute"
            ) as execute_tool,
        ):
            response = client.post(
                f"/api/v1/agents/{agent.id}/orchestrate",
                json={"instruction": "hello"},
                headers=_headers(created["access_token"]),
            )
            assert response.status_code == 200
            fake.orchestrate.assert_called_once()
            plan.assert_not_called()
            execute_plan.assert_not_called()
            execute_tool.assert_not_called()
    finally:
        _clear_orchestration_override()
