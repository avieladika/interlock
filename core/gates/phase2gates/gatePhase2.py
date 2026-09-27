import json
from typing import Tuple, List
from pydantic import ValidationError

from core.models.phase2models.RequirementsArtifact import RequirementsArtifact


class RequirementsIntegrityGate:
    """
    Gate Phase 2: Structural + Content Quality Integrity.

    Enforces:
    - Valid JSON & Schema
    - Requirements exist and have sources
    - Acceptance Criteria exist
    - Quality heuristics (no vague terms, reasonable length)
    """

    @staticmethod
    def validate(raw_llm_output: str) -> Tuple[bool, str]:
        print("🛡️ [Gate Phase 2] Validating Artifact Integrity...")

        # 1) Basic sanity checks
        if not raw_llm_output or not isinstance(raw_llm_output, str) or not raw_llm_output.strip():
            return False, "LLM output is empty or invalid type."

        # 2) JSON Syntax Validation
        try:
            json_data = json.loads(raw_llm_output)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON syntax: {e.msg}"

        # 3) Pydantic Schema Validation
        try:
            artifact = RequirementsArtifact.model_validate(json_data)
        except ValidationError as e:
            return False, f"Schema validation failed: {e.errors()}"

        # 4) Business Rules & Quality Validation
        errors: List[str] = []

        # (A) MUST have requirements
        if not artifact.requirements:
            errors.append("Requirements list is empty.")
        
        # (B) MUST have Acceptance Criteria
        if not artifact.acceptance_criteria:
            errors.append("Acceptance Criteria list is empty.")

        # (C) Validate Requirements Quality
        vague_terms = ["tbd", "unknown", "maybe", "later", "todo"]
        
        for r in artifact.requirements or []:
            rid = getattr(r, "id", "<missing-id>")
            statement = getattr(r, "statement", "").strip()
            
            # Check sources
            if not getattr(r, "sources", None):
                errors.append(f"Requirement '{rid}' missing sources.")
            
            # Check length
            if len(statement) < 10:
                errors.append(f"Requirement '{rid}' is too short/vague: '{statement}'")
            
            # Check vague terms
            if any(term in statement.lower() for term in vague_terms):
                errors.append(f"Requirement '{rid}' contains vague terms: '{statement}'")

        # (D) Validate Acceptance Criteria Quality
        for ac in artifact.acceptance_criteria or []:
            acid = getattr(ac, "id", "<missing-id>")
            desc = getattr(ac, "description", "").strip()
            
            if len(desc) < 10:
                errors.append(f"AC '{acid}' description is too short.")

        if errors:
            return False, "Validation failed: " + " | ".join(errors)

        print("✅ [Gate Phase 2] Integrity Passed.")
        return True, "OK"
