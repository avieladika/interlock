import requests
import os


class ConnectivityGate:
    """
    Phase 1: Validation Layer.
    Responsible for verifying that all data sources (Jira, GitHub, etc.)
    are reachable before the synchronization starts.
    """

    def __init__(self):
        # We are matching the EXACT keys from your .env file
        self.atlassian_url = os.getenv("CONFLUENCE_BASE_URL")  # Changed from ATLASSIAN_URL
        self.github_owner = os.getenv("GITHUB_OWNER")
        self.github_repo = os.getenv("GITHUB_REPO")

    def validate_all_connections(self) -> bool:
        """
        Executes connectivity checks for all registered sources.
        Returns True only if all sources respond successfully.
        """
        print(f"🔍 [Phase 1] Starting connectivity validation...")

        # Define the resources to check
        github_url = f"https://github.com/{self.github_owner}/{self.github_repo}"

        # Check results
        checks = {
            "Atlassian/Jira": self._ping(self.atlassian_url),
            "GitHub Repository": self._ping(github_url)
        }

        # Summary of results
        all_passed = True
        for resource, status in checks.items():
            if not status:
                print(f"  ❌ {resource} is UNREACHABLE")
                all_passed = False
            else:
                print(f"  ✅ {resource} is ONLINE")

        return all_passed

    def _ping(self, url) -> bool:
        """
        Low-level helper to check if a URL is alive.
        """
        if not url:
            return False
        try:
            # Using HEAD request for minimal overhead
            response = requests.head(url, timeout=5)
            # 2xx or 3xx status codes mean the resource is there
            return response.status_code < 400
        except Exception:
            return False