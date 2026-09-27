from pydantic import BaseModel, Field
from typing import List, Literal


# -------- Sources (required for both requirements and AC) --------
SourceType = Literal["jira", "confluence", "github"]

class SourceRef(BaseModel):
    type: SourceType = Field(..., description="Origin system")
    ref: str = Field(
        ...,
        description="Stable pointer (URL or path). Example: GitHub 'repo:path#Lx-Ly'.",
        min_length=1,
    )
    excerpt: str = Field(
        ...,
        description="Short supporting snippet from the source (keep it small).",
        min_length=1,
    )


# -------- Requirements --------
RequirementType = Literal["functional", "non_functional", "constraint"]

class Requirement(BaseModel):
    id: str = Field(..., description="Unique ID for the requirement (e.g., R-1)")
    type: RequirementType = Field(..., description="functional | non_functional | constraint")
    statement: str = Field(..., description="MUST/SHALL requirement statement", min_length=1)
    sources: List[SourceRef] = Field(
        ...,
        description="Required evidence backing this requirement",
        min_length=1
    )


# -------- Acceptance Criteria --------
class AcceptanceCriteria(BaseModel):
    id: str = Field(..., description="Unique ID for the AC (e.g., AC-1)")
    description: str = Field(..., description="Testable condition", min_length=1)
    is_automated: bool = Field(default=False, description="Can this be verified via code?")
    sources: List[SourceRef] = Field(
        default_factory=list,
        description="Required evidence backing this AC",
    )


class RequirementsArtifact(BaseModel):
    """
    Skeleton returned by the LLM.
    The artifact itself does NOT handle input collection/stop logic.
    """
    ticket_id: str
    summary: str

    requirements: List[Requirement] = Field(
        ...,
        description="Derived requirements (including constraints as type='constraint').",
        min_length=1
    )

    acceptance_criteria: List[AcceptanceCriteria] = Field(
        default_factory=list,
        description="Derived acceptance criteria (not linked to requirements)."
    )

    unknowns: List[str] = Field(
        default_factory=list,
        description="Missing info/ambiguities that prevent moving forward."
    )

    def is_usable(self) -> bool:
        # Minimal: only unknowns gate + must have requirements
        return (len(self.unknowns) == 0) and (len(self.requirements) > 0)
