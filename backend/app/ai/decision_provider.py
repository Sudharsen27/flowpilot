from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, StrictBool, StrictFloat, StrictInt, StrictStr

type DecisionValue = StrictBool | StrictInt | StrictFloat | StrictStr


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_key: str
    trusted_context: str
    untrusted_state: str


class DecisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: DecisionValue


@runtime_checkable
class DecisionProvider(Protocol):
    def decide(self, request: DecisionRequest) -> DecisionResult:
        """Return one bounded decision without performing business actions."""
        ...