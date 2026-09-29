from app.ai.decision_provider import DecisionProvider, DecisionRequest
from app.core.exceptions import ProviderError

_ESCALATE_DECISION_KEY = "escalate_to_human"


class HumanEscalationDecisionService:
    def __init__(self, provider: DecisionProvider) -> None:
        self._provider = provider

    def decide_escalation(
        self,
        *,
        trusted_context: str,
        untrusted_state: str,
    ) -> bool:
        request = DecisionRequest(
            decision_key=_ESCALATE_DECISION_KEY,
            trusted_context=trusted_context,
            untrusted_state=untrusted_state,
        )
        result = self._provider.decide(request)
        if not isinstance(result.value, bool):
            raise ProviderError("Decision provider returned a non-boolean escalation result")
        return result.value