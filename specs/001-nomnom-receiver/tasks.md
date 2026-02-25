# Tasks: NomNom Knowledge Receiver

**Input**: Design documents from `/specs/001-nomnom-receiver/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ingest-endpoint.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US4)

## Path Conventions

Single project: `nomnom/` package at repository root, `tests/` alongside it.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create project skeleton before any implementation begins.

- [x] T001 Create full directory structure with empty `__init__.py` files: `nomnom/{models,schemas,repositories,services,api}/`, `nomnom/db/migrations/`, `tests/{unit,integration}/`
- [x] T002 Create `requirements.txt` (fastapi[standard], uvicorn[standard], pydantic-settings, yt-dlp, youtube-transcript-api) and `requirements-dev.txt` (pytest, pytest-asyncio, httpx)
- [x] T003 [P] Create `pyproject.toml` with ruff linting and formatting configuration (line-length 100, isort rules)
- [x] T004 [P] Create `.env.example` with `PORT=3002`, `DB_PATH=/data/nomnom.db`, `LOG_LEVEL=info`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL user stories depend on. No user story work begins until this phase is complete.

**⚠️ CRITICAL**: Blocks all user story phases.

- [x] T005 Implement `nomnom/config.py` — `Settings` class using pydantic-settings; reads `PORT` (int, default 3002), `DB_PATH` (str, default `/data/nomnom.db`), `LOG_LEVEL` (str, default `info`) from environment
- [x] T006 Create `nomnom/db/migrations/001_init.sql` — exact DDL from `data-model.md`: `submissions` table (all fields with constraints), `enrichment_jobs` table, two indexes, `PRAGMA journal_mode=WAL`
- [x] T007 Implement `nomnom/db/connection.py` — `get_connection(db_path)` factory (opens SQLite, sets WAL mode, `timeout=10`, `row_factory=sqlite3.Row`) and `run_migrations(db_path)` runner (creates `_schema_migrations` tracking table, applies `*.sql` files from `migrations/` in filename order, skips already-applied)
- [x] T008 [P] Implement `nomnom/repositories/base.py` — `AbstractSubmissionRepository` ABC with abstract method signatures for `upsert()`, `create_enrichment_job()`, and `update_enrichment_job_status()`
- [x] T009 Implement `nomnom/repositories/submission_repository.py` — `SubmissionRepository(AbstractSubmissionRepository)`: `upsert(submission)` using `INSERT INTO submissions ... ON CONFLICT(url) DO UPDATE SET ... ingested_at = submissions.ingested_at, updated_at = CURRENT_TIMESTAMP`; `create_enrichment_job(url)`; `update_enrichment_job_status(url, status, failure_reason=None)`

**Checkpoint**: DB schema applied, connection factory tested manually (`python -c "from nomnom.db.connection import get_connection"`). Repository instantiates without error.

---

## Phase 3: User Story 1 — Passive Content Capture (Priority: P1) 🎯 MVP

**Goal**: The receiver accepts a JSON submission from the userscript, persists it to SQLite, and returns HTTP 200. Standard content types (Reddit, GitHub, generic) work end-to-end.

**Independent Test**: Start the server (`uvicorn nomnom.main:app --port 3002`), send a `curl` POST matching the standard payload in `contracts/ingest-endpoint.md`, verify HTTP 200 and data in the SQLite file.

- [x] T010 [P] [US1] Implement `nomnom/models/submission.py` — `Submission` and `EnrichmentJob` dataclasses matching all fields in `data-model.md` (use `@dataclass`, include `ingested_at` and `updated_at` as `datetime`)
- [x] T011 [P] [US1] Implement `nomnom/schemas/ingest.py` — `IngestRequest` Pydantic model (`url: str`, `domain: str`, `title: str | None`, `content_markdown: str | None`, `metadata: dict`); `IngestResponse` model (`status: str`, `message: str`)
- [x] T012 [US1] Implement `nomnom/services/ingestion_service.py` — `IngestionService.ingest(payload: IngestRequest)` for standard content types: extract `content_type` from `payload.metadata["type"]`, default unknown types to `placeholder`, build `Submission` object, call `repository.upsert()`, return operation result
- [x] T013 [US1] Implement `nomnom/api/routes.py` — `POST /` handler (accepts `IngestRequest`, calls `IngestionService.ingest()`, returns `IngestResponse`); `GET /health` handler (returns `{"status": "ok"}`); mount `CORSMiddleware` with `allow_origins=["*"]`, `allow_methods=["POST", "GET", "OPTIONS"]`, `allow_headers=["*"]`
- [x] T014 [US1] Implement `nomnom/main.py` — `create_app()` factory: instantiate `FastAPI`, register router from `api/routes.py`, add lifespan context manager that calls `run_migrations(settings.DB_PATH)` on startup; add `if __name__ == "__main__"` Uvicorn launch block

**Checkpoint**: `curl -X POST http://localhost:3002/ -H "Content-Type: application/json" -d '{"url":"https://reddit.com/r/test/comments/abc/title/","domain":"reddit.com","title":"Test","content_markdown":"# Hello","metadata":{"type":"reddit_thread"}}'` returns `{"status":"ok","message":"Archived"}`. Row visible in SQLite.

