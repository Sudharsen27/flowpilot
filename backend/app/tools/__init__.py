from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.tools.echo import EchoTool
from app.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from app.ai.provider import AIProvider


def build_default_tool_registry(
    session: Session | None = None,
    provider: AIProvider | None = None,
) -> ToolRegistry:
    """Register the allowlisted Phase 6D tools.

    Business tools require a DB session and delegate to existing services.
    When session is omitted (tests that only need echo), only EchoTool is registered.
    Business tools are imported lazily to avoid circular imports with AI providers.
    Optional provider is passed to AI-backed write tools (create_response_draft).
    """
    registry = ToolRegistry()
    registry.register(EchoTool())
    if session is not None:
        from app.tools.business import (
            CreateResponseDraftTool,
            GetCustomerContextTool,
            GetFollowUpsTool,
            GetLeadTool,
            SearchLeadsTool,
        )

        registry.register(SearchLeadsTool(session))
        registry.register(GetLeadTool(session))
        registry.register(GetCustomerContextTool(session))
        registry.register(GetFollowUpsTool(session))
        registry.register(CreateResponseDraftTool(session, provider))
    return registry
