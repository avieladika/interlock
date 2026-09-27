import json
import os
from typing import Any, Dict, Optional

from groq import Groq

from core.models.phase2models.RequirementsArtifact import RequirementsArtifact
from core.models.phase3models.PlanArtifact import PlanArtifact
from core.utils import make_json_safe


class PlanSynthesizer:
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        api_key = os.getenv("GROQ_API")
        if not api_key:
            raise RuntimeError("⚠️ [PlanSynthesizer] GROQ_API not found in environment")

        self.client = Groq(api_key=api_key)
        self.model = model

    async def generate(self, requirements: RequirementsArtifact, code_context: Optional[str] = None) -> PlanArtifact:
        prompt = self._build_prompt(requirements, code_context)
        raw_json = self._call_groq(prompt)

        data = self._safe_json_loads(raw_json)
        return PlanArtifact.model_validate(data)

    def _build_prompt(self, requirements: RequirementsArtifact, code_context: Optional[str]) -> str:
        req_context = make_json_safe(requirements.model_dump())

        context_section = ""
        if code_context:
            context_section = f"""
EXISTING CODEBASE CONTEXT (from RAG):
{code_context}
"""

        return f"""
You are the Technical Planner for the Interlock System (Phase 3).

GOAL:
Create a detailed, step-by-step technical plan to implement the requirements provided below.
Each step MUST be actionable and linked to a specific Requirement ID (R-x) or Acceptance Criteria ID (AC-x) where possible.

INPUT REQUIREMENTS:
{json.dumps(req_context, ensure_ascii=False)}
{context_section}

HARD CONSTRAINTS:
1. Output MUST be valid JSON matching the PlanArtifact schema.
2. "steps" list is MANDATORY and must be ordered logically.
3. Each step must have a "type": "code", "investigation", "configuration", or "testing".
4. If a step implements a requirement, set "linked_requirement_id" to the ID (e.g., "R-1").
5. If a step is general setup, "linked_requirement_id" can be null.
6. "file_paths" should list files you expect to create or modify.
7. Use the EXISTING CODEBASE CONTEXT to identify correct file paths and existing utilities. Do not reinvent the wheel.

OUTPUT JSON STRUCTURE:
{{
  "ticket_id": "{requirements.ticket_id}",
  "goal": "Implement feature X based on requirements...",
  "steps": [
    {{
      "step_id": "S-1",
      "title": "Create data model",
      "description": "Define the Pydantic model for...",
      "type": "code",
      "linked_requirement_id": "R-1",
      "file_paths": ["core/models/new_model.py"]
    }},
    {{
      "step_id": "S-2",
      "title": "Verify API access",
      "description": "Check if the external API key is valid...",
      "type": "investigation",
      "linked_requirement_id": null,
      "file_paths": []
    }}
  ],
  "risks": [
    "Risk 1: API rate limits might be an issue."
  ]
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
                temperature=0.2,
            )
            return response.choices[0].message.content or "{}"
        except Exception as e:
            raise RuntimeError(f"❌ [PlanSynthesizer] Groq call failed: {e}") from e

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
            raise ValueError(
                f"❌ [PlanSynthesizer] Invalid JSON returned by LLM: {e}\nRAW:\n{raw}"
            ) from e
