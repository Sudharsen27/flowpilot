from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tool_invocation import ToolInvocation
from app.repositories.agent_execution_repository import (
    EXECUTION_LIST_DEFAULT_LIMIT,
    EXECUTION_LIST_MAX_LIMIT,
)

INVOCATION_LIST_DEFAULT_LIMIT = EXECUTION_LIST_DEFAULT_LIMIT
INVOCATION_LIST_MAX_LIMIT = EXECUTION_LIST_MAX_LIMIT


class ToolInvocationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, invocation: ToolInvocation) -> ToolInvocation:
        self.session.add(invocation)
        return invocation

    def list_by_execution(
        self,
        organization_id: str,
        agent_id: str,
        execution_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[ToolInvocation], int]:
        filters = (
            ToolInvocation.organization_id == organization_id,
            ToolInvocation.agent_id == agent_id,
            ToolInvocation.execution_id == execution_id,
        )
        total = self.session.scalar(
            select(func.count()).select_from(ToolInvocation).where(*filters)
        )
        items = list(
            self.session.scalars(
                select(ToolInvocation)
                .where(*filters)
                .order_by(ToolInvocation.started_at.asc(), ToolInvocation.id.asc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, int(total or 0)
