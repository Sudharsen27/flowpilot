from app.ai.decision_provider import DecisionProvider, DecisionRequest, DecisionResult
from app.core.exceptions import ValidationError

_SUPPORTED_DECISION_KEY = "escalate_to_human"


class DeterministicDecisionProvider(DecisionProvider):
    def __init__(self, *, value: bool) -> None:
        if not isinstance(value, bool):
            raise ValueError("value must be a boolean")
        self._value = value

    def decide(self, request: DecisionRequest) -> DecisionResult:
        if request.decision_key != _SUPPORTED_DECISION_KEY:
            raise ValidationError("Unsupported decision key")
        return DecisionResult(value=self._value)