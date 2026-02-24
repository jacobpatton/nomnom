# Feature Specification: NomNom Knowledge Receiver (Server-Side)

**Feature Branch**: `001-nomnom-receiver`
**Created**: 2026-02-24
**Status**: Draft
**Input**: User description: "build a robust, extensible Universal Knowledge Ingestor system server-side component, packaged for Docker Compose deployment"

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Passive Content Capture (Priority: P1)

As a knowledge worker browsing the web with the NomNom userscript installed, I want visited pages to be automatically saved to a persistent local store without any manual action, so I can build a searchable archive of everything I've read.

**Why this priority**: This is the core value proposition — zero-friction, automatic capture. Without this working, nothing else matters.

**Independent Test**: Can be fully tested by visiting a supported web page (Reddit thread, GitHub repo, or article) in a browser with the userscript active and confirming the page's title, URL, and content appear in the stored data.

**Acceptance Scenarios**:

1. **Given** the receiver service is running, **When** the userscript submits a page's content as structured data, **Then** the receiver stores the content and responds with a success status.
2. **Given** a submission contains a title, URL, markdown content, domain, and metadata, **Then** all fields are stored and retrievable.
3. **Given** the receiver receives malformed or incomplete submission data, **Then** it responds with an appropriate error status and does not store partial records.

---

### User Story 2 - YouTube Transcript Enrichment (Priority: P2)

As a knowledge worker visiting YouTube videos, I want the system to automatically fetch the video transcript server-side, so that the video's spoken content is captured and archived even though the browser cannot extract it directly.

**Why this priority**: YouTube is a primary content type. The userscript sends only a placeholder for YouTube videos — the receiver must enrich it to make the archive useful.

**Independent Test**: Can be fully tested by submitting a YouTube video URL to the receiver and confirming the stored entry contains the fetched transcript text rather than the placeholder.

**Acceptance Scenarios**:

1. **Given** the receiver processes a submission with `type: "youtube_video"` and a video ID, **When** the submission is accepted, **Then** the system fetches the video transcript and replaces the placeholder content with the actual transcript before saving.
2. **Given** a YouTube video has no available transcript (captions disabled), **Then** the system stores the entry with a clear indicator that transcript extraction was attempted but unavailable.
3. **Given** the transcript fetch fails due to network error or rate limiting, **Then** the submission is still stored with the placeholder content and the failure reason is recorded.

---

### User Story 3 - Duplicate URL Handling (Priority: P3)

As a knowledge worker who revisits pages, I want the system to handle resubmissions of the same URL predictably, so I don't end up with redundant entries cluttering my archive.

**Why this priority**: As browsing patterns repeat, the same URLs will be submitted multiple times. Without a defined policy, the archive becomes noisy and unreliable.

**Independent Test**: Can be fully tested by submitting the same URL twice and confirming only one record exists (with an updated timestamp).

**Acceptance Scenarios**:

1. **Given** a URL has already been stored, **When** the same URL is submitted again, **Then** the system updates the existing record with the new content and timestamp rather than creating a duplicate.
2. **Given** a URL is updated, **Then** the original ingestion timestamp is preserved alongside the updated timestamp.

---

### User Story 4 - Containerized Deployment (Priority: P4)

As a developer setting up NomNom on a home server or workstation, I want to launch the entire receiver service with a single command, so I can get it running quickly without managing dependencies manually.

**Why this priority**: Without reliable packaging, the tool is difficult to adopt. Docker Compose deployment is the stated delivery format for this feature.

**Independent Test**: Can be fully tested by cloning the repository on a clean machine with Docker installed, running the compose command, and successfully capturing a page from the browser.

**Acceptance Scenarios**:

1. **Given** a machine with Docker installed, **When** the compose command is run, **Then** the receiver service starts and is reachable on the expected port within 30 seconds.
2. **Given** the container is stopped and restarted, **Then** all previously stored data is still accessible (data persists via a mounted volume).
3. **Given** no prior configuration, **Then** the service starts with sensible defaults and no manual setup is required beyond running the compose command.

---

