import json
import ast
from typing import Tuple, Dict, Any, List

class CodeIntegrityGate:
    """
    Validates the integrity of the Phase 4 Execution Artifact.
    Ensures the LLM output is a valid code change structure AND valid Python code.
    """

    @staticmethod
    def validate(raw_json: str) -> Tuple[bool, str]:
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            return False, "Invalid JSON format."

        if not isinstance(data, dict):
            return False, "Root must be a JSON object."

        # 1. Check required top-level keys
        required_keys = ["changes"]
        for key in required_keys:
            if key not in data:
                return False, f"Missing top-level key: '{key}'"

        # 2. Validate changes list
        changes = data.get("changes")
        if not isinstance(changes, list):
            return False, "'changes' must be a list."

        # 3. Validate each change
        valid_actions = {"create", "modify", "delete"}
        
        for i, change in enumerate(changes):
            if not isinstance(change, dict):
                return False, f"Change #{i+1} is not an object."
            
            # Check required change fields
            change_req_keys = ["file_path", "action", "content", "description"]
            for k in change_req_keys:
                if k not in change:
                    return False, f"Change #{i+1} missing required field: '{k}'"

            # Validate action
            action = change.get("action")
            if action not in valid_actions:
                return False, f"Change #{i+1} has invalid action '{action}'. Must be one of {valid_actions}"
            
            # Validate content (must be string)
            content = change.get("content")
            if not isinstance(content, str):
                 return False, f"Change #{i+1} content must be a string."

            # 4. Syntax Check (AST Parse)
            # Only check syntax if it's a Python file and not a delete action
            file_path = change.get("file_path", "")
            if file_path.endswith(".py") and action != "delete":
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    return False, f"Change #{i+1} ({file_path}) contains invalid Python syntax: {e}"

        return True, "Code execution result is valid."
