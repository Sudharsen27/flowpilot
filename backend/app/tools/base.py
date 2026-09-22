from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.tools.schema import (
    ToolContext,
    ToolDefinition,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


class Tool(ABC):
    name: str
    description: str
    risk_level: ToolRiskLevel
    side_effect_level: ToolSideEffectLevel = ToolSideEffectLevel.READ
    requires_human_approval: bool = False
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    def definition(self) -> ToolDefinition:
        requires_approval = self.requires_human_approval or self.risk_level in {
            ToolRiskLevel.MEDIUM,
            ToolRiskLevel.HIGH,
        }
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
            output_schema=self.output_model.model_json_schema(),
            risk_level=self.risk_level,
            side_effect_level=self.side_effect_level,
            requires_human_approval=requires_approval,
        )

    @abstractmethod
    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        """Run the tool with already-validated arguments and server-side tenant context."""
