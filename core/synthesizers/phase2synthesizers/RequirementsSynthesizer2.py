import json
import os
from typing import Any, Dict

from groq import Groq

from core.models.phase2models import EvidenceBundle, RequirementsArtifact
from core.utils import make_json_safe
from core.gates.phase2gates.gatePhase2 import RequirementsIntegrityGate


class RequirementsSynthesizer:
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        api_key = os.getenv("GROQ_API")
        if not api_key:
            raise RuntimeError("⚠️ [RequirementsSynthesizer] GROQ_API not found in environment")

        self.client = Groq(api_key=api_key)
        self.model = model

    async def generate(self, bundle: EvidenceBundle, ticket_id: str, summary: str) -> RequirementsArtifact:
        # Build the prompt with strict instructions
        prompt = self._build_prompt(bundle, ticket_id=ticket_id, summary=summary)
        
        # Call LLM
        raw_json = self._call_groq(prompt)

        # ✅ Gate validates the RAW LLM OUTPUT STRING (optional, depending on gate implementation)
        # Note: If the gate expects specific keys, ensure it matches the new schema.
        is_valid, msg = RequirementsIntegrityGate.validate(raw_json)
        if not is_valid:
            raise RuntimeError(f"❌ [RequirementsSynthesizer] Gate failed: {msg}")

        # Parse and validate against Pydantic model
        data = self._safe_json_loads(raw_json)
        return RequirementsArtifact.model_validate(data)

    def _build_prompt(self, bundle: EvidenceBundle, ticket_id: str, summary: str) -> str:
        context = make_json_safe(bundle.to_llm_context())

        return f"""
You are the Requirements Synthesizer for the Interlock System (Phase 2).

GOAL:
Analyze the provided INPUT EVIDENCE and generate a structured Requirements Artifact.
You MUST extract requirements and acceptance criteria based ONLY on the evidence.

HARD CONSTRAINTS (MUST FOLLOW):
1. Output MUST be valid JSON (no markdown, no prose).
2. The JSON MUST match the target schema EXACTLY.
3. "requirements" list is MANDATORY and MUST NOT be empty.
4. Each "requirement" object MUST have a "sources" list with at least one valid source reference from the input evidence.
5. "acceptance_criteria" list is optional but recommended.
6. "unknowns" should list missing critical information.

INPUT EVIDENCE:
{json.dumps(context, ensure_ascii=False)}

TICKET INFO:
ID: {ticket_id}
Summary: {summary}

OUTPUT JSON STRUCTURE (Fill this template):
{{
  "ticket_id": "{ticket_id}",
  "summary": "{summary}",
  "requirements": [
    {{
      "id": "R-1",
      "type": "functional",  // or "non_functional", "constraint"
      "statement": "The system shall...",
      "sources": [
        {{
          "type": "jira", // or "confluence", "github"
          "ref": "URL or ID",
          "excerpt": "Quote from text proving this requirement"
        }}
      ]
    }}
  ],
  "acceptance_criteria": [
    {{
      "id": "AC-1",
      "description": "Verify that...",
      "is_automated": false,
      "sources": []
    }}
  ],
  "unknowns": []
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
            raise RuntimeError(f"❌ [RequirementsSynthesizer] Groq call failed: {e}") from e

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
                f"❌ [RequirementsSynthesizer] Invalid JSON returned by LLM: {e}\nRAW:\n{raw}"
            ) from e
