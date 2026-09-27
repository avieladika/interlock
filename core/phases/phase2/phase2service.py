import json
import re
import os
from typing import Any, Dict, Optional, Protocol
import asyncio

from core.gates.phase2gates.gatePhase2 import RequirementsIntegrityGate
from core.models.phase2models.RequirementsArtifact import RequirementsArtifact
from core.models.phase1_5models.ContextArtifact import ContextArtifact
from core.phases.phase2.EvidenceBuilder import EvidenceBuilder
from core.phases.phase2.confluenceCollector import ConfluenceCollector
from core.utils import make_json_safe
from core.utils.knowledge_base import KnowledgeBase


class RequirementsSynthesizerProto(Protocol):
    async def generate(self, bundle: Any, ticket_id: str, summary: str) -> RequirementsArtifact: ...


class ConfluencePlannerProto(Protocol):
    async def build_confluence_cql_plan(self, issue_key: str, ticket_text: str) -> str: ...

class UserInputProvider(Protocol):
    async def ask(self, field: str, question: str) -> str: ...


class ConsoleInputProvider:
    """
    Default CLI implementation.
    Uses a thread so it doesn't block the async loop.
    """
    async def ask(self, field: str, question: str) -> str:
        # We print to stdout so the user sees it in the terminal logs
        print(f"\n👉 QUESTION [{field}]: {question}")
        prompt = "> "
        return await asyncio.to_thread(input, prompt)


