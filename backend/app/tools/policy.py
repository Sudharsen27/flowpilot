from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.models.membership import MembershipRole
from app.tools.schema import PolicyDecision, ToolRiskLevel, ToolSideEffectLevel

# Roles that may use READ tools (matches existing lead/inbox API membership access).
_READ_ROLES = frozenset(
    {MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.MEMBER}
)
_WRITE_ROLES = frozenset(
    {MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.MEMBER}
)


class ToolPolicyRequest(BaseModel):
    """Deterministic inputs for tool authorization. Never sourced from LLM args."""

    model_config = ConfigDict(frozen=True)

    tool_name: str
    risk_level: ToolRiskLevel
    side_effect_level: ToolSideEffectLevel
    requires_human_approval: bool
    organization_id: str | None
    user_id: str | None
    role: str | None


class ToolPolicy(Protocol):
    def decide(self, request: ToolPolicyRequest) -> PolicyDecision:
        """Return ALLOW, REQUIRE_APPROVAL, or DENY. Never bypassed by the model."""
        ...


def _parse_role(role: str | None) -> MembershipRole | None:
    if role is None or not role.strip():
        return None
    try:
        return MembershipRole(role)
    except ValueError:
        return None


class DefaultToolPolicy:
    """Fail-closed authorization using role + risk + side-effect metadata.

    READ tools: any valid org membership role (OWNER/ADMIN/MEMBER), matching
    existing lead/inbox/follow-up read APIs.

    WRITE: reserved for future tools — allowed for membership roles when risk is LOW.
    SENSITIVE_WRITE / APPROVAL_REQUIRED / MEDIUM+HIGH risk: REQUIRE_APPROVAL (no execute).
    """

    def decide(self, request: ToolPolicyRequest) -> PolicyDecision:
        if (
            not request.organization_id
            or not request.user_id
            or not request.role
        ):
            return PolicyDecision.DENY

        parsed_role = _parse_role(request.role)
        if parsed_role is None:
            return PolicyDecision.DENY

        if request.requires_human_approval:
            return PolicyDecision.REQUIRE_APPROVAL

        if request.risk_level in {ToolRiskLevel.MEDIUM, ToolRiskLevel.HIGH}:
            return PolicyDecision.REQUIRE_APPROVAL

        side = request.side_effect_level
        if side in {
            ToolSideEffectLevel.APPROVAL_REQUIRED,
            ToolSideEffectLevel.SENSITIVE_WRITE,
        }:
            return PolicyDecision.REQUIRE_APPROVAL

        if side == ToolSideEffectLevel.WRITE:
            if parsed_role not in _WRITE_ROLES:
                return PolicyDecision.DENY
            return PolicyDecision.ALLOW

        # READ (and any unexpected future enum treated as deny)
        if side != ToolSideEffectLevel.READ:
            return PolicyDecision.DENY
        if parsed_role not in _READ_ROLES:
            return PolicyDecision.DENY
        return PolicyDecision.ALLOW


class StaticToolPolicy:
    """Test helper: override decisions for named tools after fail-closed auth checks."""

    def __init__(
        self,
        decisions: dict[str, PolicyDecision],
        *,
        fallback: ToolPolicy | None = None,
    ) -> None:
        self._decisions = decisions
        self._fallback = fallback or DefaultToolPolicy()

    def decide(self, request: ToolPolicyRequest) -> PolicyDecision:
        if (
            not request.organization_id
            or not request.user_id
            or not request.role
        ):
            return PolicyDecision.DENY
        if _parse_role(request.role) is None:
            return PolicyDecision.DENY
        if request.tool_name in self._decisions:
            return self._decisions[request.tool_name]
        return self._fallback.decide(request)
