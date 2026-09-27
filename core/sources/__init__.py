"""
Sources package.

This module exposes all data source classes responsible for
fetching raw data from external systems (Jira, Confluence, GitHub, etc.).

Usage:
    from core.sources import JiraSource, ConfluenceSource, GitHubSource
"""

from .jira_source import JiraSource
from .confluence_source import ConfluenceSource
from .github_source import GitHubSource

__all__ = [
    "JiraSource",
    "ConfluenceSource",
    "GitHubSource",
]
