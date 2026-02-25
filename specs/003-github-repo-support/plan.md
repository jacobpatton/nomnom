# Implementation Plan: GitHub Repository Support

**Branch**: `003-github-repo-support` | **Date**: 2026-02-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/003-github-repo-support/spec.md`

## Summary

Add GitHub repository support to the Nomnom receiver. When a user visits any GitHub repository URL (homepage, deep link, or anchor variant), the userscript submits the URL to the existing `POST /` endpoint. The receiver normalizes the URL to the canonical `github.com/<owner>/<repo>` form, checks for an existing record, fetches the README via `raw.githubusercontent.com`, and stores the result using the existing `submissions` table with `content_type = "github_repo"`. No new database tables or API endpoints are required.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, Pydantic v2, `httpx` (for async HTTP — already available or trivially added), sqlite3 (stdlib)
**Storage**: SQLite WAL mode — existing `submissions` table, no migration needed
**Testing**: pytest (unit/ and integration/ directories)
**Target Platform**: Linux server (existing Docker deployment)
**Project Type**: Web service (FastAPI receiver)
**Performance Goals**: README fetch adds one outbound HTTP call per new submission; acceptable for a personal-use tool
**Constraints**: No GitHub API token; unauthenticated raw content fetch only; fail-silent on fetch errors
**Scale/Scope**: Personal use; no concurrency or rate-limit concerns at scale

## Constitution Check

Constitution template is unfilled — no project-specific gates defined. Standard practices apply: keep changes minimal, test-first, no new abstractions beyond what's needed.

**Post-design re-check**: No violations. Feature is additive; no existing behavior changed except `IngestionService.ingest()` gaining a new branch.

## Project Structure

### Documentation (this feature)

```text
specs/003-github-repo-support/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── ingest-api.md    # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
nomnom/
├── services/
│   ├── ingestion_service.py     # MODIFY: add GitHub branch
│   └── github_service.py        # NEW: URL normalization + README fetch
└── repositories/
    └── submission_repository.py # MODIFY: add exists_by_url() method

tests/
├── unit/
│   └── test_github_service.py   # NEW: normalization + fetch logic
└── integration/
    └── test_github_ingest.py    # NEW: end-to-end POST / with GitHub URLs
```

**Structure Decision**: Single project, Option 1. Two new files, two modified files. No new directories.

## Phase 0: Research

**Status**: Complete. See [research.md](./research.md).

Key decisions:

- README fetched via `https://raw.githubusercontent.com/<owner>/<repo>/HEAD/README.md` (no auth, fail-silent)
- URL validated by requiring ≥2 path segments; system paths blocklisted
- No schema migration; use existing `submissions` table with `content_type = "github_repo"`
- Skip-not-update on duplicate canonical URLs

## Phase 1: Design & Contracts

**Status**: Complete.

### Data Model

See [data-model.md](./data-model.md).

No new tables. Existing `submissions` table accommodates all fields via column mapping:

- `url` → canonical repo URL (unique key)
- `content_type` → `"github_repo"`
- `content_markdown` → README content
- `metadata` → `{"owner": "...", "repo": "..."}`
- `enrichment_status` → `"none"`

### API Contract

See [contracts/ingest-api.md](./contracts/ingest-api.md).

`POST /` endpoint is unchanged. GitHub handling is triggered when `domain == "github.com"`. Response uses existing `status`/`message` shape with `"skipped"` for non-repo URLs and duplicate submissions.

### Implementation Design

#### `nomnom/services/github_service.py` (new)

```
GithubService
  BLOCKED_PREFIXES = {orgs, users, features, marketplace, settings,
                      notifications, dashboard, explore, pulls, issues, sponsors}

  normalize_url(url: str) -> tuple[str, str, str] | None
    # Returns (canonical_url, owner, repo) or None if not a valid repo URL
    # Parse URL, check domain, validate 2+ path segments, blocklist check
    # Return https://github.com/<owner>/<repo>

  async def fetch_readme(owner: str, repo: str) -> str
    # async GET https://raw.githubusercontent.com/<owner>/<repo>/HEAD/README.md
    # Return content on 200, empty string on any error (404, timeout, rate-limit)
```

#### `nomnom/repositories/submission_repository.py` (modify)

Add one method:

```
exists_by_url(url: str) -> bool
  # SELECT 1 FROM submissions WHERE url = ? LIMIT 1
```

#### `nomnom/services/ingestion_service.py` (modify)

In `ingest()`, before the generic persistence path, add:

```
if submission.domain == "github.com":
    result = self._ingest_github(submission)
    return result   # early return; skip generic path

_ingest_github(submission) -> IngestResponse:
    parsed = github_service.normalize_url(submission.url)
    if parsed is None:
        return IngestResponse(status="skipped", message="Not a GitHub repository URL.")
    canonical_url, owner, repo = parsed
    if self.repo.exists_by_url(canonical_url):
        return IngestResponse(status="skipped", message=f"GitHub repository {owner}/{repo} already saved.")
    readme = github_service.fetch_readme(owner, repo)
    self.repo.insert_github_repo(canonical_url, owner, repo, readme)
    return IngestResponse(status="saved", message=f"GitHub repository {owner}/{repo} saved.")
```

#### `nomnom/repositories/submission_repository.py` (modify, cont.)

Add:

```
insert_github_repo(url, owner, repo, readme) -> None
  # INSERT INTO submissions (url, domain, title, content_markdown, content_type,
  #   metadata, enrichment_status, ingested_at, updated_at)
  # VALUES (?, 'github.com', ?, ?, 'github_repo', ?, 'none', now, now)
```

### Test Plan

**Unit tests** (`tests/unit/test_github_service.py`):

- `normalize_url` with bare repo URL → correct tuple
- `normalize_url` with deep link → strips sub-path
- `normalize_url` with anchor fragment → strips fragment
- `normalize_url` with profile URL (1 segment) → None
- `normalize_url` with blocked prefix (`orgs/foo`) → None
- `fetch_readme` with mock 200 → returns content
- `fetch_readme` with mock 404 → returns `""`
- `fetch_readme` with mock timeout → returns `""`

**Integration tests** (`tests/integration/test_github_ingest.py`):

- POST bare repo URL → 200, status `"saved"`, record in DB with correct fields
- POST deep link URL → 200, status `"saved"`, canonical URL stored
- POST anchor URL → 200, status `"saved"`, canonical URL stored (no fragment)
- POST duplicate URL → 200, status `"skipped"`, record count unchanged
- POST profile URL → 200, status `"skipped"`, no record created
- POST with README fetch mocked to 404 → saved with empty `content_markdown`
