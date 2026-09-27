from __future__ import annotations
from typing import Any, Dict, List, Optional

from core.sources.base_source import BaseSource


class ConfluenceSource(BaseSource):
    """
    Fetch Confluence content via Atlassian MCP server.
    """

    def __init__(self, mcp, server_name: str = "atlassian"):
        super().__init__(mcp, server_name)

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Searches pages related to the ticket.
        Tool name here is a best-guess; adapt if your MCP tool differs.
        """
        resp = await self._call("confluence_search", {"query": query, "limit": limit})
        data = getattr(resp, "content", resp)

        # Normalize common shapes
        if isinstance(data, dict):
            if "results" in data and isinstance(data["results"], list):
                return data["results"]
            if "items" in data and isinstance(data["items"], list):
                return data["items"]
        return []

    async def get_page(self, page_id: str, expand: str = "body.storage") -> Dict[str, Any]:
        """
        Fetch a single Confluence page by id.
        Tool name here is a best-guess; adapt if your MCP tool differs.
        """
        resp = await self._call("confluence_get_page", {"page_id": page_id, "expand": expand})
        return getattr(resp, "content", resp)

    async def search_and_fetch_pages(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        hits = await self.search(query, limit=limit)
        pages: List[Dict[str, Any]] = []

        for h in hits[:limit]:
            page_id = str(h.get("id") or h.get("page_id") or "")
            if not page_id:
                continue
            try:
                page = await self.get_page(page_id)
                pages.append(page)
            except Exception:
                continue

        return pages
