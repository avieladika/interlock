from typing import Any, Dict, List, Optional

from core.models.phase2models import EvidenceBundle, EvidenceItem


class EvidenceBuilder:
    """
    Converts raw data (jira issue, confluence pages, github files) into EvidenceBundle.
    Deterministic structure: jira / confluence / github + warnings
    """

    def build(
        self,
        issue_key: str,
        jira_issue: Dict[str, Any],
        confluence_pages: Optional[List[Dict[str, Any]]] = None,
        github_payload: Optional[Dict[str, Any]] = None,
    ) -> EvidenceBundle:
        bundle = EvidenceBundle.empty(issue_key=issue_key)

        # -------------------------
        # Jira -> EvidenceItem(s)
        # -------------------------
        bundle.add_item(
            EvidenceItem(
                source="jira",
                ref=f"jira:{issue_key}",
                title="Jira issue (raw)",
                kind="json",
                content=jira_issue,
            )
        )

        # Optional: add a stable text snapshot (helps LLM)
        bundle.add_item(
            EvidenceItem(
                source="jira",
                ref=f"jira:{issue_key}#text",
                title="Jira issue (stable text snapshot)",
                kind="text",
                content=self._stringify_jira_issue(jira_issue),
            )
        )

        # -------------------------
        # Confluence pages -> EvidenceItem(s)
        # -------------------------
        confluence_pages = confluence_pages or []
        if not confluence_pages:
            bundle.add_warning("Confluence returned no pages.")

        for i, page in enumerate(confluence_pages):
            page_id = str(page.get("id") or page.get("page_id") or "")
            title = page.get("title") or f"Confluence page {page_id}"
            bundle.add_item(
                EvidenceItem(
                    source="confluence",
                    ref=f"confluence:{page_id or 'unknown'}#{i}",
                    title=str(title),
                    kind="json",
                    content=page,
                )
            )

        # -------------------------
        # GitHub -> EvidenceItem(s)  (אופציונלי בשלב זה)
        # -------------------------
        if github_payload:
            bundle.add_item(
                EvidenceItem(
                    source="github",
                    ref="github:repo",
                    title="GitHub repo payload (raw)",
                    kind="json",
                    content=github_payload,
                )
            )

        return bundle

    def _stringify_jira_issue(self, jira_issue: Dict[str, Any]) -> str:
        if not isinstance(jira_issue, dict):
            return str(jira_issue)

        fields = jira_issue.get("fields", {}) if isinstance(jira_issue.get("fields"), dict) else {}
        summary = fields.get("summary", "")
        desc = fields.get("description", "")
        labels = fields.get("labels", [])
        components = [c.get("name") for c in fields.get("components", []) if isinstance(c, dict)]

        return (
            f"issue_key: {jira_issue.get('key', '')}\n"
            f"summary: {summary}\n"
            f"description: {desc}\n"
            f"labels: {labels}\n"
            f"components: {components}\n"
        )
