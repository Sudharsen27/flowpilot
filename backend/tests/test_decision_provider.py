import pytest
from pydantic import ValidationError

from app.ai.decision_provider import DecisionProvider, DecisionRequest, DecisionResult


@pytest.mark.parametrize(
    "value",
    ["high", True, 3, 0.75],
)
def test_decision_result_accepts_bounded_scalar_values(value: object) -> None:
    result = DecisionResult(value=value)

    assert result.value == value


def test_decision_result_rejects_unstructured_values() -> None:
    with pytest.raises(ValidationError):
        DecisionResult(value={"priority": "high"})


def test_decision_request_keeps_context_and_untrusted_state_separate() -> None:
    request = DecisionRequest(
        decision_key="lead_escalation",
        trusted_context="Escalate urgent support enquiries.",
        untrusted_state="Customer enquiry text",
    )

    assert request.trusted_context != request.untrusted_state
    assert set(DecisionRequest.model_fields) == {
        "decision_key",
        "trusted_context",
        "untrusted_state",
    }


def test_decision_request_rejects_unexpected_authorization_fields() -> None:
    with pytest.raises(ValidationError):
        DecisionRequest(
            decision_key="lead_escalation",
            trusted_context="Escalate urgent support enquiries.",
            untrusted_state="Customer enquiry text",
            organization_id="org-1",
        )


def test_decision_provider_protocol_is_runtime_checkable() -> None:
    class FakeDecisionProvider:
        def decide(self, request: DecisionRequest) -> DecisionResult:
            return DecisionResult(value=True)

    assert isinstance(FakeDecisionProvider(), DecisionProvider)