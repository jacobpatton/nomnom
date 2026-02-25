import logging
from urllib.parse import urlparse

from nomnom.models.submission import Submission
from nomnom.repositories.base import AbstractSubmissionRepository
from nomnom.schemas.ingest import IngestRequest, IngestResponse
from nomnom.services.github_service import GithubService

logger = logging.getLogger(__name__)

KNOWN_CONTENT_TYPES = {"reddit_thread", "github", "youtube_video", "generic_article", "placeholder"}


class SubmissionSkipped(Exception):
    pass


class IngestionService:
    def __init__(self, repository: AbstractSubmissionRepository) -> None:
        self._repository = repository
        self._github = GithubService()

    def check_submission(self, payload: IngestRequest) -> None:
        """Raises SubmissionSkipped if this submission should be silently ignored."""
        content_type = payload.metadata.get("type", "placeholder")
        if content_type == "reddit_thread":
            path = urlparse(payload.url).path
            if "/comments/" not in path:
                raise SubmissionSkipped("Reddit non-post URL filtered")

    async def _ingest_github(self, payload: IngestRequest) -> IngestResponse:
        """Handle GitHub repository ingestion. Returns saved or skipped response."""
        result = self._github.normalize_url(payload.url)
        if result is None:
            logger.info("[ingest] github url rejected | url=%s", payload.url)
            return IngestResponse(status="skipped", message="Not a valid GitHub repository URL")
        canonical_url, owner, repo = result
        if self._repository.exists_by_url(canonical_url):
            logger.info("[ingest] github duplicate | url=%s", canonical_url)
            return IngestResponse(status="skipped", message="Already saved")
        readme = await self._github.fetch_readme(owner, repo)
        self._repository.insert_github_repo(canonical_url, owner, repo, readme)
        logger.info("[ingest] github saved | url=%s", canonical_url)
        return IngestResponse(status="saved", message="Saved")

    async def ingest(self, payload: IngestRequest) -> IngestResponse:
        """
        Persist a submission. Returns an IngestResponse with status saved/updated/skipped.
        """
        if payload.domain == "github.com":
            return await self._ingest_github(payload)

        content_type = payload.metadata.get("type", "placeholder")
        if content_type not in KNOWN_CONTENT_TYPES:
            logger.info("[ingest] unknown content_type=%r, storing as placeholder", content_type)
            content_type = "placeholder"

        is_youtube = content_type == "youtube_video"

        submission = Submission(
            url=payload.url,
            domain=payload.domain,
            title=payload.title,
            content_markdown=payload.content_markdown,
            content_type=content_type,
            metadata=payload.metadata,
            enrichment_status="pending" if is_youtube else "none",
        )

        is_insert = self._repository.upsert(submission)

        logger.info(
            "[ingest] %s | url=%s | type=%s",
            "new" if is_insert else "updated",
            payload.url,
            content_type,
        )

        return IngestResponse(
            status="saved" if is_insert else "updated",
            message="Saved" if is_insert else "Updated",
        )
