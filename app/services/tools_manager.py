from typing import Dict, Any, Callable
from app.core.logging import logging

logger = logging.getLogger(__name__)

class ToolsManager:
    """
    Manages the registration and execution of tools (functions) 
    available to the Agent.
    """
    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register_tool(self, name: str, func: Callable):
        """Registers a new tool"""
        logger.info(f"Registering tool: {name}")
        self._tools[name] = func

    def get_tool_definitions(self):
        """Returns the definitions (schemas) of registered tools for the LLM"""
        # To be implemented: generate JSON schema from function signatures
        return []

    async def execute_tool(self, name: str, args: Dict[str, Any]):
        """Executes a tool by name"""
        if name not in self._tools:
            logger.error(f"Tool not found: {name}")
            return None
        logger.info(f"Executing tool: {name} with args: {args}")
        try:
            # Handle async vs sync tools if needed
            return await self._tools[name](**args)
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            raise e
