# core/utils/debug_dump.py
from __future__ import annotations
import json
from typing import Any, Dict

def _safe_len_text(x: Any) -> int:
    if x is None:
        return 0
    if isinstance(x, str):
        return len(x)
    try:
        return len(x)  # lists/dicts
    except Exception:
        return 0

def summarize_evidence_bundle(bundle: Dict[str, Any]) -> Dict[str, Any]:
    jira = bundle.get("jira") or {}
    confluence = bundle.get("confluence") or {}
    github = bundle.get("github") or {}

    # Jira summary
    jira_summary = {
        "issue_key": jira.get("issue_key") or jira.get("key"),
        "summary_len": _safe_len_text(jira.get("summary")),
        "description_len": _safe_len_text(jira.get("description")),
        "comments_count": _safe_len_text(jira.get("comments")),
        "acceptance_len": _safe_len_text(jira.get("acceptance")),
    }

    # Confluence summary
    pages = confluence.get("pages") or []
    conf_summary = {
        "pages_count": len(pages) if isinstance(pages, list) else _safe_len_text(pages),
        "total_content_len": sum(_safe_len_text(p.get("content")) for p in pages) if isinstance(pages, list) else 0,
        "titles": [p.get("title") for p in pages[:5]] if isinstance(pages, list) else [],
    }

    # GitHub summary
    files = github.get("files") or {}
    gh_summary = {
        "files_count": len(files) if isinstance(files, dict) else _safe_len_text(files),
        "file_names": list(files.keys())[:10] if isinstance(files, dict) else [],
        "total_chars": sum(_safe_len_text(v) for v in files.values()) if isinstance(files, dict) else 0,
    }

    return {
        "jira": jira_summary,
        "confluence": conf_summary,
        "github": gh_summary,
    }

def summarize_requirements_artifact(artifact_dict: Dict[str, Any]) -> Dict[str, Any]:
    reqs = artifact_dict.get("requirements") or []
    unknowns = artifact_dict.get("unknowns") or []
    assumptions = artifact_dict.get("assumptions") or []

    # source refs coverage
    req_with_refs = 0
    refs_flat = []
    for r in reqs if isinstance(reqs, list) else []:
        refs = r.get("source_refs") or []
        if refs:
            req_with_refs += 1
            refs_flat.extend(refs)

    return {
        "requirements_count": len(reqs) if isinstance(reqs, list) else _safe_len_text(reqs),
        "unknowns_count": len(unknowns) if isinstance(unknowns, list) else _safe_len_text(unknowns),
        "assumptions_count": len(assumptions) if isinstance(assumptions, list) else _safe_len_text(assumptions),
        "req_with_source_refs": req_with_refs,
        "unique_source_refs": sorted(set(refs_flat))[:30],
    }

def pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
