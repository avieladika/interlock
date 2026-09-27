from __future__ import annotations

from typing import List, Literal
from pydantic import BaseModel, Field, conint, confloat, field_validator


class ConfluenceSheiltaArtifact(BaseModel):
    """
    Strict output contract for LLM-generated Confluence CQL plan.

    NOTE:
    spaces are OPTIONAL here because runtime enforces the space via user input.
    """

    cql: str = Field(..., min_length=10, max_length=600)
    issue_key: str = Field(..., min_length=3, max_length=32)

    terms: List[str] = Field(default_factory=list, min_length=1, max_length=10)

    # ✅ OPTIONAL now (LLM may return empty; runtime overrides with user space)
    spaces: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Optional space keys. Can be empty; runtime enforces the user-selected space.",
    )

    page_limit: conint(ge=1, le=20) = Field(default=10)
    expand: Literal["body.storage", "body.view", "none"] = Field(default="body.storage")
    confidence: confloat(ge=0.0, le=1.0) = Field(default=0.5)
    warnings: List[str] = Field(default_factory=list, max_length=10)

    @field_validator("spaces")
    @classmethod
    def validate_spaces(cls, spaces: List[str]) -> List[str]:
        cleaned: List[str] = []
        for s in spaces or []:
            s = (s or "").strip()
            if not s:
                continue
            if s not in cleaned:
                cleaned.append(s)

        # ✅ no "must contain at least 1"
        if len(cleaned) > 5:
            cleaned = cleaned[:5]
        return cleaned
