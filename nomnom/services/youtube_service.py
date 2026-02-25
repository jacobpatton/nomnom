import logging

import yt_dlp
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi

from nomnom.repositories.base import AbstractSubmissionRepository

logger = logging.getLogger(__name__)


class YouTubeService:
    def fetch_metadata(self, url: str) -> dict:
        """Fetch video metadata via yt-dlp. Raises on failure."""
        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "title": info.get("title"),
            "description": info.get("description"),
            "uploader": info.get("uploader"),
            "duration": info.get("duration"),
            "upload_date": info.get("upload_date"),
            "view_count": info.get("view_count"),
        }

    def fetch_transcript(self, video_id: str) -> str:
        """
        Fetch transcript text for a YouTube video.
        Tries English first, then any available language.
        Returns joined plain text. Raises if no transcript is available.
        """
        try:
            segments = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        except NoTranscriptFound:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            segments = transcript_list.find_transcript(
                [t.language_code for t in transcript_list]
            ).fetch()
        return " ".join(seg["text"] for seg in segments)

    def enrich(self, url: str, video_id: str) -> tuple[dict, str | None]:
        """
        Fetch full video data (metadata + transcript).
        Returns (enriched_metadata, error_string).
        Never raises — errors are captured and returned as the second element.
        """
        metadata: dict = {"type": "youtube_video", "video_id": video_id}
        title = None
        content_markdown = None
        error: str | None = None

        try:
            meta = self.fetch_metadata(url)
            title = meta.pop("title", None)
            description = meta.pop("description", None)
            metadata.update(meta)

            try:
                transcript = self.fetch_transcript(video_id)
                word_count = len(transcript.split())
                logger.info(
                    "[youtube] transcript fetched | video_id=%s | words=%d", video_id, word_count
                )
                content_markdown = f"## Description\n\n{description or ''}\n\n## Transcript\n\n{transcript}"
            except (NoTranscriptFound, TranscriptsDisabled) as exc:
                logger.info("[youtube] no transcript available | video_id=%s | reason=%s", video_id, exc)
                content_markdown = f"## Description\n\n{description or ''}"
                metadata["transcript_unavailable"] = True

        except Exception as exc:
            error = str(exc)
            logger.error("[youtube] enrichment failed | video_id=%s | error=%s", video_id, error)

        return {
            "title": title,
            "content_markdown": content_markdown,
            "metadata": metadata,
        }, error


async def enrich_youtube_submission(
    url: str, video_id: str, repository: AbstractSubmissionRepository
) -> None:
    """Background task: enrich a YouTube submission and update the repository."""
    service = YouTubeService()
    result, error = service.enrich(url, video_id)

    if error:
        repository.update_submission_content(
            url=url,
            title=result.get("title"),
            content_markdown=result.get("content_markdown"),
            metadata=result.get("metadata", {}),
            enrichment_status="failed",
            enrichment_error=error,
        )
        repository.update_enrichment_job_status(url, "failed", failure_reason=error)
    else:
        repository.update_submission_content(
            url=url,
            title=result.get("title"),
            content_markdown=result.get("content_markdown"),
            metadata=result.get("metadata", {}),
            enrichment_status="complete",
        )
        repository.update_enrichment_job_status(url, "complete")