---

## Phase 4: User Story 2 — YouTube Full Content Extraction (Priority: P2)

**Goal**: When the receiver gets a `youtube_video` submission, it immediately returns 200 and asynchronously fetches the video title, description, and transcript via server-side tooling, updating the stored record.

**Independent Test**: Submit a YouTube URL (`{"url":"https://www.youtube.com/watch?v=<id>","domain":"www.youtube.com","metadata":{"type":"youtube_video","video_id":"<id>"}}`) to the running receiver, receive 200 immediately, wait 10–15 seconds, inspect SQLite — the row should contain the actual title and transcript text, not the placeholder.

- [x] T015 [US2] Implement `nomnom/services/youtube_service.py` — `YouTubeService` with two methods: `fetch_metadata(url: str) -> dict` using `yt_dlp.YoutubeDL({"skip_download": True, "quiet": True})` (returns `title`, `description`, `uploader`, `duration`, `upload_date`, `view_count`); `fetch_transcript(video_id: str) -> str` using `YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])` with fallback to any available language, returning joined plain text; each method raises descriptive exception on failure
- [x] T016 [US2] Add `enrich(url: str, video_id: str) -> tuple[dict, str]` to `YouTubeService` in `nomnom/services/youtube_service.py` — orchestrates `fetch_metadata` then `fetch_transcript`; on any failure returns partial data and error string rather than raising
- [x] T017 [US2] Add `enrich_youtube_submission(url, video_id, repository)` async background function in `nomnom/services/ingestion_service.py` — calls `YouTubeService.enrich()`, updates submission `content_markdown` and `metadata` via `repository.upsert()`, calls `repository.update_enrichment_job_status()` with `complete` or `failed`
- [x] T018 [US2] Update `nomnom/api/routes.py` `POST /` handler — inject `BackgroundTasks`; after saving the submission, if `content_type == "youtube_video"` call `background_tasks.add_task(enrich_youtube_submission, url, video_id, repository)`; update `IngestionService.ingest()` in `nomnom/services/ingestion_service.py` to set `enrichment_status = "pending"` and call `repository.create_enrichment_job(url)` for YouTube submissions before returning

**Checkpoint**: YouTube submission returns 200 immediately. After ~15 seconds the SQLite row for that URL has a non-placeholder `content_markdown` containing transcript text (or `enrichment_error` populated on failure, `enrichment_status` = `"failed"`).

---

## Phase 5: User Story 3 — Duplicate URL Handling (Priority: P3)

**Goal**: Submitting the same URL a second time updates the existing record (preserving `ingested_at`) rather than creating a duplicate or returning an error.

