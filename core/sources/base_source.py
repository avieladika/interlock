from __future__ import annotations
from abc import ABC
from typing import Any, Dict, Optional

from core.mcp_Manager import MCPManager


class BaseSource(ABC):
    """
    Base class for sources that fetch raw data via MCPManager.
    Keeps MCP details centralized but does NOT contain business logic.
    """

    def __init__(self, mcp: MCPManager, server_name: str):
        self.mcp = mcp
        self.server_name = server_name

    async def _call(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        args = arguments or {}
        return await self.mcp.call_tool(
            server_name=self.server_name,
            tool_name=tool_name,
            arguments=args
        )
