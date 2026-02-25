# Research: GitHub Repository Support

**Feature**: `003-github-repo-support`
**Date**: 2026-02-24
**Status**: Complete — no unresolved unknowns

---

## Decision 1: README Fetch URL Pattern

**Decision**: Use `https://raw.githubusercontent.com/<owner>/<repo>/HEAD/README.md`

**Rationale**: The `/HEAD/` ref resolves to the default branch without requiring a separate API call to discover the branch name. Works for both `main` and `master` default branches. No authentication required for public repos. A 404 response (repo has no README, or uses a different filename) is treated as an empty README per clarification Q3.

**Alternatives considered**:

- Fetch via GitHub REST API (`/repos/<owner>/<repo>/readme`) — adds JSON parsing, unauthenticated rate limit is 60 req/hr per IP, more complex failure modes. Rejected: added complexity with no benefit for MVP.
- Detect default branch first, then fetch — two network calls instead of one. Rejected: unnecessary.
- Try multiple filenames (README.rst, README.txt, etc.) — adds complexity. Rejected: README.md covers the overwhelming majority of repos; others store empty.

---

## Decision 2: GitHub URL Validation & Normalization

**Decision**: A URL is treated as a GitHub repository URL if and only if it has **at least 2 non-empty path segments** after `github.com`. The canonical URL is `https://github.com/<segment[0]>/<segment[1]>` — all additional path segments and fragments are stripped.

**Rationale**: GitHub's own reserved top-level paths (`settings`, `notifications`, `dashboard`, `explore`, etc.) are all single-segment. Two-path-segment URLs like `github.com/owner/repo` unambiguously identify a repository in practice. GitHub does not allow usernames that conflict with its reserved paths.

**Known two-segment GitHub system paths to blocklist** (defensive, low probability of user visits):

- `github.com/orgs/<name>` → org page, not a repo
- `github.com/users/<name>` → user page, not a repo
- `github.com/features/<name>` → marketing pages
- `github.com/marketplace/<name>` → marketplace listings

**Alternatives considered**:

- Call GitHub API to verify repo exists — adds latency and a rate-limited network call. Rejected: overkill for MVP.
- Only support `github.com/<owner>/<repo>` exact pattern — same result with simpler logic. Adopted as the primary rule; blocklist is supplementary.

---

## Decision 3: Database Storage Strategy

**Decision**: Store GitHub repository records in the **existing `submissions` table** using `content_type = "github_repo"`. No new table required.

**Field mapping**:
| submissions column | GitHub repo value |
|-|-|
| `url` | Canonical repo URL (unique key) |
| `domain` | `"github.com"` |
| `title` | `"<owner>/<repo>"` |
| `content_markdown` | README.md content (may be empty) |
| `content_type` | `"github_repo"` |
| `metadata` | `{"owner": "<owner>", "repo": "<repo>"}` (JSON) |
| `enrichment_status` | `"none"` (README fetched synchronously) |

**Rationale**: The `submissions` table already has all necessary columns. Reusing it avoids schema migration complexity and keeps query patterns consistent.

**Alternatives considered**:

- Separate `github_repos` table — cleaner schema isolation but requires a new migration and complicates cross-content queries. Rejected: no query requirement currently justifies it.

---

## Decision 4: Duplicate Handling (Insert vs Update)

**Decision**: Use a **check-then-insert** approach: if the canonical URL already exists in `submissions`, return a skip response without updating. Do not use the existing `upsert()` method which overwrites README content.

**Rationale**: Per clarification Q2, revisiting a saved repo should not overwrite the existing record. Existing `SubmissionRepository.upsert()` performs an `INSERT OR REPLACE`, which would clobber the stored README. A pre-existence check before insertion preserves the original record.

**Alternatives considered**:

- `INSERT OR IGNORE` — achieves skip behavior at DB level, simpler. Could be used. Chosen instead: explicit check in the service layer to return meaningful status to the caller.
- `upsert()` with update flag — would require modifying the existing method signature. Rejected: more invasive change.

---

## Decision 5: Integration Point in Existing Code

**Decision**: Add a `GithubService` class in `nomnom/services/github_service.py`. Modify `IngestionService.ingest()` to detect `content_type == "github_repo"` (or detect from domain) and delegate to `GithubService` before the generic persistence path.

**Rationale**: Mirrors the existing YouTube enrichment pattern. Keeps content-type-specific logic isolated and independently testable.
