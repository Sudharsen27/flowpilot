from sqlalchemy.orm import Session

from app.models.agent_execution import AgentExecution


class AgentExecutionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, execution: AgentExecution) -> AgentExecution:
        self.session.add(execution)
        return execution
