# Feature Specification: GitHub Repository Support

**Feature Branch**: `001-github-repo-support`
**Created**: 2026-02-24
**Status**: Draft
**Input**: User description: "add support for Github. The userscript will send the repository URL, and the receiver should grab the github username, repo name, url, and README.md. If I visit a Github page, and it's _not_ the bare repo homepage (like a deep link to another file within the repo), receiver should save it as though I visited the repo homepage. That means it should also ignore anchor-links on the homepage (so it doesn't create needless duplicates in the db)."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Save GitHub Repository (Priority: P1)

When a user visits a GitHub repository homepage, the userscript sends the URL to the receiver, which extracts the repository's metadata (owner username, repo name, canonical URL, and README content) and stores it as a saved item.

**Why this priority**: This is the core functionality — capturing a GitHub repo visit and persisting meaningful metadata about it.

**Independent Test**: Submit a bare repo homepage URL (e.g., `https://github.com/owner/repo`) and verify all four fields are stored correctly.

**Acceptance Scenarios**:

1. **Given** a user visits `https://github.com/owner/repo`, **When** the userscript submits the URL to the receiver, **Then** the system stores the owner username, repo name, canonical URL, and README content as a single record.
2. **Given** a repository with a README, **When** the record is saved, **Then** the README content is captured and associated with the record.
3. **Given** a repository without a README, **When** the record is saved, **Then** the record is still created with the README field empty.

---

### User Story 2 - Normalize Deep Links to Repo Homepage (Priority: P2)

When a user visits any GitHub page within a repository (e.g., a specific file, directory, commit, or issue), the receiver recognizes it as a GitHub repo URL and saves it as if the user had visited the bare repository homepage.

**Why this priority**: Without this, deep links create fragmented or duplicate records for the same repo viewed from different entry points.

**Independent Test**: Submit a deep-link URL (e.g., `https://github.com/owner/repo/blob/main/README.md`) and verify the record saved matches what would be saved for `https://github.com/owner/repo`.

**Acceptance Scenarios**:

1. **Given** a URL like `https://github.com/owner/repo/blob/main/somefile.py`, **When** submitted to the receiver, **Then** the system saves the record using the canonical repo URL `https://github.com/owner/repo`.
2. **Given** a URL like `https://github.com/owner/repo/issues/42`, **When** submitted, **Then** the record is saved as the repo homepage.
3. **Given** a URL like `https://github.com/owner/repo/tree/feature-branch`, **When** submitted, **Then** the record is saved as the repo homepage.

---

### User Story 3 - Deduplicate Anchor Links on Repo Homepage (Priority: P3)

When a user visits the repo homepage with a URL fragment (e.g., `https://github.com/owner/repo#readme`), the system treats it as the same record as `https://github.com/owner/repo`, preventing duplicate entries.

**Why this priority**: Anchor fragments on the homepage do not represent different content; without deduplication, the same repo can accumulate multiple records.

**Independent Test**: Submit `https://github.com/owner/repo#readme` after `https://github.com/owner/repo` is already stored. Verify only one record exists for this repo.

**Acceptance Scenarios**:

1. **Given** `https://github.com/owner/repo` is already saved, **When** `https://github.com/owner/repo#readme` is submitted, **Then** no new record is created.
2. **Given** `https://github.com/owner/repo#installation` is submitted for the first time, **When** stored, **Then** the canonical URL without the fragment is used as the unique key.

---

### Edge Cases

- What happens when a GitHub URL belongs to a user profile or organization page (not a repo), e.g., `https://github.com/owner`? — The system should not attempt to save it as a repo record; the submission is ignored or rejected.
- What happens when the README is very large? — The system captures it as-is; no truncation is required.
- What happens if the README is inaccessible (e.g., private repo, network error)? — The record is still saved with the README field empty; no error is surfaced to the user.
- What happens when the same canonical repo URL is submitted twice? — The system deduplicates on the canonical URL; no duplicate record is created.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST accept a GitHub URL submitted by the userscript and identify whether it resolves to a GitHub repository.
- **FR-002**: System MUST extract the repository owner username and repository name from any submitted GitHub repo URL.
- **FR-003**: System MUST normalize any GitHub URL pointing within a repository (deep links, branch views, file views, issue pages, etc.) to the canonical bare repository URL before saving.
- **FR-004**: System MUST strip URL fragments (anchor links such as `#readme`) from GitHub repo URLs before deduplication and storage.
- **FR-005**: System MUST fetch the repository's README content server-side via the public raw content URL (no authentication required) and store it at the time of saving. If the fetch fails or the file does not exist, the README field is stored empty.
- **FR-006**: System MUST use the canonical repository URL as the unique key to prevent duplicate records.
- **FR-007**: System MUST ignore GitHub URLs that do not resolve to a repository (e.g., user profile pages, organization pages, GitHub root).
- **FR-008**: System MUST store at minimum: owner username, repository name, canonical URL, and README content for each saved repository.

### Key Entities

- **GitHub Repository Record**: Represents a saved GitHub repository. Attributes: owner username, repository name, canonical URL (unique key), README content (may be empty).

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Any GitHub repository URL variant (bare homepage, deep link, or anchor link) submitted by the userscript results in exactly one record stored per unique repository.
- **SC-002**: The stored record for a repository always contains the canonical homepage URL, regardless of the URL variant submitted.
- **SC-003**: README content is successfully captured for all publicly accessible repositories that have a README file.
- **SC-004**: Submitting the same repository URL (or any variant of it) multiple times does not create duplicate records in the database.
- **SC-005**: Non-repository GitHub URLs (user profiles, org pages) are silently ignored without creating records or returning errors to the userscript.

## Clarifications

### Session 2026-02-24

- Q: How should the README be fetched — by the userscript from the DOM, by the receiver via unauthenticated raw content URL, or by the receiver via the GitHub REST API? → A: Receiver fetches server-side via unauthenticated raw content URL (Option B).

## Assumptions

- The userscript detects that the current page is on `github.com` and sends the URL to the receiver; the receiver does not initiate browsing.
- README content is fetched by the receiver server-side via the public raw content URL (e.g., `raw.githubusercontent.com`), requiring no authentication.
- Only public repository READMEs are in scope; inaccessible READMEs result in an empty field without error.
- The existing receiver infrastructure is the target platform; no new services are required.
- "Bare repository homepage" means the URL pattern `https://github.com/<owner>/<repo>` with no additional path segments and no fragment.