class Phase2Service:
    def __init__(
        self,
        mcp,
        requirements_synthesizer: RequirementsSynthesizerProto,
        confluence_planner: ConfluencePlannerProto,
        allowed_confluence_spaces: set[str],
        default_confluence_expand: str = "body.storage",
        input_provider=None,
        knowledge_base: Optional[KnowledgeBase] = None,
        confluence_output_dir: Optional[str] = None,  # ✅ New
    ):
        self.mcp = mcp
        self.requirements_synthesizer = requirements_synthesizer
        self.evidence_builder = EvidenceBuilder()
        self.kb = knowledge_base
        self.confluence_output_dir = confluence_output_dir

        self.confluence_collector = ConfluenceCollector(
            mcp=mcp,
            planner=confluence_planner,
            allowed_spaces=allowed_confluence_spaces,
            default_expand=default_confluence_expand,
        )

        # Default: CLI
        self.input_provider = input_provider or ConsoleInputProvider()

    async def run(
        self, 
        ticket_key: str, 
        user_inputs: Optional[Dict[str, str]] = None,
        context_artifact: Optional[ContextArtifact] = None
    ) -> RequirementsArtifact:
        
        # 1) Fetch Jira issue
        jira_issue = await self._fetch_jira_issue(ticket_key)

        # 2) Compact Jira text
        jira_text = self.evidence_builder._stringify_jira_issue(jira_issue)

        # 3) Confluence space: 
        confluence_space = None
        if context_artifact and context_artifact.confluence_space_key:
            confluence_space = context_artifact.confluence_space_key
            print(f"   ℹ Using discovered Confluence Space: {confluence_space}")
        elif user_inputs and "confluence_space" in user_inputs:
            confluence_space = user_inputs["confluence_space"]
        
        if not confluence_space:
            confluence_space = await self._require_confluence_space()

        # 4) Collect Confluence pages
        confluence_pages = await self.confluence_collector.collect(
            issue_key=ticket_key,
            jira_text=jira_text,
            space_key=confluence_space,
        )

        # ✅ Save & Index Confluence pages
        if confluence_pages:
            print(f"   📚 Processing {len(confluence_pages)} Confluence pages...")
            texts = []
            metadatas = []
            
            for page in confluence_pages:
                # Extract text
                body = page.get("body", {}).get("storage", {}).get("value", "")
                title = page.get("title", "Untitled")
                page_id = page.get("id", "unknown")
                
                # Save to file (if dir configured)
                if self.confluence_output_dir:
                    safe_title = "".join([c for c in title if c.isalnum() or c in " -_"]).strip()
                    filename = f"{page_id}_{safe_title}.txt"
                    filepath = os.path.join(self.confluence_output_dir, filename)
                    try:
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(f"Title: {title}\nURL: .../pages/{page_id}\n\n{body}")
                    except Exception as e:
                        print(f"   ⚠️ Failed to save page {page_id}: {e}")

                # Prepare for RAG
                texts.append(f"Title: {title}\n\n{body}")
                metadatas.append({"source": "confluence", "title": title, "page_id": page_id})
            
            # Index into RAG
            if self.kb:
                try:
                    self.kb.add_documents(texts, metadatas)
                    print("   ✅ Confluence pages indexed into RAG.")
                except Exception as e:
                    print(f"   ⚠️ Failed to index Confluence pages: {e}")

        # 5) GitHub branch: 
        branch = None
        if context_artifact and context_artifact.target_branch:
            branch = context_artifact.target_branch
            print(f"   ℹ Using discovered GitHub Branch: {branch}")
        
        if not branch:
            branch = self._extract_branch_from_jira(jira_issue, jira_text)
            
        if not branch and user_inputs and "github_branch" in user_inputs:
            branch = user_inputs["github_branch"]

        if not branch:
            branch = await self._ask_user(
                field="github_branch",
                question="Which GitHub branch should I use for this ticket? (e.g., 'main', 'develop', 'feature/CKM-1')",
            )

        # 6) Build EvidenceBundle
        bundle = self.evidence_builder.build(
            issue_key=ticket_key,
            jira_issue=jira_issue,
            confluence_pages=confluence_pages,
            github_payload=None,  # later: use `branch` when GitHub collector exists
        )

        # 7) ticket_id + summary
        ticket_id = ticket_key
        summary = ""
        if isinstance(jira_issue, dict):
            fields = jira_issue.get("fields")
            if isinstance(fields, dict):
                s = fields.get("summary")
                if isinstance(s, str):
                    summary = s
            if not summary:
                s2 = jira_issue.get("summary")
                if isinstance(s2, str):
                    summary = s2

        # Debug snapshot
        debug_payload = make_json_safe(
            {
                "evidence_bundle": bundle.to_llm_context(),
                "jira_issue": jira_issue,
                "confluence_pages": confluence_pages,
                "branch": branch,
                "confluence_space": confluence_space,
            }
        )
        _ = json.dumps(debug_payload, ensure_ascii=False)

        # 8) LLM synthesis
        requirements_artifact = await self.requirements_synthesizer.generate(
            bundle=bundle,
            ticket_id=ticket_id,
            summary=summary,
        )

        # 9) Gate validation
        artifact_json = json.dumps(make_json_safe(requirements_artifact.model_dump()), ensure_ascii=False)
        is_valid, msg = RequirementsIntegrityGate.validate(artifact_json)
        if not is_valid:
            raise RuntimeError(f"Phase 2 RequirementsIntegrityGate failed: {msg}")

        return requirements_artifact

    async def _require_confluence_space(self) -> str:
        return await self._ask_user(
            field="confluence_space",
            question="Which Confluence space key should I search in? (e.g., 'ENG', 'INT', 'CKM')",
        )

    async def _ask_user(self, field: str, question: str) -> str:
        while True:
            ans = await self.input_provider.ask(field=field, question=question)
            ans = (ans or "").strip()
            if ans:
                return ans

    async def _fetch_jira_issue(self, ticket_key: str) -> Dict[str, Any]:
        resp = await self.mcp.call_tool(
            server_name="atlassian",
            tool_name="jira_get_issue",
            arguments={"issue_key": ticket_key},
        )
        return getattr(resp, "content", resp)

    def _extract_branch_from_jira(self, jira_issue: Dict[str, Any], jira_text: str) -> Optional[str]:
        text = (jira_text or "").strip()
        patterns = [
            r"(?im)^\s*branch\s*:\s*(.+?)\s*$",
            r"(?im)^\s*github\s*branch\s*:\s*(.+?)\s*$",
            r"(?im)^\s*target\s*branch\s*:\s*(.+?)\s*$",
            r"(?im)^\s*base\s*branch\s*:\s*(.+?)\s*$",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                candidate = m.group(1).strip()
                if 1 <= len(candidate) <= 200 and " " not in candidate:
                    return candidate
        return None
