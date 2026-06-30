from app.tools.tool_registry import registry
from app.tools.file_tool import file_create, file_read
from app.tools.exec_tool import exec_code

# Register all tools on import
registry.register("file_create", file_create)
registry.register("file_read", file_read)
registry.register("exec_code", exec_code)

__all__ = ["registry"]
