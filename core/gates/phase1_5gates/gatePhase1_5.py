import json
from typing import Tuple, List, Optional
from pydantic import ValidationError

from core.models.phase1_5models.ContextArtifact import ContextArtifact


class ContextIntegrityGate:
    """
    Gate Phase 1.5: Validates the Context Discovery Artifact.
    Ensures the selected Branch and Space are valid and exist.
    """

    @staticmethod
    def validate(raw_llm_output: str, available_branches: Optional[List[str]] = None) -> Tuple[bool, str]:
        print("🛡️ [Gate Phase 1.5] Validating Context Artifact...")

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
            artifact = ContextArtifact.model_validate(json_data)
        except ValidationError as e:
            return False, f"Schema validation failed: {e.errors()}"

        # 4) Business Rules & Reality Check
        errors: List[str] = []

        # (A) Check Branch Validity
        branch = artifact.target_branch.strip()
        if not branch:
            errors.append("Target branch is empty.")
        elif " " in branch:
            errors.append(f"Target branch '{branch}' contains spaces (invalid format).")
        
        # (B) Reality Check: Does the branch exist?
        if available_branches:
            if branch not in available_branches:
                # We allow creating new branches if explicitly stated, but usually Phase 1.5 selects a BASE branch.
                # If the LLM selected a branch that doesn't exist, it might be hallucinating.
                # However, sometimes the LLM might suggest a NEW branch name.
                # For now, let's be strict: it must pick from available, OR we need a flag for "new branch".
                # Assuming Phase 1.5 selects the BASE branch to work ON (checkout), it MUST exist.
                errors.append(f"Selected branch '{branch}' does not exist in the repository. Available: {available_branches}")

        # (C) Check Space Validity
        space = artifact.confluence_space_key.strip()
        if not space:
            errors.append("Confluence Space Key is empty.")
        
        # (D) Check Reasoning
        if len(artifact.reasoning) < 10:
            errors.append("Reasoning is too short or missing.")

        if errors:
            return False, "Validation failed: " + " | ".join(errors)

        print("✅ [Gate Phase 1.5] Integrity Passed.")
        return True, "OK"
