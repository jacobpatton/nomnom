import logging

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

from nomnom.repositories.base import AbstractSubmissionRepository

logger = logging.getLogger(__name__)


class YouTubeService:
    def fetch_transcript(self, video_id: str) -> str:
        """
        Fetch transcript text for a YouTube video.
        Tries English first, then any available language.
        Returns joined plain text. Raises if no transcript is available.
        """
        api = YouTubeTranscriptApi()
        try:
            transcript = api.fetch(video_id, languages=["en"])
        except NoTranscriptFound:
            transcript_list = api.list(video_id)
            transcript = transcript_list.find_transcript(
                [t.language_code for t in transcript_list]
            ).fetch()
        return " ".join(seg.text for seg in transcript)

    def enrich(self, video_id: str) -> tuple[str | None, str | None]:
        """
        Fetch transcript for a YouTube video.
        Returns (transcript_markdown, error_string).
        Never raises — errors are captured and returned as the second element.
        """
        try:
            transcript = self.fetch_transcript(video_id)
            word_count = len(transcript.split())
            logger.info("[youtube] transcript fetched | video_id=%s | words=%d", video_id, word_count)
            return f"## Transcript\n\n{transcript}", None
        except (NoTranscriptFound, TranscriptsDisabled) as exc:
            logger.info("[youtube] no transcript available | video_id=%s | reason=%s", video_id, exc)
            return None, f"no transcript available: {exc}"
        except Exception as exc:
            logger.error("[youtube] enrichment failed | video_id=%s | error=%s", video_id, exc)
            return None, str(exc)


async def enrich_youtube_submission(
    url: str, video_id: str, repository: AbstractSubmissionRepository
) -> None:
    """Background task: enrich a YouTube submission and update the repository."""
    import asyncio

    service = YouTubeService()
    content_markdown, error = await asyncio.to_thread(service.enrich, video_id)

    if error:
        repository.update_submission_content(
            url=url,
            content_markdown=None,
            enrichment_status="failed",
            enrichment_error=error,
        )
        repository.update_enrichment_job_status(url, "failed", failure_reason=error)
    else:
        repository.update_submission_content(
            url=url,
            content_markdown=content_markdown,
            enrichment_status="complete",
        )
        repository.update_enrichment_job_status(url, "complete")
