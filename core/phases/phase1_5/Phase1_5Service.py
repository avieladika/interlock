import json
from typing import Any, Dict, List, Protocol

from core.models.phase1_5models.ContextArtifact import ContextArtifact


class ContextSynthesizerProto(Protocol):
    async def analyze(
        self, 
        ticket_id: str, 
        ticket_data: Dict[str, Any], 
        available_branches: List[str],
        confluence_search_results: List[Dict[str, Any]]
    ) -> ContextArtifact: ...


class Phase1_5Service:
    def __init__(
        self,
        mcp,
        context_synthesizer: ContextSynthesizerProto,
    ):
        self.mcp = mcp
        self.synthesizer = context_synthesizer

    async def run(self, ticket_key: str) -> ContextArtifact:
        print(f"🕵️ Phase 1.5: Discovering context for {ticket_key}...")

        # 1. Fetch Jira Ticket
        jira_issue = await self._fetch_jira_issue(ticket_key)
        
        # 2. List Git Branches (Discovery)
        branches = await self._list_git_branches()
        
        # 3. Search Confluence Globally (Discovery)
        # We search for the ticket summary to see where similar docs live
        summary = jira_issue.get("fields", {}).get("summary", ticket_key)
        confluence_hits = await self._search_confluence_global(summary)

        # 4. Synthesize Decision
        artifact = await self.synthesizer.analyze(
            ticket_id=ticket_key,
            ticket_data=jira_issue,
            available_branches=branches,
            confluence_search_results=confluence_hits
        )

        self._print_summary(artifact)
        return artifact

    async def _fetch_jira_issue(self, ticket_key: str) -> Dict[str, Any]:
        resp = await self.mcp.call_tool(
            server_name="atlassian",
            tool_name="jira_get_issue",
            arguments={"issue_key": ticket_key},
        )
        return getattr(resp, "content", resp)

    async def _list_git_branches(self) -> List[str]:
        # Currently we don't have a git MCP connected in this env, 
        # so we'll mock it or try to use a shell command if available.
        # For now, let's return a standard list + maybe try to fetch if possible.
        # If you have a 'git' MCP, use it here.
        return ["main", "develop", "release/v1.0"] 

    async def _search_confluence_global(self, query: str) -> List[Dict[str, Any]]:
        # Search without space filter to find where relevant docs are
        cql = f'text ~ "{query}"'
        resp = await self.mcp.call_tool(
            server_name="atlassian",
            tool_name="confluence_search",
            arguments={"query": cql, "limit": 5},
        )
        
        data = getattr(resp, "content", resp)
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return parsed.get("results", [])
            except:
                pass
        if isinstance(data, dict):
            return data.get("results", [])
        return []

    def _print_summary(self, artifact: ContextArtifact):
        print(f"✅ Context Discovered:")
        print(f"   - Target Branch: {artifact.target_branch}")
        print(f"   - Confluence Space: {artifact.confluence_space_key}")
        print(f"   - Reasoning: {artifact.reasoning}")
