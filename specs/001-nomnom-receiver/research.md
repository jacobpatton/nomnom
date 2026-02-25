# Research: NomNom Knowledge Receiver

**Feature**: 001-nomnom-receiver | **Date**: 2026-02-24

---

## Decision 1: Web Framework — FastAPI

**Decision**: FastAPI

**Rationale**: FastAPI is the clear choice for this single-endpoint receiver. It provides async request handling out of the box (important for non-blocking YouTube enrichment), built-in CORS middleware, automatic JSON validation via Pydantic, and runs on Uvicorn for production-grade performance. Flask lacks native async support and would require additional libraries. Bare Starlette is an option but FastAPI adds negligible overhead while eliminating boilerplate.

**Alternatives considered**:

- Flask: Synchronous by default; async support via extensions is awkward. Rejected.
- Starlette (bare): Lower-level; FastAPI is a thin wrapper that adds value at no real cost. Rejected.

---

## Decision 2: YouTube Content Extraction — yt-dlp + youtube-transcript-api

**Decision**: `yt-dlp` for video metadata (title, description, uploader, duration); `youtube-transcript-api` for clean transcript text.

**Rationale**: yt-dlp's Python API (`YoutubeDL` class) is powerful but extracting transcript _text_ requires downloading and parsing subtitle files (VTT/SRT format) with no built-in text accessor. `youtube-transcript-api` gives clean, structured transcript text directly in Python without file I/O or ffmpeg. Using both libraries gives complete coverage: rich metadata from yt-dlp, clean transcript text from `youtube-transcript-api`.

Both are called with `skip_download=True` / no video download — only metadata is fetched.

**yt-dlp key options**:

```python
ydl_opts = {
    'skip_download': True,
    'quiet': True,
    'no_warnings': True,
}
info = ydl.extract_info(url, download=False)
# info keys: title, description, uploader, duration, upload_date, view_count
```

**youtube-transcript-api key usage**:

```python
from youtube_transcript_api import YouTubeTranscriptApi
transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
text = ' '.join([t['text'] for t in transcript])
```

**Docker note**: No ffmpeg required with this approach. Both libraries are pure-Python installable via pip.

**Alternatives considered**:

- yt-dlp only for transcripts: Requires downloading/parsing VTT files; more complexity, ffmpeg dependency. Rejected for v1.
- whisper (speech-to-text): Too heavyweight; only needed if no captions exist. Out of scope for v1.

---

## Decision 3: SQLite Usage — WAL Mode + Per-Thread Connections + Repository Pattern

**Decision**: WAL journal mode, one connection per request thread, Repository pattern for data access, versioned SQL migration scripts.

**Rationale**:

- **WAL mode** enables concurrent reads while writes are in progress — essential for a web service where reads and writes can overlap.
- **Per-thread connections** (`sqlite3.connect()` called per request, not shared) avoid SQLite's thread-safety limitations cleanly. FastAPI's async context makes this manageable.
- **Repository pattern** cleanly separates data access from business logic, making services testable with mock repositories.
- **Versioned SQL scripts** (`001_init.sql`, `002_*.sql`) are sufficient for a single-developer project. Alembic adds complexity not justified for v1.

**Thread safety approach**: Each request handler acquires a fresh connection, enables WAL + timeout, executes, and closes. No connection pool library needed for SQLite at this scale.

**Alternatives considered**:

- SQLAlchemy ORM: Heavyweight for SQLite + simple schema. Rejected.
- Alembic migrations: Appropriate if team grows. Deferred to future.
- Shared connection with `check_same_thread=False`: Requires manual write serialization. Rejected.

---

## Decision 4: Docker Image — Multi-Stage Build on python:3.12-slim → GHCR

**Decision**: Multi-stage Dockerfile (`python:3.12-slim`), GitHub Actions for automated GHCR publish, Docker Compose with named volume.

**Key choices**:

- Base image: `python:3.12-slim` (~130MB final image). Alpine rejected — musl libc causes C-extension recompilation issues with yt-dlp.
- Multi-stage: `builder` stage installs deps; `runtime` stage copies only the virtualenv. Keeps final image lean.
- GHCR auth: `GITHUB_TOKEN` with `packages: write` — no manual secrets needed.
- Image name: `ghcr.io/<owner>/nomnom-receiver` (lowercase).
- GitHub Actions: Build and push on `main` branch push; skip push on PRs. Use `docker/metadata-action` for semantic tags (SHA, `latest`).
- Docker Compose: Named volume (`nomnom_data:/data`) for SQLite persistence. Port binding `127.0.0.1:3002:3002` for local security. `restart: unless-stopped`. Healthcheck on `/health` endpoint.
- Run as non-root user (UID 1000) in container.

**Alternatives considered**:

- Alpine base: Smaller but causes build failures with native Python extensions. Rejected.
- Bind mount for SQLite: Works but named volumes have better Docker tooling. Named volume chosen.
