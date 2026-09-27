import json
from typing import Any, Dict, List, Protocol, Union, Optional

from core.gates.phase2gates.gatePhaseConfluence import (
    ConfluenceGateConfig,
    apply_confluence_gate,
)
from core.models.phase2models.confluenceSheiltaArtifact import ConfluenceSheiltaArtifact


class MissingConfluenceSpaceError(RuntimeError):
    pass


class ConfluencePlannerProto(Protocol):
    async def build_confluence_cql_plan(self, issue_key: str, ticket_text: str) -> str: ...


class ConfluenceCollector:
    def __init__(
        self,
        mcp,
        planner: ConfluencePlannerProto,
        allowed_spaces: Optional[set[str]] = None,  # ✅ None = open (no restriction)
        default_expand: str = "body.storage",
        max_page_limit: int = 15,
        max_cql_length: int = 600,
    ):
        self.mcp = mcp
        self.planner = planner

        self.allowed_spaces = allowed_spaces  # None => open
        self.default_expand = default_expand

        self.max_page_limit = max_page_limit
        self.max_cql_length = max_cql_length

    async def collect(
        self,
        issue_key: str,
        jira_text: str,
        space_key: Optional[str],   # מגיע מהמשתמש
    ) -> List[Dict[str, Any]]:
        # ✅ still require explicit space_key from user
        if space_key is None or not str(space_key).strip():
            raise MissingConfluenceSpaceError(
                "Missing required input: confluence_space (space_key)."
            )

        space_key = str(space_key).strip()

        # ✅ OPEN MODE: no allowlist enforcement here
        # (If allowed_spaces is provided intentionally in the future, you can re-enable enforcement.)

        # 1) Ask planner to generate a CQL plan (JSON string)
        raw_plan_json = await self.planner.build_confluence_cql_plan(
            issue_key=issue_key,
            ticket_text=jira_text,
        )

        # 2) Validate plan against schema
        plan = ConfluenceSheiltaArtifact.model_validate_json(raw_plan_json)

        # 2.5) Force space from user (ignore planner spaces)
        plan.spaces = [space_key]

        # 3) Apply safety + determinism gate
        # ✅ OPEN MODE: pass allowed_spaces=None so gate won't block spaces
        cfg = ConfluenceGateConfig(
            allowed_spaces=None,
            max_page_limit=self.max_page_limit,
            max_cql_length=self.max_cql_length,
            require_type_page=True,
            require_issue_key_in_cql=True,
        )
        plan = apply_confluence_gate(plan, cfg)

        # 4) Search Confluence using MCP tool (query can be CQL)
        hits = await self._search(plan=plan)

        # 5) Fetch full pages
        expand = self._resolve_expand(plan.expand)
        pages: List[Dict[str, Any]] = []

        for hit in hits[: plan.page_limit]:
            page_id = self._extract_page_id(hit)
            if not page_id:
                continue

            page = await self._get_page(page_id, expand=expand)
            pages.append(page)

        return pages

    # --- rest unchanged ---
    def _resolve_expand(self, requested_expand: str) -> str:
        if not requested_expand or requested_expand == "none":
            return self.default_expand
        return requested_expand

    def _extract_page_id(self, hit: Dict[str, Any]) -> str:
        pid = hit.get("id") or hit.get("page_id")
        return str(pid).strip() if pid else ""

    async def _search(self, plan: ConfluenceSheiltaArtifact) -> List[Dict[str, Any]]:
        spaces_filter = ",".join(plan.spaces) if getattr(plan, "spaces", None) else None

        resp = await self.mcp.call_tool(
            server_name="atlassian",
            tool_name="confluence_search",
            arguments={
                "query": plan.cql,
                "limit": plan.page_limit,
                "spaces_filter": spaces_filter,
            },
        )

        data = self._unwrap_mcp_payload(resp)

        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, list):
                    return [x for x in parsed if isinstance(x, dict)]
                if isinstance(parsed, dict):
                    results = parsed.get("results") or parsed.get("items")
                    if isinstance(results, list):
                        return [x for x in results if isinstance(x, dict)]
                    return []
            except Exception:
                return []

        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]

        if isinstance(data, dict):
            results = data.get("results") or data.get("items")
            if isinstance(results, list):
                return [x for x in results if isinstance(x, dict)]
            return []

        return []

    async def _get_page(self, page_id: str, expand: str) -> Dict[str, Any]:
        resp = await self.mcp.call_tool(
            server_name="atlassian",
            tool_name="confluence_get_page",
            arguments={"page_id": page_id, "expand": expand},
        )

        data = self._unwrap_mcp_payload(resp)

        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                return parsed if isinstance(parsed, dict) else {"raw": data}
            except Exception:
                return {"raw": data}

        return data if isinstance(data, dict) else {"raw": data}

    def _unwrap_mcp_payload(self, resp: Any) -> Union[Dict[str, Any], List[Any], str, Any]:
        content = getattr(resp, "content", resp)

        if isinstance(content, list) and content:
            first = content[0]
            if hasattr(first, "text") and isinstance(first.text, str):
                return first.text
            if isinstance(first, (dict, list, str)):
                return first
            return content

        return content
