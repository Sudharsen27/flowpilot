from typing import Protocol

from app.tools.schema import PolicyDecision, ToolRiskLevel


class ToolPolicy(Protocol):
    def decide(self, tool_name: str, risk_level: ToolRiskLevel) -> PolicyDecision:
        """Return ALLOW, REQUIRE_APPROVAL, or DENY. Never bypassed by the model."""
        ...


class DefaultToolPolicy:
    """LOW tools may run. MEDIUM and HIGH require human approval (approvals backend deferred)."""

    def decide(self, tool_name: str, risk_level: ToolRiskLevel) -> PolicyDecision:
        if risk_level == ToolRiskLevel.LOW:
            return PolicyDecision.ALLOW
        return PolicyDecision.REQUIRE_APPROVAL


class StaticToolPolicy:
    def __init__(self, decisions: dict[str, PolicyDecision]) -> None:
        self._decisions = decisions

    def decide(self, tool_name: str, risk_level: ToolRiskLevel) -> PolicyDecision:
        if tool_name in self._decisions:
            return self._decisions[tool_name]
        return DefaultToolPolicy().decide(tool_name, risk_level)
