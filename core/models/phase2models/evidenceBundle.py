# core/models/phase2models/evidenceBundle.py
# Deterministic evidence bundle for Phase 2:
# - evidence items normalized into jira / confluence / github buckets
# - stable refs per item (used later as SourceRef.ref)
# - short per-item excerpt to support strict grounding
# - ref_index (valid refs) to prevent "ref hallucinations" by the LLM

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, ConfigDict, field_validator


SourceType = Literal["jira", "confluence", "github"]
EvidenceKind = Literal["text", "json", "file", "link", "snippet"]
EvidenceConfidence = Literal["extracted", "derived"]  # extracted=direct from source, derived=combined/inferred


def _default_excerpt_for(content: Any, max_chars: int = 280) -> str:
    """
    Produce a short excerpt from content WITHOUT mutating content.
    This is used only as a helper when excerpt is not provided.
    """
    try:
        if isinstance(content, str):
            s = content.strip()
            return s[:max_chars] if len(s) > max_chars else s
        # For dict/list we avoid heavy serialization; just a lightweight marker.
        if isinstance(content, dict):
            keys = list(content.keys())[:10]
            return f"json keys: {keys}"
        if isinstance(content, list):
            return f"list[{len(content)}]"
        return str(content)[:max_chars]
    except Exception:
        return ""


class EvidenceItem(BaseModel):
    """
    A single evidence unit.

    IMPORTANT for Phase 2->LLM strict grounding:
    - ref is a stable ID and should be used later as SourceRef.ref
    - excerpt is a short, stable snippet to be cited by the LLM as SourceRef.excerpt
    """

    model_config = ConfigDict(extra="forbid")

    source: SourceType = Field(..., description="Which system produced this evidence.")
    ref: str = Field(
        ...,
        min_length=1,
        description="Stable reference id (e.g., 'jira:KAN-1', 'confluence:12345#0', 'github:README.md').",
    )

    title: Optional[str] = Field(None, description="Human friendly title (optional).")
    kind: EvidenceKind = Field("text", description="Evidence payload type.")
    confidence: EvidenceConfidence = Field(
        "extracted",
        description="extracted=directly from source; derived=combined/inferred from multiple evidence.",
    )

    # Main content (can be large; we do NOT truncate here)
    content: Union[str, Dict[str, Any], List[Any]] = Field(
        ...,
        description="Evidence payload. Usually str, sometimes structured json/list.",
    )

    # Short snippet to support strict grounding (LLM can quote this in SourceRef.excerpt)
    excerpt: str = Field(
        default="",
        description="Short supporting snippet (stable). If empty, will be auto-derived from content.",
    )

    # Metadata for traceability
    url: Optional[str] = Field(None, description="Optional URL for direct navigation.")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    meta: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("ref")
    @classmethod
    def _ref_must_have_prefix(cls, v: str) -> str:
        # Keep refs consistent (prefix:...).
        if ":" not in v:
            raise ValueError("ref must include a prefix like 'jira:...', 'confluence:...', 'github:...'.")
        return v

    @field_validator("excerpt")
    @classmethod
    def _ensure_excerpt_string(cls, v: str) -> str:
        return (v or "").strip()

    def ensure_excerpt(self) -> None:
        """
        Fill excerpt if missing, without altering the main content.
        Safe to call after creation.
        """
        if not self.excerpt:
            self.excerpt = _default_excerpt_for(self.content)


class EvidenceBundle(BaseModel):
    """
    Deterministic bundle for Phase 2.
    Always includes 3 top-level buckets: jira, confluence, github.
    Plus warnings.

    Adds:
    - ref_index: stable list/map of valid refs for strict SourceRef validation.
    """

    model_config = ConfigDict(extra="forbid")

    jira: List[EvidenceItem] = Field(default_factory=list)
    confluence: List[EvidenceItem] = Field(default_factory=list)
    github: List[EvidenceItem] = Field(default_factory=list)

    warnings: List[str] = Field(default_factory=list)

    issue_key: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def empty(cls, issue_key: Optional[str] = None) -> "EvidenceBundle":
        return cls(issue_key=issue_key)

    # -------------------------
    # Mutators / helpers
    # -------------------------

    def add_warning(self, msg: str) -> None:
        msg = (msg or "").strip()
        if msg:
            self.warnings.append(msg)

    def add_item(self, item: EvidenceItem) -> None:
        # Ensure excerpt is always available for strict grounding
        item.ensure_excerpt()

        if item.source == "jira":
            self.jira.append(item)
        elif item.source == "confluence":
            self.confluence.append(item)
        elif item.source == "github":
            self.github.append(item)
        else:
            raise ValueError(f"Unsupported evidence source: {item.source}")

    def add_items(self, items: List[EvidenceItem]) -> None:
        for it in items:
            self.add_item(it)

    # -------------------------
    # Read helpers / metrics
    # -------------------------

    def count_items(self) -> int:
        return len(self.jira) + len(self.confluence) + len(self.github)

    def has_minimum_context(self, min_total_items: int = 3) -> bool:
        return self.count_items() >= min_total_items

    # -------------------------
    # Ref index (valid refs)
    # -------------------------

    def build_ref_index(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns a deterministic index of valid refs.
        Used for:
        - LLM: choose SourceRef.ref from a closed set
        - Gate: verify LLM did not hallucinate refs

        NOTE: We keep only small metadata here (no full content).
        """
        def pack(it: EvidenceItem) -> Dict[str, Any]:
            return {
                "source": it.source,
                "title": it.title,
                "kind": it.kind,
                "url": it.url,
                "excerpt": it.excerpt,
            }

        index: Dict[str, Dict[str, Any]] = {}
        for bucket in (self.jira, self.confluence, self.github):
            for it in bucket:
                # If duplicates occur, last write wins; (you chose not to enforce uniqueness in Gate)
                index[it.ref] = pack(it)
        return index

    # -------------------------
    # LLM context
    # -------------------------

    def to_llm_context(self) -> Dict[str, Any]:
        """
        Deterministic, JSON-serializable object for the synthesizer prompt.

        Adds:
        - ref_index: map of valid refs -> small metadata (excerpt/url/title)
        So the LLM can only cite valid refs in SourceRef.ref.
        """
        # Ensure excerpts are present everywhere
        for bucket in (self.jira, self.confluence, self.github):
            for it in bucket:
                it.ensure_excerpt()

        return {
            "issue_key": self.issue_key,
            "created_at": self.created_at.isoformat(),
            "warnings": list(self.warnings),

            # Closed set of valid refs (for strict grounding + Gate checks)
            "ref_index": self.build_ref_index(),

            # Full items (content can be large; we keep it because you chose 3.A)
            "jira": [it.model_dump() for it in self.jira],
            "confluence": [it.model_dump() for it in self.confluence],
            "github": [it.model_dump() for it in self.github],
        }

    # -------------------------
    # Validation
    # -------------------------

    @field_validator("jira", "confluence", "github")
    @classmethod
    def _no_none_items(cls, v: List[EvidenceItem]) -> List[EvidenceItem]:
        if any(x is None for x in v):
            raise ValueError("Evidence buckets cannot contain None.")
        return v
