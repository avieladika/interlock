import json
import os
from typing import Tuple, Dict, Any, List, Optional

class PlanIntegrityGate:
    """
    Validates the integrity of the Phase 3 Plan Artifact.
    Ensures the LLM output is a valid plan structure and logically sound.
    """

    @staticmethod
    def validate(raw_json: str, requirements_ids: Optional[List[str]] = None, repo_path: Optional[str] = None) -> Tuple[bool, str]:
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            return False, "Invalid JSON format."

        if not isinstance(data, dict):
            return False, "Root must be a JSON object."

        # 1. Check required top-level keys
        required_keys = ["ticket_id", "goal", "steps"]
        for key in required_keys:
            if key not in data:
                return False, f"Missing top-level key: '{key}'"

        # 2. Validate steps list
        steps = data.get("steps")
        if not isinstance(steps, list):
            return False, "'steps' must be a list."
        
        if len(steps) == 0:
            return False, "'steps' list cannot be empty."

        # 3. Validate each step
        valid_types = {"code", "investigation", "configuration", "testing"}
        linked_reqs = set()
        
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                return False, f"Step #{i+1} is not an object."
            
            # Check required step fields
            step_req_keys = ["step_id", "title", "type"]
            for k in step_req_keys:
                if k not in step or not step[k]:
                    return False, f"Step #{i+1} missing required field: '{k}'"

            # Validate step type
            s_type = step.get("type")
            if s_type not in valid_types:
                return False, f"Step #{i+1} has invalid type '{s_type}'. Must be one of {valid_types}"
            
            # Collect linked requirements
            linked_id = step.get("linked_requirement_id")
            if linked_id:
                linked_reqs.add(linked_id)

            # Validate file existence (if repo_path is provided and action is modify)
            # We assume the step might have a 'file_paths' list
            file_paths = step.get("file_paths", [])
            if repo_path and file_paths and s_type == "code":
                for fpath in file_paths:
                    # If the plan says we are modifying a file, it should ideally exist.
                    # But sometimes the plan says "Create X", so we can't be too strict unless we know the action.
                    # For now, we'll just log a warning or check if it looks like a valid path.
                    if ".." in fpath or fpath.startswith("/"):
                         return False, f"Step #{i+1} has suspicious file path: '{fpath}'"

        # 4. Validate Requirements Coverage (if requirements provided)
        if requirements_ids:
            missing_reqs = set(requirements_ids) - linked_reqs
            if missing_reqs:
                # We don't fail, but we append a warning to the message
                return True, f"Plan is valid, but some requirements are not linked: {missing_reqs}"

        return True, "Plan is valid."
