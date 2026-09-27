from typing import List, Optional
from pydantic import BaseModel, Field

class FileChange(BaseModel):
    file_path: str = Field(..., description="Relative path to the file (e.g., core/models/MyModel.py)")
    content: str = Field(..., description="Full content of the file (or diff)")
    action: str = Field(..., description="create | modify | delete")
    description: str = Field(..., description="Short explanation of the change")

class StepExecutionResult(BaseModel):
    step_id: str = Field(..., description="ID of the plan step executed")
    status: str = Field(..., description="success | failed | skipped")
    changes: List[FileChange] = Field(default_factory=list, description="List of file changes produced by this step")
    logs: str = Field("", description="Execution logs or reasoning from the LLM")

class ExecutionArtifact(BaseModel):
    ticket_id: str
    results: List[StepExecutionResult] = Field(default_factory=list, description="Results for each step in the plan")

    def is_complete(self) -> bool:
        # Simple check: do we have results?
        return len(self.results) > 0
