"""
core.gates

Root gates package.
Phase-specific gates are under phase1gates/, phase2gates/, phase3gates/, phase4gates/, etc.
"""

from .phase1gates import *
from .phase2gates import *
from .phase3gates import *
from .phase4gates import *

__all__ = []
__all__ += phase1gates.__all__  # type: ignore[name-defined]
__all__ += phase2gates.__all__  # type: ignore[name-defined]
__all__ += phase3gates.__all__  # type: ignore[name-defined]
__all__ += phase4gates.__all__  # type: ignore[name-defined]