### Edge Cases

- What happens when the receiver is offline while the userscript tries to submit? (Browser shows error toast; no client-side buffering — acceptable for v1.)
- How does the system handle very large content submissions (e.g., Reddit threads with thousands of comments)?
- What happens when a YouTube video ID is invalid or the video has been deleted?
- How does the system handle concurrent submissions from multiple browser tabs simultaneously?
- What if the data storage volume fills up — does the service fail gracefully with a clear error?

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The receiver MUST accept structured content submissions from the NomNom userscript over the local network.
- **FR-002**: Each submission MUST include the following fields: page URL, domain, title, markdown content, and a metadata object containing at minimum a content type identifier.
- **FR-003**: The receiver MUST persist all accepted submissions to durable storage that survives service restarts.
- **FR-004**: The receiver MUST accept cross-origin requests from browser extensions running on any domain.
- **FR-005**: The receiver MUST respond to each submission with a clear success or failure status that the userscript can interpret.
- **FR-006**: The receiver MUST respond to successful submissions within 2 seconds for standard content types (non-YouTube).
- **FR-007**: When a submission is identified as a YouTube video, the receiver MUST attempt to fetch the video's transcript server-side and store the fetched transcript content rather than the placeholder.
- **FR-008**: If transcript enrichment fails for a YouTube video, the receiver MUST still store the submission with the original placeholder content and record the failure reason.
- **FR-009**: The receiver MUST update an existing record when the same URL is submitted again, rather than creating a duplicate entry.
- **FR-010**: The receiver MUST be fully operable as a containerized service launched via a container orchestration configuration file.
- **FR-011**: Stored data MUST be persisted to a host-mounted volume so it survives container recreation.
- **FR-012**: The service MUST start successfully with no configuration beyond what is provided in the compose file.
- **FR-013**: [NEEDS CLARIFICATION: Should the receiver expose a read interface (e.g., a simple web UI or query endpoint) to browse stored entries, or is it purely a write-only ingest service for v1?]

### Key Entities

- **Submission**: A single captured web page. Contains: URL (unique identifier), domain, title, markdown content, content type, metadata (flexible store for type-specific fields such as subreddit name, video ID, author, comment count), ingestion timestamp, last-updated timestamp, and enrichment status.
- **Enrichment Job**: A server-side processing task triggered by certain content types (currently YouTube). Contains: associated submission URL, status (pending / complete / failed), failure reason if applicable, and completion timestamp.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: A page visited in the browser with the userscript installed is stored in the receiver's archive within 10 seconds of the page loading, with no user action required.
- **SC-002**: 100% of submissions that receive a success response are retrievable from storage without data loss.
- **SC-003**: YouTube video entries stored in the archive contain the actual transcript text in at least 90% of cases where the video has captions available.
- **SC-004**: Visiting the same URL 10 times results in exactly 1 stored record (with an updated timestamp), not 10 records.
- **SC-005**: The service can be brought online on a new machine with Docker installed in under 5 minutes from first clone to first successful capture.
- **SC-006**: The archive retains all entries across container restarts with zero data loss.
- **SC-007**: The receiver handles at least 10 simultaneous submissions without dropping or corrupting any entries.

## Assumptions

- The userscript POSTs JSON to `http://localhost:3002` (root endpoint). The receiver listens on port 3002 by default.
- The submitted JSON payload follows the structure defined in the existing userscript: `{ url, domain, title, content_markdown, metadata: { type, ...extra } }`.
- Content types currently in scope: `reddit_thread`, `github`, `youtube_video`, `generic_article`, `placeholder`.
- YouTube transcript fetching will be performed server-side using an appropriate tool (selection deferred to planning phase).
- The receiver is a single-user, local-network tool — no multi-tenancy, user accounts, or rate limiting required for v1.
- No authentication is required for v1, as the service runs on a trusted local network only.
- A read/browse interface for stored content is out of scope for this feature unless clarified (see FR-013).
- The container orchestration file will use Docker Compose v2 syntax.
- Storage volume path will be configurable via environment variable with a sensible default.
