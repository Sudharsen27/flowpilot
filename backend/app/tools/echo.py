from pydantic import BaseModel, ConfigDict, Field

from app.tools.base import Tool
from app.tools.schema import ToolContext, ToolRiskLevel


class EchoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)


class EchoOutput(BaseModel):
    message: str


class EchoTool(Tool):
    """Harmless in-process echo used to prove the tool boundary. Not a product integration."""

    name = "echo"
    description = "Return the provided message unchanged. Test and runtime-foundation use only."
    risk_level = ToolRiskLevel.LOW
    input_model = EchoInput
    output_model = EchoOutput

    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        payload = EchoInput.model_validate(arguments)
        return EchoOutput(message=payload.message)
