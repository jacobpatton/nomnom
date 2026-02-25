import logging

from nomnom.models.submission import Submission
from nomnom.repositories.base import AbstractSubmissionRepository
from nomnom.schemas.ingest import IngestRequest

logger = logging.getLogger(__name__)

KNOWN_CONTENT_TYPES = {"reddit_thread", "github", "youtube_video", "generic_article", "placeholder"}


class IngestionService:
    def __init__(self, repository: AbstractSubmissionRepository) -> None:
        self._repository = repository

    def ingest(self, payload: IngestRequest) -> bool:
        """
        Persist a submission. Returns True if new, False if updated.
        For YouTube submissions, sets enrichment_status to 'pending' but does NOT
        dispatch the background task (that is the route handler's responsibility).
        """
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

        if is_youtube:
            self._repository.create_enrichment_job(payload.url)

        return is_insert