**Independent Test**: Submit the same URL twice with different `title` values. Query SQLite: only one row for that URL, `title` reflects the second submission, `ingested_at` matches the first submission time, `updated_at` reflects the second submission time.

- [x] T019 [US3] Verify and harden `upsert()` SQL in `nomnom/repositories/submission_repository.py` — confirm the `ON CONFLICT(url) DO UPDATE` clause explicitly sets `ingested_at = submissions.ingested_at` (not `excluded.ingested_at`) to preserve original capture timestamp; add `updated_at = CURRENT_TIMESTAMP` to the update clause; return a flag indicating whether the operation was an insert or update
- [x] T020 [US3] Add upsert outcome logging in `nomnom/services/ingestion_service.py` — after `repository.upsert()` returns, log at INFO level: `"[ingest] {'new' if is_insert else 'updated'} | url={url} | type={content_type}"`

**Checkpoint**: Submit `https://reddit.com/r/test/comments/abc/` twice. SQLite contains exactly one row. `ingested_at` is unchanged. `updated_at` is later than `ingested_at`.

---

## Phase 6: User Story 4 — Containerized Deployment (Priority: P4)

**Goal**: The receiver can be built as a Docker image, pushed to GHCR automatically via GitHub Actions, and run with a single `docker compose up` command with data persisted across restarts.

**Independent Test**: On a machine with Docker installed, run `docker compose up -d`, then `curl http://localhost:3002/health`. Returns `{"status":"ok"}`. Send a test submission. Stop and restart the container. Submission is still present in SQLite.

- [x] T021 [P] [US4] Write `Dockerfile` — two stages: `builder` (`python:3.12-slim`, create venv at `/opt/venv`, install `requirements.txt`); `runtime` (`python:3.12-slim`, copy `/opt/venv` from builder, create non-root user `appuser` UID 1000, copy `nomnom/` package, set `ENV PATH /opt/venv/bin:$PATH`, `EXPOSE 3002`, `CMD ["uvicorn", "nomnom.main:app", "--host", "0.0.0.0", "--port", "3002"]`)
- [x] T022 [P] [US4] Write `.dockerignore` — exclude `.venv/`, `__pycache__/`, `*.pyc`, `.git/`, `tests/`, `specs/`, `.env`, `*.md`, `.github/`
- [x] T023 [US4] Write `docker-compose.yml` — single service `nomnom-receiver`: `image: ghcr.io/<owner>/nomnom-receiver:latest`, `ports: ["127.0.0.1:3002:3002"]`, `volumes: [nomnom_data:/data]`, `environment: {DB_PATH: /data/nomnom.db}`, `restart: unless-stopped`, `healthcheck: {test: ["CMD", "curl", "-f", "http://localhost:3002/health"], interval: 30s, retries: 3}`; define `volumes: {nomnom_data: {}}`
- [x] T024 [US4] Write `.github/workflows/docker-publish.yml` — trigger on `push` to `main`; permissions: `contents: read`, `packages: write`; steps: checkout, set up QEMU (for arm64), set up Docker Buildx, log in to GHCR using `GITHUB_TOKEN`, extract metadata (tags: `latest` + `sha-${{ github.sha }}`), build and push multi-arch (`linux/amd64,linux/arm64`) to `ghcr.io/${{ github.repository_owner }}/nomnom-receiver`

**Checkpoint**: Push to `main` branch. GitHub Actions workflow completes. `docker pull ghcr.io/<owner>/nomnom-receiver:latest` succeeds. `docker compose up -d` starts the container. `curl http://localhost:3002/health` returns 200.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Logging, error handling hardening, and documentation across all stories.

