# Tasks: GitHub Repository Support

**Input**: Design documents from `/specs/003-github-repo-support/`
**Prerequisites**: plan.md ✓, spec.md ✓, data-model.md ✓, contracts/ingest-api.md ✓

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Single project: source in `nomnom/`, tests in `tests/`

---

## Phase 1: Setup

**Purpose**: Verify httpx dependency is available for async README fetches

- [x] T001 Verify `httpx` is listed in requirements/dependencies (check `requirements.txt` or `pyproject.toml`); add it if missing

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Repository helper methods required by all user stories before any story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 Add `exists_by_url(url: str) -> bool` method to `nomnom/repositories/submission_repository.py` — `SELECT 1 FROM submissions WHERE url = ? LIMIT 1`
- [x] T003 Add `insert_github_repo(url, owner, repo, readme) -> None` method to `nomnom/repositories/submission_repository.py` — INSERT into submissions with `content_type="github_repo"`, `domain="github.com"`, `title="<owner>/<repo>"`, `metadata={"owner": ..., "repo": ...}`, `enrichment_status="none"`

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Save GitHub Repository (Priority: P1) 🎯 MVP

**Goal**: Accept a bare repo URL (e.g., `https://github.com/owner/repo`), fetch its README via `raw.githubusercontent.com`, and store the record with all required fields.

**Independent Test**: `POST /` with `{"url": "https://github.com/owner/repo", "domain": "github.com"}` → response `{"status": "saved", ...}` and record exists in DB with correct `url`, `title`, `content_type`, `metadata`, and `content_markdown`.

### Implementation for User Story 1

- [x] T004 [US1] Create `nomnom/services/github_service.py` with `GithubService` class skeleton: define `BLOCKED_PREFIXES` set (`orgs`, `users`, `features`, `marketplace`, `settings`, `notifications`, `dashboard`, `explore`, `pulls`, `issues`, `sponsors`) and stub signatures for `normalize_url` and `fetch_readme`
- [x] T005 [US1] Implement `GithubService.normalize_url(url: str) -> tuple[str, str, str] | None` in `nomnom/services/github_service.py`: parse URL, verify host is `github.com`, split path segments, reject if fewer than 2 segments or first segment is in `BLOCKED_PREFIXES`, strip fragment, return `(canonical_url, owner, repo)` where `canonical_url = https://github.com/<seg0>/<seg1>`
- [x] T006 [US1] Implement `async def GithubService.fetch_readme(owner: str, repo: str) -> str` in `nomnom/services/github_service.py`: async GET `https://raw.githubusercontent.com/<owner>/<repo>/HEAD/README.md` via httpx with a short timeout; return response text on HTTP 200, empty string on any other status or exception
- [x] T007 [US1] Add `_ingest_github(submission) -> IngestResponse` method to `nomnom/services/ingestion_service.py` and wire it into `ingest()`: if `submission.domain == "github.com"`, call `github_service.normalize_url(submission.url)`; if None return skipped; if `repo.exists_by_url(canonical_url)` return skipped; else fetch README and call `repo.insert_github_repo(...)`, return saved
- [x] T008 [US1] Write unit tests in `tests/unit/test_github_service.py` — `normalize_url` with bare repo URL returns correct `(canonical_url, owner, repo)` tuple; `fetch_readme` with mocked httpx 200 returns content; `fetch_readme` with mocked httpx 404 returns `""`; `fetch_readme` with mocked httpx timeout returns `""`
- [x] T014 [P] [US1] Add unit tests to `tests/unit/test_github_service.py` — `normalize_url` with profile URL `https://github.com/owner` (1 segment) returns `None`; `normalize_url` with `https://github.com/orgs/myorg/teams` (blocked prefix) returns `None`; `normalize_url` with `https://github.com/settings/profile` returns `None`
- [x] T009 [US1] Write integration tests in `tests/integration/test_github_ingest.py` — (1) POST `{"url": "https://github.com/owner/repo", "domain": "github.com"}` (README fetch mocked) → status `"saved"`, one record in DB with `url="https://github.com/owner/repo"`, `title="owner/repo"`, `content_type="github_repo"`, `metadata={"owner":"owner","repo":"repo"}`; (2) POST the same URL a second time → status `"skipped"`, DB record count unchanged
- [x] T015 [P] [US1] Add integration tests to `tests/integration/test_github_ingest.py` — POST `{"url": "https://github.com/owner", "domain": "github.com"}` → status `"skipped"`, no record created; POST `{"url": "https://github.com/orgs/myorg", "domain": "github.com"}` → status `"skipped"`, no record created

**Checkpoint**: US1 complete — MVP deliverable. Verify with quickstart if available.

---

## Phase 4: User Story 2 - Normalize Deep Links to Repo Homepage (Priority: P2)

**Goal**: Any GitHub URL pointing to a file, directory, commit, or issue within a repo is treated as a visit to the canonical `github.com/<owner>/<repo>` homepage.

