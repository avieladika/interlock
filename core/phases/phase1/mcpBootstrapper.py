import os
from typing import Dict, Optional


class MCPBootstrapper:
    """
    Boots MCP servers if not already connected.
    Keeps all MCP boot details out of the synchronizer.
    """

    def __init__(self, mcp_manager):
        self.mcp = mcp_manager

    async def ensure_atlassian_connected(self) -> None:
        """
        If no active sessions, connect to Atlassian MCP server.
        """
        if getattr(self.mcp, "sessions", None):
            # already connected
            return

        # We add --quiet to uvx to suppress its output.
        # We also try to suppress FastMCP logs via env vars.
        await self.mcp.connect_to_server(
            name="atlassian",
            command="uvx",
            args=["--quiet", "--python=3.12", "mcp-atlassian"],
            env=self._build_env(),
        )

    # python
    def _build_env(self) -> Dict[str, str]:
        """
        Centralize env mapping and filter out None values.
        Returns a mapping of strings suitable for subprocess env.
        """
        env = {
            "JIRA_URL": os.getenv("ATLASSIAN_URL"),
            "JIRA_USERNAME": os.getenv("ATLASSIAN_EMAIL"),
            "JIRA_API_TOKEN": os.getenv("ATLASSIAN_API_TOKEN"),
            "CONFLUENCE_URL": os.getenv("CONFLUENCE_BASE_URL"),
            "CONFLUENCE_USERNAME": os.getenv("ATLASSIAN_EMAIL"),
            "CONFLUENCE_API_TOKEN": os.getenv("ATLASSIAN_API_TOKEN"),
            "FASTMCP_NO_BANNER": "1",
            "FASTMCP_QUIET": "1",
            "FASTMCP_LOG_LEVEL": "ERROR",
            "LOG_LEVEL": "ERROR",
            "NO_COLOR": "1",
            "PYTHONUNBUFFERED": "1",
        }
        # Filter out None and ensure all values are strings
        return {k: str(v) for k, v in env.items() if v is not None}

    async def ensure_atlassian_connected(self) -> None:
        if getattr(self.mcp, "sessions", None):
            return

        # Merge with current environment so subprocess inherits needed vars
        merged_env = dict(os.environ, **self._build_env())

        await self.mcp.connect_to_server(
            name="atlassian",
            command="uvx",
            args=["--quiet", "--python=3.12", "mcp-atlassian"],
            env=merged_env,
        )

