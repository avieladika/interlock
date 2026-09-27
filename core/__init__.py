"""
core

Main internal package for the Interlock System.

This package exposes the primary orchestration entrypoints.
Submodules (gates, models, synthesizers, etc.) remain internal.
"""

from .synchronizer import InterlockSynchronizer
from .mcp_Manager import MCPManager

__all__ = [
    "InterlockSynchronizer",
    "MCPManager",
]
