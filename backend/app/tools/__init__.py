from sqlalchemy.orm import Session

from app.tools.echo import EchoTool
from app.tools.registry import ToolRegistry


def build_default_tool_registry(session: Session | None = None) -> ToolRegistry:
    """Register the allowlisted Phase 6D.2 tools.

    Business tools require a DB session and delegate to existing services.
    When session is omitted (tests that only need echo), only EchoTool is registered.
    Business tools are imported lazily to avoid circular imports with AI providers.
    """
    registry = ToolRegistry()
    registry.register(EchoTool())
    if session is not None:
        from app.tools.business import (
            GetCustomerContextTool,
            GetFollowUpsTool,
            GetLeadTool,
            SearchLeadsTool,
        )

        registry.register(SearchLeadsTool(session))
        registry.register(GetLeadTool(session))
        registry.register(GetCustomerContextTool(session))
        registry.register(GetFollowUpsTool(session))
    return registry
