"""
core.phases

Service-layer phases (Phase 1, Phase 2, Phase 3, Phase 4...).
Each phase encapsulates the business logic of a system stage.
"""

from .phase1 import Phase1Service
from .phase2 import Phase2Service
from .phase3 import Phase3Service
from .phase4 import Phase4Service

__all__ = [
    "Phase1Service",
    "Phase2Service",
    "Phase3Service",
    "Phase4Service",
]
