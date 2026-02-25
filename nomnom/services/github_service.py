import logging
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

BLOCKED_PREFIXES = {
    "orgs", "users", "features", "marketplace", "settings",
    "notifications", "dashboard", "explore", "pulls", "issues", "sponsors",
}


class GithubService:
    def normalize_url(self, url: str) -> tuple[str, str, str] | None:
        """
        Parse a GitHub URL and return (canonical_url, owner, repo), or None if rejected.
        Strips sub-paths and fragments; rejects profile/org/nav URLs.
        """
        parsed = urlparse(url)
        if parsed.hostname != "github.com":
            return None
        segments = [s for s in parsed.path.split("/") if s]
        if len(segments) < 2:
            return None
        if segments[0] in BLOCKED_PREFIXES:
            return None
        owner, repo = segments[0], segments[1]
        canonical_url = f"https://github.com/{owner}/{repo}"
        return canonical_url, owner, repo

    async def fetch_readme(self, owner: str, repo: str) -> str:
        """Fetch README.md from raw.githubusercontent.com. Returns empty string on failure."""
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.text
                return ""
        except Exception:
            logger.debug("[github] README fetch failed for %s/%s", owner, repo)
            return ""