**Independent Test**: `POST /` with `{"url": "https://github.com/owner/repo/blob/main/README.md", "domain": "github.com"}` → response `{"status": "saved", ...}` and stored record has `url="https://github.com/owner/repo"` (sub-path stripped).

### Implementation for User Story 2

- [x] T010 [P] [US2] Add unit tests to `tests/unit/test_github_service.py` — `normalize_url` with `https://github.com/owner/repo/blob/main/file.py` returns `("https://github.com/owner/repo", "owner", "repo")`; `normalize_url` with `https://github.com/owner/repo/issues/42` returns correct tuple; `normalize_url` with `https://github.com/owner/repo/tree/feature-branch` returns correct tuple
- [x] T011 [P] [US2] Add integration tests to `tests/integration/test_github_ingest.py` — POST deep link URL `https://github.com/owner/repo/blob/main/somefile.py` → status `"saved"`, stored `url` equals `"https://github.com/owner/repo"` (sub-path stripped); POST issue URL `https://github.com/owner/repo/issues/42` → same canonical URL stored

**Checkpoint**: US2 complete — deep links normalized correctly alongside US1 behavior.

---

## Phase 5: User Story 3 - Deduplicate Anchor Links on Repo Homepage (Priority: P3)

**Goal**: A URL with a fragment (e.g., `https://github.com/owner/repo#readme`) is treated as identical to `https://github.com/owner/repo`, preventing duplicate records.

**Independent Test**: First POST `https://github.com/owner/repo` → saved. Then POST `https://github.com/owner/repo#readme` → response `{"status": "skipped", ...}` and only one record exists in DB.

### Implementation for User Story 3

- [x] T012 [P] [US3] Add unit tests to `tests/unit/test_github_service.py` — `normalize_url` with `https://github.com/owner/repo#readme` returns `("https://github.com/owner/repo", "owner", "repo")` (fragment stripped); `normalize_url` with `https://github.com/owner/repo#installation` returns same canonical URL
- [x] T013 [P] [US3] Add integration tests to `tests/integration/test_github_ingest.py` — POST `https://github.com/owner/repo` → saved; then POST `https://github.com/owner/repo#readme` → status `"skipped"`, DB record count for this repo is still 1; POST `https://github.com/owner/repo#installation` fresh (no prior record) → status `"saved"`, stored URL has no fragment

**Checkpoint**: US3 complete — all three user stories fully functional and tested independently.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: README failure scenarios and full suite validation

- [x] T016 Add integration test to `tests/integration/test_github_ingest.py` — POST valid repo URL with README fetch mocked to return 404 → status `"saved"`, record created with `content_markdown=""` (empty string)
- [x] T017 Run full test suite (`pytest tests/`) and confirm all tests pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Stories (Phases 3–5)**: All depend on Foundational completion
  - US1 must complete before US2/US3 (integration tests share the same test file and DB setup)
  - US2 and US3 can proceed after US1 is complete
- **Polish (Phase 6)**: Depends on all user stories being complete

### Within Each User Story

- T005 then T006 sequentially (same file: `github_service.py`)
- T007 depends on T005 and T006
- T008 depends on T002, T003, T004, T005, T006
- T014 [P] can run alongside T008 (both test normalize_url behavior, different test cases — same file, so sequence within that file)
- T009 depends on T008; T015 [P] can run alongside T009 (different scenarios, both in integration test file — sequence within file)
- Tests within US2/US3 phases are parallel across files (T010‖T011, T012‖T013)

### Parallel Opportunities

- T002 then T003 sequentially (same file: `submission_repository.py`)
- T005 then T006 sequentially (same file: `github_service.py`)
- T010 and T011 are parallel within US2 (different test files)
- T012 and T013 are parallel within US3 (different test files)
- T016 and T017 are sequential (run suite after adding test)

---

## Parallel Example: User Story 2

```bash
# After US1 is complete — T010 and T011 can run in parallel (different files):
Task: "Add deep link unit tests to tests/unit/test_github_service.py"   # T010
Task: "Add deep link integration tests to tests/integration/test_github_ingest.py"  # T011
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: POST a bare repo URL and inspect the DB record
5. Deploy if ready — this delivers the core value

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready
2. Phase 3 → MVP: bare repo URL captured ✓
3. Phase 4 → US2: deep links normalized ✓
4. Phase 5 → US3: anchor fragments deduplicated ✓
5. Phase 6 → Polish: edge cases covered ✓

---

## Notes

- No schema migrations required — existing `submissions` table accommodates all fields
- `normalize_url()` handles US1, US2, and US3 URL variants in a single function; phases 4 and 5 add test coverage for behaviors already designed into the function
- README fetch is always fail-silent — never surface errors to the userscript
- `content_type = "github_repo"` is the discriminator; no existing records or behavior is changed
- [P] tasks can run in parallel; edit the same file sequentially to avoid conflicts
