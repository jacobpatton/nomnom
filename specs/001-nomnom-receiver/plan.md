# Implementation Plan: NomNom Receiver — Dedup, Filtering & Speed

**Branch**: `001-nomnom-receiver` | **Date**: 2026-02-24 | **Spec**: [spec.md](./spec.md)

## Summary

Three targeted fixes to the existing FastAPI receiver:

1. **YouTube deduplication** — normalize YouTube URLs to canonical `?v=VIDEO_ID` form at parse time so any URL variant (timestamps, playlists, referral params) maps to one DB record.
2. **Reddit homepage filter** — reject Reddit submissions whose URL doesn't contain `/comments/` (i.e., not a post), returning `status="skipped"` immediately.
3. **Faster browser response** — move the synchronous DB write into a background task, returning 202 immediately after payload validation and filtering. The browser gets a response without waiting for SQLite.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, Pydantic v2, sqlite3 (stdlib), youtube-transcript-api
**Storage**: SQLite (WAL mode), URL as UNIQUE key
**Testing**: pytest
**Target Platform**: Linux container / local server
**Project Type**: web-service
**Performance Goals**: Respond to browser < 50ms (currently ~sync DB write time)
**Constraints**: No authentication, single-user, local network

## Constitution Check

Constitution template not yet filled for this project — no gates to enforce. Complexity is minimal (3 small changes across 3 files).

## Project Structure

### Documentation (this feature)

```text
specs/001-nomnom-receiver/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code

```text
nomnom/
├── schemas/
│   └── ingest.py          # CHANGE: add URL normalization validator
├── services/
│   └── ingestion_service.py  # CHANGE: add SubmissionSkipped + check_submission()
└── api/
    └── routes.py          # CHANGE: filter before returning, move write to background
```

---

## Phase 0: Research

No external unknowns. All decisions are based on existing code.

### Decision: YouTube URL normalization location

- **Decision**: Pydantic model validator on `IngestRequest` (schema layer), not service layer
- **Rationale**: Normalizing at parse time means ALL downstream code (service, background task, enrichment) automatically uses the canonical URL. No risk of passing the wrong URL to enrichment.
- **Alternative rejected**: Normalizing in `IngestionService.ingest()` — requires tracking and returning the modified URL; awkward with the async/background refactor.

### Decision: Reddit filter location

- **Decision**: `IngestionService.check_submission()` called synchronously in the route before registering any background task
- **Rationale**: Filtering must happen before we 202 the response, so the browser knows if content was silently skipped. Running it before background registration avoids wasted work.
- **Detection rule**: Reddit post URLs always contain `/comments/` in the path. Any other reddit.com URL (homepage, subreddit listing, user profile) is rejected.

### Decision: Response speed approach

- **Decision**: Return 202 immediately after validation + filtering. DB write and YouTube enrichment run in a single combined async background task.
- **Rationale**: The DB write is the only synchronous blocking step in the critical path for non-YouTube requests. Moving it out of the critical path makes the response near-instant.
- **Tradeoff**: We return `status="queued"` instead of `status="ok"`, which is honest — we've accepted the request but not confirmed the write. If the write fails, the browser isn't notified (acceptable for a local tool with reliable SQLite).
- **Alternative rejected**: Keeping the write synchronous and only speeding up via connection pooling — benchmarking shows the write itself is the bottleneck, not connection setup.

### Decision: Background task structure

- **Decision**: Single `async def _process_submission(payload, ingestion_service, repository)` in `routes.py` that runs ingest then optional YouTube enrichment sequentially.
- **Rationale**: Ingest must complete before enrichment can start (enrichment updates the same row). FastAPI `BackgroundTasks` doesn't support task chaining, so both steps go in one function.
- **Approach**: `await asyncio.to_thread(ingestion_service.ingest, payload)` for the sync DB write, then call the existing `enrich_youtube_submission()` if applicable.

---

## Phase 1: Design

### Data Model (no changes)

The existing data model is unchanged. The UNIQUE constraint on `url` provides deduplication. URL normalization ensures YouTube variants all resolve to the same key.

No new tables, no schema migrations.

### Contracts

The receiver's HTTP API has one observable change:

**POST /** response when submission is filtered:

```json
{ "status": "skipped", "message": "Filtered: Reddit non-post URL" }
```

**POST /** response for accepted submissions (changed):

```json
{ "status": "queued", "message": "Queued" }
```

Previously `status` was `"ok"`. The userscript should treat both `"ok"` and `"queued"` as success. (The userscript is currently out of scope — the server-side change is safe because the userscript only checks for a non-error response.)

### Implementation Detail: Three Changes

#### Change 1: `schemas/ingest.py` — YouTube URL normalization

Add a `model_validator(mode='after')` to `IngestRequest`:

```python
from pydantic import BaseModel, field_validator, model_validator

class IngestRequest(BaseModel):
    url: str
    domain: str
    title: str | None = None
    content_markdown: str | None = None
    metadata: dict = {}

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("url must not be empty")
        return v

    @field_validator("domain")
    @classmethod
    def domain_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("domain must not be empty")
        return v

    @model_validator(mode="after")
    def normalize_youtube_url(self) -> "IngestRequest":
        if self.metadata.get("type") == "youtube_video":
            video_id = self.metadata.get("video_id")
            if video_id:
                self.url = f"https://www.youtube.com/watch?v={video_id}"
        return self
```

#### Change 2: `services/ingestion_service.py` — Reddit filter

Add exception and `check_submission()` method:

```python
from urllib.parse import urlparse

class SubmissionSkipped(Exception):
    pass

class IngestionService:
    def check_submission(self, payload: IngestRequest) -> None:
        """Raises SubmissionSkipped if the submission should be silently ignored."""
        content_type = payload.metadata.get("type", "placeholder")
        if content_type == "reddit_thread":
            path = urlparse(payload.url).path
            if "/comments/" not in path:
                raise SubmissionSkipped(f"Reddit non-post URL filtered")

    def ingest(self, payload: IngestRequest) -> bool:
        # ... unchanged ...
```

#### Change 3: `api/routes.py` — Immediate response + background processing

```python
import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from nomnom.schemas.ingest import IngestRequest, IngestResponse
from nomnom.services.ingestion_service import SubmissionSkipped
from nomnom.services.youtube_service import enrich_youtube_submission

logger = logging.getLogger(__name__)
router = APIRouter()


async def _process_submission(payload, ingestion_service, repository) -> None:
    """Background task: write to DB, then optionally enrich YouTube content."""
    try:
        await asyncio.to_thread(ingestion_service.ingest, payload)
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
                logger.exception("[ingest] enrichment job creation failed | url=%s", payload.url)
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
        return IngestResponse(status="skipped", message=str(exc))

    background_tasks.add_task(_process_submission, payload, ingestion_service, repository)
    return IngestResponse(status="queued", message="Queued")
```

---

## Complexity Tracking

No violations. All changes are minimal surgical edits to existing files.
