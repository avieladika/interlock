from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
import os


TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg",
    ".xml", ".html", ".css", ".js", ".ts", ".tsx", ".jsx",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".java", ".go", ".rs",
    ".sh", ".bat", ".ps1",
    ".dockerfile",  # sometimes used
}

TEXT_FILENAMES = {
    "Dockerfile",
    "Makefile",
    "README",
    "LICENSE",
}


def _is_probably_text(path: str) -> bool:
    name = os.path.basename(path)
    if name in TEXT_FILENAMES:
        return True
    _, ext = os.path.splitext(name)
    return ext.lower() in TEXT_EXTENSIONS


def _should_skip_path(path: str) -> bool:
    # Skip common heavy/noisy folders
    lowered = path.lower()
    skip_parts = [
        "/.git/", "/node_modules/", "/dist/", "/build/", "/.venv/", "/venv/",
        "/__pycache__/", "/.pytest_cache/", "/.mypy_cache/", "/.idea/", "/.vscode/",
        "/.next/", "/coverage/", "/target/", "/bin/", "/obj/",
    ]
    return any(p in f"/{lowered}/" for p in skip_parts)


@dataclass
class GitHubSourceConfig:
    repo: str  # "owner/name"
    branch: Optional[str] = None  # if None -> use default_branch
    max_files: int = 8000
    max_file_bytes: int = 200_000  # 200KB per file
    include_all_paths: bool = True  # if False, only text-like files
    fail_on_rate_limit: bool = False


class GitHubSource:
    """
    Stage 2 source: fetch raw repo data and normalize into Evidence.
    No analysis. No requirements generation. Just collection.  :contentReference[oaicite:1]{index=1}
    """

    def __init__(self, mcp_client: Any, config: GitHubSourceConfig):
        self.mcp = mcp_client
        self.cfg = config

    async def fetch(self) -> Dict[str, Any]:
        repo_info = await self._get_repo_info(self.cfg.repo)
        branch = self.cfg.branch or repo_info.get("default_branch")

        if not branch:
            return {
                "type": "github",
                "repo": self.cfg.repo,
                "error": "Could not resolve branch (no default_branch returned).",
                "files": {},
            }

        file_paths = await self._list_repo_files(self.cfg.repo, branch)

        selected_paths: List[str] = []
        for p in file_paths:
            if _should_skip_path(p):
                continue
            if self.cfg.include_all_paths:
                # still skip obvious binaries by extension if you want;
                # but since user asked "repo full", we keep everything text-ish below when downloading.
                selected_paths.append(p)
            else:
                if _is_probably_text(p):
                    selected_paths.append(p)

            if len(selected_paths) >= self.cfg.max_files:
                break

        files: Dict[str, str] = {}
        warnings: List[str] = []

        for p in selected_paths:
            # If include_all_paths=True, still avoid binaries by only downloading text-ish.
            if not _is_probably_text(p) and self.cfg.include_all_paths:
                continue

            try:
                content = await self._get_file_content(self.cfg.repo, p, branch)
                if content is None:
                    continue

                # Hard cap by bytes (roughly)
                if isinstance(content, str) and len(content.encode("utf-8", errors="ignore")) > self.cfg.max_file_bytes:
                    warnings.append(f"Skipped large file (>{self.cfg.max_file_bytes} bytes): {p}")
                    continue

                files[p] = content

            except Exception as e:
                msg = str(e)
                warnings.append(f"Failed to fetch {p}: {msg}")
                if self.cfg.fail_on_rate_limit and "rate limit" in msg.lower():
                    break

        evidence = {
            "type": "github",
            "repo": self.cfg.repo,
            "branch": branch,
            "files": files,
            "warnings": warnings,
        }
        return evidence

    # ---------------- MCP wrappers (adapt tool names to your MCP server) ----------------

    async def _get_repo_info(self, repo: str) -> Dict[str, Any]:
        # Example tool name: github_get_repository
        # Should return something including "default_branch"
        return await self.mcp.github_get_repository({"repo": repo})

    async def _list_repo_files(self, repo: str, branch: str) -> List[str]:
        """
        Returns a flat list of file paths in the repo at the given branch.
        Preferred approach: use Git tree API via MCP (recursive).
        """
        # Example tool name: github_get_tree (recursive)
        tree = await self.mcp.github_get_tree({"repo": repo, "branch": branch, "recursive": True})

        paths: List[str] = []
        for item in tree.get("tree", []):
            if item.get("type") == "blob" and item.get("path"):
                paths.append(item["path"])
        return paths

    async def _get_file_content(self, repo: str, path: str, branch: str) -> Optional[str]:
        # Example tool name: github_get_file_contents
        # Should return text content (decoded) if file is text.
        res = await self.mcp.github_get_file_contents({"repo": repo, "path": path, "branch": branch})

        # Adapt depending on your MCP response shape
        # Common shapes: {"content": "..."} or {"text": "..."}.
        return res.get("content") or res.get("text")