- [x] T025 [P] Add structured logging to `nomnom/services/ingestion_service.py` and `nomnom/services/youtube_service.py` — log at startup (config values, db path), per ingest (url, content_type, insert vs update), per enrichment outcome (success: word count of transcript; failure: error message and video_id)
- [x] T026 [P] Harden input validation and error responses in `nomnom/schemas/ingest.py` and `nomnom/api/routes.py` — ensure missing `url` returns 422 with clear message; unknown `metadata.type` silently stored as `placeholder` with INFO log; unhandled exceptions caught by FastAPI exception handler returning 500 JSON matching contract format
- [x] T027 [P] Write `README.md` — project overview (NomNom receiver, what it does), prerequisites (Docker), quickstart (docker compose up, curl health check, userscript `SERVER_URL` config), development setup (venv, uvicorn --reload), data access note (SQLite path)
- [ ] T028 End-to-end validation per `quickstart.md` — run receiver locally or via Docker, open browser with userscript active, visit a Reddit thread, a GitHub page, and a YouTube video; confirm three rows appear in SQLite with correct content types and non-empty content; confirm YouTube row eventually has transcript content

---

## Phase 8: Improvements — Dedup, Filtering & Speed

**Purpose**: Three targeted fixes to the working codebase based on real-world usage. No schema changes, no new files — surgical edits to three existing files.

**Reference**: `specs/001-nomnom-receiver/plan.md` (2026-02-24 revision)

### a) Update Contract Doc

- [x] T029 Update `specs/001-nomnom-receiver/contracts/ingest-endpoint.md` — document two new response shapes alongside the existing `{"status":"ok"}` example: `{"status":"queued","message":"Queued"}` (accepted submissions, backwards-compatible — userscript treats any 200 as success) and `{"status":"skipped","message":"Filtered: Reddit non-post URL"}` (filtered submissions)

### b) YouTube Duplicate Prevention [US3]

**Goal**: Any YouTube URL variant (timestamps, playlist params, etc.) normalizes to `https://www.youtube.com/watch?v={video_id}` at parse time, so the existing `UNIQUE(url)` constraint handles deduplication automatically.

**Independent Test**: POST `https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLxxx&t=42` with `video_id=dQw4w9WgXcQ`, then POST `https://www.youtube.com/watch?v=dQw4w9WgXcQ` — DB has exactly 1 row with URL `https://www.youtube.com/watch?v=dQw4w9WgXcQ`.

- [x] T030 [P] [US3] Add `model_validator(mode="after")` to `IngestRequest` in `nomnom/schemas/ingest.py` — import `model_validator` from `pydantic`; when `self.metadata.get("type") == "youtube_video"` and `video_id = self.metadata.get("video_id")` is truthy, set `self.url = f"https://www.youtube.com/watch?v={video_id}"` and return `self`

### c) Reddit Homepage Filter [US1]

**Goal**: Reject Reddit submissions that are not posts (homepage, subreddit listings, user profiles). Only URLs containing `/comments/` in the path are accepted.

**Independent Test**: POST `https://www.reddit.com/` with `metadata.type="reddit_thread"` → response `{"status":"skipped"}`. POST `https://www.reddit.com/r/Python/comments/abc123/title/` → response `{"status":"queued"}` and DB record appears.

- [x] T031 [P] [US1] Add `SubmissionSkipped` exception class and `check_submission(payload: IngestRequest) -> None` method to `IngestionService` in `nomnom/services/ingestion_service.py` — import `urlparse` from `urllib.parse`; `check_submission` raises `SubmissionSkipped("Reddit non-post URL filtered")` when `metadata.type == "reddit_thread"` and `/comments/` is not in `urlparse(payload.url).path`

### d) Faster Browser Response [US1]

**Goal**: Return 200 to the browser before the DB write. Move the synchronous DB write (and YouTube enrichment) into a single background task. Response is near-instant regardless of content type.

**Independent Test**: POST any article URL and measure response time — should be < 50ms. DB record appears within ~1 second after response. YouTube enrichment still completes asynchronously.

