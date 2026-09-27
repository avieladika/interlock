import json
import os
from typing import Any, Dict

from groq import Groq

from core.models.phase2models.confluenceSheiltaArtifact import ConfluenceSheiltaArtifact


class ConfluencePlanSynthesizer:
    """
    Phase 2B Synthesizer:
    Jira text -> ConfluenceSheiltaArtifact (CQL plan) as JSON.
    """

    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        api_key = os.getenv("GROQ_API")
        if not api_key:
            raise RuntimeError("⚠️ [ConfluencePlanSynthesizer] GROQ_API not found in environment")

        self.client = Groq(api_key=api_key)
        self.model = model

    async def build_confluence_cql_plan(self, issue_key: str, ticket_text: str) -> str:
        """
        Returns a JSON string that matches ConfluenceSheiltaArtifact schema.
        """
        # IMPORTANT: We will prompt for a JSON object, and then validate it using the model
        prompt = self._build_prompt(issue_key=issue_key, ticket_text=ticket_text)

        raw_json = self._call_groq(prompt)
        # validate structure now (fail fast) - also guarantees it matches your artifact
        plan = ConfluenceSheiltaArtifact.model_validate_json(raw_json)
        # return normalized json string (stable)
        return plan.model_dump_json()

    def _build_prompt(self, issue_key: str, ticket_text: str) -> str:
        return f"""
    You are a Confluence CQL Plan Generator.

    You MUST output ONLY a valid JSON object (no markdown, no explanations).

    The JSON MUST match this schema and rules:

    FIELDS (ALL REQUIRED):
    - issue_key: string like "ABC-123" (MUST equal "{issue_key}")
    - cql: string (10..600 chars)
        - MUST include "type=page"
        - MUST include the literal issue key "{issue_key}" somewhere in the query
        - MUST NOT include banned constructs: created by, ORDER BY rand(), macro, permission
    - terms: array of strings (MUST contain at least 1 item, up to 10)
        - each term length 2..60
        - terms must be unique
    - spaces: array of strings (0..5). Use empty [] if you are not sure.
    - page_limit: integer 1..20 (prefer <= 15)
    - expand: one of ["body.storage", "body.view", "none"]
    - confidence: number 0..1
    - warnings: array of strings (0..10), short items only

    INSTRUCTIONS:
    - Extract 3-8 meaningful terms from the ticket text (short, verifiable).
    - Build a CQL query using:
      - type=page
      - text ~ "{issue_key}"
      - optionally add text ~ "TERM" for 1-3 of the extracted terms
      - optionally add space in ("ENG","ARCH","INT") ONLY if clearly relevant; otherwise use [].

    JIRA_TICKET_TEXT:
    {ticket_text}

    OUTPUT EXAMPLE (FOLLOW THIS SHAPE EXACTLY):
    {{
      "issue_key": "{issue_key}",
      "cql": "type=page AND text ~ \\"{issue_key}\\"",
      "terms": ["{issue_key}", "design", "requirements"],
      "spaces": [],
      "page_limit": 10,
      "expand": "body.storage",
      "confidence": 0.65,
      "warnings": []
    }}
    """.strip()

    def _call_groq(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You output ONLY JSON that matches the requested schema."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            return response.choices[0].message.content or "{}"
        except Exception as e:
            raise RuntimeError(f"❌ [ConfluencePlanSynthesizer] Groq call failed: {e}") from e
