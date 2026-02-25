import asyncio
import logging

from youtube_transcript_api import YouTubeTranscriptApi

from nomnom.repositories.base import AbstractSubmissionRepository

logger = logging.getLogger(__name__)

# Error class names vary across youtube-transcript-api versions; catch by name to be safe.
_NO_TRANSCRIPT_ERRORS = ("NoTranscriptFound", "TranscriptsDisabled", "NoTranscriptAvailable")


def _is_no_transcript_error(exc: Exception) -> bool:
    return type(exc).__name__ in _NO_TRANSCRIPT_ERRORS


class YouTubeService:
    def fetch_transcript(self, video_id: str) -> str:
        """
        Fetch transcript text for a YouTube video.
        Tries English first, then falls back to any available language.
        Returns joined plain text. Raises if no transcript can be fetched.
        """
        api = YouTubeTranscriptApi()
        try:
            transcript = api.fetch(video_id, languages=["en"])
            return " ".join(seg.text for seg in transcript)
        except Exception as first_exc:
            if not _is_no_transcript_error(first_exc):
                raise
            logger.debug("[youtube] no English transcript | video_id=%s | trying any language", video_id)

        # Fallback: any available language
        transcript_list = api.list(video_id)
        available = list(transcript_list)
        if not available:
            raise RuntimeError(f"No transcripts available for video_id={video_id}")
        transcript = available[0].fetch()
        return " ".join(seg.text for seg in transcript)

    def enrich(self, video_id: str) -> tuple[str | None, str | None]:
        """
        Returns (transcript_markdown, error_string). Never raises.
        """
        try:
            transcript = self.fetch_transcript(video_id)
            word_count = len(transcript.split())
            logger.info("[youtube] transcript fetched | video_id=%s | words=%d", video_id, word_count)
            return f"## Transcript\n\n{transcript}", None
        except Exception as exc:
            if _is_no_transcript_error(exc):
                logger.info("[youtube] no transcript available | video_id=%s | reason=%s", video_id, exc)
                return None, f"no transcript available: {exc}"
            logger.error("[youtube] enrichment failed | video_id=%s | error=%s", video_id, exc)
            return None, str(exc)


async def enrich_youtube_submission(
    url: str, video_id: str, repository: AbstractSubmissionRepository
) -> None:
    """Background task: enrich a YouTube submission and update the repository."""
    try:
        content_markdown, error = await asyncio.to_thread(
            YouTubeService().enrich, video_id
        )
    except Exception as exc:
        logger.exception("[youtube] background task crashed | video_id=%s | url=%s", video_id, url)
        error = str(exc)
        content_markdown = None

    try:
        repository.update_submission_content(
            url=url,
            content_markdown=content_markdown,
            enrichment_status="failed" if error else "complete",
            enrichment_error=error,
        )
        repository.update_enrichment_job_status(
            url, "failed" if error else "complete", failure_reason=error
        )
    except Exception:
        logger.exception("[youtube] failed to persist enrichment result | url=%s", url)
