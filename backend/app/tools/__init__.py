from app.tools.echo import EchoTool
from app.tools.registry import ToolRegistry


def build_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(EchoTool())
    return registry
