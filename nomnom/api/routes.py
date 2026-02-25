import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from nomnom.schemas.ingest import IngestRequest, IngestResponse

logger = logging.getLogger(__name__)

router = APIRouter()


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
        ingestion_service.ingest(payload)
    except Exception as exc:
        logger.exception("[ingest] unexpected error for url=%s", payload.url)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    # Record is committed to DB at this point.
    # Schedule enrichment as a background task after the response is sent.
    content_type = payload.metadata.get("type")
    if content_type == "youtube_video":
        video_id = payload.metadata.get("video_id")
        if video_id:
            try:
                repository.create_enrichment_job(payload.url)
            except Exception:
                logger.exception("[ingest] failed to create enrichment job | url=%s", payload.url)
            from nomnom.services.youtube_service import enrich_youtube_submission
            background_tasks.add_task(enrich_youtube_submission, payload.url, video_id, repository)

    return IngestResponse(status="ok", message="Archived")
