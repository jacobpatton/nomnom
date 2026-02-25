import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from nomnom.schemas.ingest import IngestRequest, IngestResponse
from nomnom.services.ingestion_service import SubmissionSkipped
from nomnom.services.youtube_service import enrich_youtube_submission

logger = logging.getLogger(__name__)

router = APIRouter()


async def _process_submission(
    payload: IngestRequest, ingestion_service, repository
) -> None:
    """Background task: write submission to DB, then optionally enrich YouTube content."""
    try:
        await ingestion_service.ingest(payload)
    except Exception:
        logger.exception("[ingest] background write failed | url=%s", payload.url)
        return

    content_type = payload.metadata.get("type")
    if content_type == "youtube_video":
        video_id = payload.metadata.get("video_id")
        if video_id:
            try:
                await asyncio.to_thread(repository.create_enrichment_job, payload.url)
            except Exception:
                logger.exception(
                    "[ingest] enrichment job creation failed | url=%s", payload.url
                )
            await enrich_youtube_submission(payload.url, video_id, repository)


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/", response_model=IngestResponse)
async def ingest(
    payload: IngestRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> IngestResponse:
    ingestion_service = request.app.state.ingestion_service
    repository = request.app.state.repository

    try:
        ingestion_service.check_submission(payload)
    except SubmissionSkipped as exc:
        logger.info("[ingest] skipped | url=%s | reason=%s", payload.url, exc)
        return IngestResponse(status="skipped", message="Filtered: Reddit non-post URL")

    if payload.domain == "github.com":
        return await ingestion_service.ingest(payload)

    background_tasks.add_task(_process_submission, payload, ingestion_service, repository)
    return IngestResponse(status="queued", message="Queued")