- [x] T032 [US1] Add async `_process_submission(payload, ingestion_service, repository)` helper in `nomnom/api/routes.py` — runs `await asyncio.to_thread(ingestion_service.ingest, payload)`; then if `metadata.type == "youtube_video"` and `video_id` present: `await asyncio.to_thread(repository.create_enrichment_job, payload.url)` then `await enrich_youtube_submission(payload.url, video_id, repository)`; wraps each step in try/except with `logger.exception` on failure (depends on T031)

- [x] T033 [US1] Refactor `ingest` route handler in `nomnom/api/routes.py` — (1) import `SubmissionSkipped` from `nomnom.services.ingestion_service`; (2) call `ingestion_service.check_submission(payload)` synchronously and return `IngestResponse(status="skipped", message="Filtered: Reddit non-post URL")` on `SubmissionSkipped`; (3) register `_process_submission` as background task; (4) return `IngestResponse(status="queued", message="Queued")` immediately — remove old inline `create_enrichment_job` call and `enrich_youtube_submission` background task registration from route body (depends on T031, T032)

**Checkpoint**: Reddit homepage POST returns `{"status":"skipped"}`. Any other POST returns `{"status":"queued"}` near-instantly. DB write and YouTube enrichment complete in background.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Requires Phase 1 — BLOCKS all user story phases
- **Phase 3 (US1 P1)**: Requires Phase 2
- **Phase 4 (US2 P2)**: Requires Phase 3 (builds on IngestionService and routes)
- **Phase 5 (US3 P3)**: Requires Phase 3 (hardens repository upsert already in place)
- **Phase 6 (US4 P4)**: Requires Phase 3 (needs working app to containerize); T024 GitHub Actions requires T021 Dockerfile
- **Phase 7 (Polish)**: Requires all user story phases complete

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no story dependencies
- **US2 (P2)**: After US1 — extends IngestionService and routes
- **US3 (P3)**: After US1 — hardens repository behavior already implemented
- **US4 (P4)**: After US1 — containerizes the working service (T021–T022 can start earlier; T023–T024 need working app)

### Within Each Phase

- Models and schemas within a story ([P] marked) can run in parallel
- Services depend on models
- Routes depend on services
- App entrypoint depends on routes

### Parallel Opportunities

**Phase 1**: T003 and T004 can run alongside T002.

**Phase 2**: T008 can run in parallel with T006–T007.

**Phase 3**: T010 and T011 can run in parallel (different files).

**Phase 6**: T021 and T022 can run in parallel (different files).

**Phase 7**: T025, T026, T027 can all run in parallel (different files).

---

## Parallel Example: Phase 3 (US1)

```text
# These two tasks have no dependencies on each other — launch together:
Task: "T010 - Implement nomnom/models/submission.py"
Task: "T011 - Implement nomnom/schemas/ingest.py"

# Then sequentially:
Task: "T012 - Implement nomnom/services/ingestion_service.py"
Task: "T013 - Implement nomnom/api/routes.py"
Task: "T014 - Implement nomnom/main.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational — CRITICAL, blocks everything
3. Complete Phase 3: User Story 1 (T010–T014)
4. **STOP and VALIDATE**: `curl` test against running server, check SQLite data
5. Proceed to Phase 4 (YouTube) only after US1 is confirmed working

### Incremental Delivery

1. Setup + Foundational → DB and repo layer ready
2. US1 (P1) → Working ingest endpoint, standard content types → **deploy and use**
3. US2 (P2) → YouTube enrichment added → richer archive
4. US3 (P3) → Duplicate handling hardened → cleaner data
5. US4 (P4) → Containerized → homelab deployment
6. Polish → Logging + docs finalized

---

## Notes

- [P] tasks touch different files and have no dependency on each other within the same phase
- Commit after each phase checkpoint at minimum
- YouTube enrichment (US2) is async — endpoint response time is not affected
- `ingested_at` preservation (US3) is the SQL upsert clause — verify it manually before moving on
- `docker-compose.yml` uses `127.0.0.1:3002:3002` binding intentionally — userscript targets `localhost` and this keeps the port off the LAN interface
