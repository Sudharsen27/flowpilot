from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.tools.schema import ToolContext, ToolDefinition, ToolRiskLevel


class Tool(ABC):
    name: str
    description: str
    risk_level: ToolRiskLevel
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
            output_schema=self.output_model.model_json_schema(),
            risk_level=self.risk_level,
        )

    @abstractmethod
    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        """Run the tool with already-validated arguments and server-side tenant context."""
