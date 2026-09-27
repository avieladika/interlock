from pydantic import BaseModel, Field
from typing import Optional

class ContextArtifact(BaseModel):
    """
    Output of Phase 1.5: Context Discovery.
    Contains the decisions about WHERE to work (Branch, Space).
    """
    ticket_id: str
    ticket_summary: str
    
    target_branch: str = Field(..., description="The GitHub branch to base changes on (e.g., 'main')")
    confluence_space_key: str = Field(..., description="The Confluence Space Key to search for requirements (e.g., 'ENG')")
    
    reasoning: str = Field(..., description="Why these contexts were chosen")

    def is_usable(self) -> bool:
        return bool(self.target_branch and self.confluence_space_key)
