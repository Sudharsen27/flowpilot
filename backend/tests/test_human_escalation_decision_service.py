from collections.abc import Callable

import pytest

from app.ai.decision_provider import DecisionProvider, DecisionRequest, DecisionResult
from app.ai.deterministic_decision_provider import DeterministicDecisionProvider
from app.core.exceptions import ProviderError
from app.services.human_escalation_decision_service import HumanEscalationDecisionService


class RecordingDecisionProvider:
    def __init__(self, result: DecisionResult | None = None) -> None:
        self.result = result or DecisionResult(value=True)
        self.requests: list[DecisionRequest] = []
        self.error: Exception | None = None

    def decide(self, request: DecisionRequest) -> DecisionResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.result


@pytest.mark.parametrize("value", [True, False])
def test_service_returns_deterministic_boolean_decision(value: bool) -> None:
    provider = DeterministicDecisionProvider(value=value)
    service = HumanEscalationDecisionService(provider)

    result = service.decide_escalation(
        trusted_context="Lead source: contact form; status: new.",
        untrusted_state="Please have a person call me.",
    )

    assert result is value


def test_service_uses_fixed_decision_key_and_forwards_separate_context() -> None:
    provider = RecordingDecisionProvider()
    service = HumanEscalationDecisionService(provider)
    trusted_context = "Lead source: contact form; status: new."
    untrusted_state = "Please have a person call me."

    service.decide_escalation(
        trusted_context=trusted_context,
        untrusted_state=untrusted_state,
    )

    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.decision_key == "escalate_to_human"
    assert request.trusted_context == trusted_context
    assert request.untrusted_state == untrusted_state
    assert set(DecisionRequest.model_fields) == {
        "decision_key",
        "trusted_context",
        "untrusted_state",
    }


def test_caller_cannot_supply_arbitrary_decision_key() -> None:
    service = HumanEscalationDecisionService(DeterministicDecisionProvider(value=True))
    decide_escalation: Callable[..., bool] = service.decide_escalation

    with pytest.raises(TypeError, match="decision_key"):
        decide_escalation(
            trusted_context="Trusted CRM facts.",
            untrusted_state="Customer message.",
            decision_key="arbitrary_key",
        )


def test_provider_failure_propagates() -> None:
    provider = RecordingDecisionProvider()
    failure = ProviderError("Decision provider failed")
    provider.error = failure
    service = HumanEscalationDecisionService(provider)

    with pytest.raises(ProviderError) as caught:
        service.decide_escalation(
            trusted_context="Trusted CRM facts.",
            untrusted_state="Customer message.",
        )

    assert caught.value is failure


def test_service_has_no_database_or_external_provider_dependency() -> None:
    provider = RecordingDecisionProvider()
    service = HumanEscalationDecisionService(provider)

    service.decide_escalation(
        trusted_context="Trusted CRM facts.",
        untrusted_state="Customer message.",
    )

    assert vars(service) == {"_provider": provider}
    assert len(provider.requests) == 1


def test_authentication_and_tenant_identifiers_are_not_added_to_decision_input() -> None:
    provider = RecordingDecisionProvider()
    service = HumanEscalationDecisionService(provider)

    service.decide_escalation(
        trusted_context="Lead source: contact form.",
        untrusted_state="Can someone call me?",
    )

    request = provider.requests[0]
    assert request.untrusted_state == "Can someone call me?"
    assert "tenant_id" not in DecisionRequest.model_fields
    assert "user_id" not in DecisionRequest.model_fields
    assert "organization_id" not in DecisionRequest.model_fields
    assert "auth" not in DecisionRequest.model_fields


def test_service_depends_only_on_decision_provider_protocol() -> None:
    provider = DeterministicDecisionProvider(value=False)
    service = HumanEscalationDecisionService(provider)

    assert isinstance(provider, DecisionProvider)
    assert service.decide_escalation(
        trusted_context="Lead status: new.",
        untrusted_state="I would like to speak to a person.",
    ) is False