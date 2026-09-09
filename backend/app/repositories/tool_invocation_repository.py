from sqlalchemy.orm import Session

from app.models.tool_invocation import ToolInvocation


class ToolInvocationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, invocation: ToolInvocation) -> ToolInvocation:
        self.session.add(invocation)
        return invocation
