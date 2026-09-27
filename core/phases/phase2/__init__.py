"""
core.phase2

Phase 2 Service Layer:
- Collect evidence (Jira/Confluence/GitHub)
- Build EvidenceBundle
- Run synthesizers (Confluence plan + Requirements)
- Return validated RequirementsArtifact
"""

from .phase2service import Phase2Service

__all__ = ["Phase2Service"]
