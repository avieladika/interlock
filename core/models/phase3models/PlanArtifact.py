from typing import List, Optional, Literal
from pydantic import BaseModel, Field

StepType = Literal["code", "investigation", "configuration", "testing"]

class PlanStep(BaseModel):
    step_id: str = Field(..., description="Unique ID for the step (e.g., S-1)")
    title: str = Field(..., description="Short title of the step")
    description: str = Field(..., description="Detailed technical description of what needs to be done")
    type: StepType = Field(..., description="Type of activity")
    linked_requirement_id: Optional[str] = Field(
        None, 
        description="The ID of the Requirement (R-x) or AC (AC-x) this step satisfies. 'None' if it's a general setup step."
    )
    file_paths: List[str] = Field(
        default_factory=list, 
        description="Target files to be created or modified (if known)"
    )

class PlanArtifact(BaseModel):
    """
    Represents the structured technical plan generated in Phase 3.
    """
    ticket_id: str
    goal: str = Field(..., description="High level goal of this plan")
    
    steps: List[PlanStep] = Field(
        ..., 
        description="Ordered list of technical steps to execute",
        min_length=1
    )

    risks: List[str] = Field(
        default_factory=list,
        description="Potential technical risks identified during planning"
    )

    def is_usable(self) -> bool:
        # A plan is usable if it has at least one step
        return len(self.steps) > 0
