from __future__ import annotations
from typing import Any, Dict, Optional, List

from core.sources.base_source import BaseSource


class JiraSource(BaseSource):
    """
    Fetch Jira data (issue + optional comments) via Atlassian MCP server.
    """

    def __init__(self, mcp, server_name: str = "atlassian"):
        super().__init__(mcp, server_name)

    async def get_issue(self, issue_key: str) -> Dict[str, Any]:
        resp = await self._call("jira_get_issue", {"issue_key": issue_key})
        return getattr(resp, "content", resp)

    async def get_issue_comments(self, issue_key: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        If your MCP toolset supports a dedicated comments tool, use it.
        Otherwise, comments might already be embedded in get_issue fields.
        Tool name here is a best-guess; adapt if your MCP tool differs.
        """
        try:
            resp = await self._call("jira_get_issue_comments", {"issue_key": issue_key, "limit": limit})
            data = getattr(resp, "content", resp)
            return data.get("comments", []) if isinstance(data, dict) else []
        except Exception:
            # fallback: return empty if tool isn't available
            return []
