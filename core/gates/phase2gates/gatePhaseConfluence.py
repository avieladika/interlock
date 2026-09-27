from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set

from core.models.phase2models.confluenceSheiltaArtifact import ConfluenceSheiltaArtifact


@dataclass(frozen=True)
class ConfluenceGateConfig:
    """
    allowed_spaces meanings:
    - None  => OPEN MODE (no allowlist enforcement)
    - set() => also effectively open (no spaces to enforce)
    - non-empty set => enforce that plan.spaces are subset of this set
    """
    allowed_spaces: Optional[Set[str]] = None
    max_page_limit: int = 15
    max_cql_length: int = 600
    require_type_page: bool = True
    require_issue_key_in_cql: bool = True


class ConfluencePlanGateError(Exception):
    """Raised when an LLM plan is unsafe/invalid to execute."""


def apply_confluence_gate(plan: ConfluenceSheiltaArtifact, cfg: ConfluenceGateConfig) -> ConfluenceSheiltaArtifact:
    """
    Enforce hard safety/determinism rules on an LLM-generated CQL plan.
    Returns a (possibly sanitized) plan if accepted, otherwise raises ConfluencePlanGateError.
    """

    # 1) Cap page_limit
    if plan.page_limit > cfg.max_page_limit:
        plan.page_limit = cfg.max_page_limit

    # 2) Filter spaces by allowlist (ONLY if allowlist is provided and non-empty)
    if plan.spaces:
        allowed = cfg.allowed_spaces
        if allowed is not None and len(allowed) > 0:
            # enforce subset
            plan.spaces = [s for s in plan.spaces if s in allowed]
        # else: OPEN MODE -> keep plan.spaces as-is

    # 3) Hard rules on CQL string
    cql = (plan.cql or "").strip()
    if not cql:
        raise ConfluencePlanGateError("CQL is empty")

    if len(cql) > cfg.max_cql_length:
        raise ConfluencePlanGateError(f"CQL too long (>{cfg.max_cql_length})")

    low = cql.lower().replace(" ", "")

    if cfg.require_type_page:
        if "type=page" not in low:
            raise ConfluencePlanGateError("CQL must include type=page")

    if cfg.require_issue_key_in_cql:
        if plan.issue_key not in cql:
            raise ConfluencePlanGateError("CQL must include the issue_key literal")

    # 4) Ban risky/unstable constructs
    banned_substrings = [
        "order by rand",   # non-deterministic
        "macro",           # can explode results
        "permission",      # sensitive/irrelevant
    ]
    low_cql = cql.lower()
    for b in banned_substrings:
        if b in low_cql:
            raise ConfluencePlanGateError(f"CQL contains banned construct: {b}")

    # 5) Normalize final CQL (trim)
    plan.cql = cql
    return plan
