import json
import os
from typing import Any, Dict, List

from groq import Groq

from core.models.phase1_5models.ContextArtifact import ContextArtifact
from core.gates.phase1_5gates.gatePhase1_5 import ContextIntegrityGate  # ✅ Import Gate
from core.utils import make_json_safe


class ContextSynthesizer:
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        api_key = os.getenv("GROQ_API")
        if not api_key:
            raise RuntimeError("⚠️ [ContextSynthesizer] GROQ_API not found in environment")

        self.client = Groq(api_key=api_key)
        self.model = model

    async def analyze(
        self, 
        ticket_id: str, 
        ticket_data: Dict[str, Any], 
        available_branches: List[str],
        confluence_search_results: List[Dict[str, Any]]
    ) -> ContextArtifact:
        
        prompt = self._build_prompt(ticket_id, ticket_data, available_branches, confluence_search_results)
        raw_json = self._call_groq(prompt)
        
        # ✅ Gate Validation
        is_valid, msg = ContextIntegrityGate.validate(raw_json, available_branches=available_branches)
        if not is_valid:
            raise RuntimeError(f"❌ Phase 1.5 Gate Failed: {msg}\nRaw Output: {raw_json}")

        data = self._safe_json_loads(raw_json)
        return ContextArtifact.model_validate(data)

    def _build_prompt(
        self, 
        ticket_id: str, 
        ticket_data: Dict[str, Any], 
        available_branches: List[str],
        confluence_search_results: List[Dict[str, Any]]
    ) -> str:
        
        # Extract summary/description safely
        fields = ticket_data.get("fields", {})
        summary = fields.get("summary", "")
        description = fields.get("description", "")
        
        # Simplify confluence results for the prompt
        simplified_results = []
        for res in confluence_search_results[:10]: # Limit to top 10
            space = res.get("space", {})
            simplified_results.append({
                "title": res.get("title"),
                "space_key": space.get("key"),
                "space_name": space.get("name")
            })

        return f"""
You are the Context Analyzer for the Interlock System (Phase 1.5).

GOAL:
Determine the correct GitHub Branch and Confluence Space to work on for the given Jira Ticket.

INPUT DATA:
1. Jira Ticket: {ticket_id}
   Summary: {summary}
   Description: {description}

2. Available GitHub Branches:
   {json.dumps(available_branches)}

3. Confluence Search Results (for context):
   {json.dumps(simplified_results)}

INSTRUCTIONS:
1. Analyze the ticket to understand the project and task type.
2. Choose the best 'target_branch':
   - If the ticket mentions a specific branch, use it.
   - If it's a feature, usually base on 'main' or 'develop'.
   - If it's a fix, look for a relevant release branch.
   - If unsure, default to 'main'.
   - **CRITICAL:** You MUST choose a branch from the "Available GitHub Branches" list. Do not invent new branches.
3. Choose the best 'confluence_space_key':
   - Look at the search results. Which Space Key appears most often for relevant pages?
   - If no clear winner, infer from the project name (e.g., ticket CKM-1 -> Space CKM).
   - Default to 'ENG' if completely unsure.

OUTPUT JSON STRUCTURE:
{{
  "ticket_id": "{ticket_id}",
  "ticket_summary": "{summary}",
  "target_branch": "main",
  "confluence_space_key": "ENG",
  "reasoning": "Chose 'main' because... Chose 'ENG' because..."
}}
""".strip()

    def _call_groq(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You output ONLY JSON that matches the provided schema."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1, # Low temp for deterministic decisions
            )
            return response.choices[0].message.content or "{}"
        except Exception as e:
            raise RuntimeError(f"❌ [ContextSynthesizer] Groq call failed: {e}") from e

    def _safe_json_loads(self, raw: str) -> Dict[str, Any]:
        raw = (raw or "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Root JSON must be an object/dict.")
            return data
        except Exception as e:
            raise ValueError(f"Invalid JSON: {e}") from e
