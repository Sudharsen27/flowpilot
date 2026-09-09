from app.core.exceptions import ConflictError, NotFoundError
from app.tools.base import Tool
from app.tools.schema import ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ConflictError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def lookup(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise NotFoundError(f"Unknown tool '{name}'")
        return tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_available(self) -> list[ToolDefinition]:
        return [tool.definition() for tool in self._tools.values()]
