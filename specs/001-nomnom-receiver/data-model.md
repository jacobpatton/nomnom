# Data Model: NomNom Knowledge Receiver

**Feature**: 001-nomnom-receiver | **Date**: 2026-02-24

---

## Entities

### Submission

Represents a single captured web page or video. The URL is the unique natural key — re-submitting the same URL performs an upsert (update, not insert).

| Field               | Type     | Constraints              | Description                                                                          |
| ------------------- | -------- | ------------------------ | ------------------------------------------------------------------------------------ |
| `id`                | INTEGER  | PK, AUTOINCREMENT        | Internal row ID                                                                      |
| `url`               | TEXT     | NOT NULL, UNIQUE         | Full page URL (natural key for upserts)                                              |
| `domain`            | TEXT     | NOT NULL                 | Hostname (e.g., `reddit.com`)                                                        |
| `title`             | TEXT     | NULLABLE                 | Page or video title                                                                  |
| `content_markdown`  | TEXT     | NULLABLE                 | Full content in Markdown format                                                      |
| `content_type`      | TEXT     | NOT NULL                 | One of: `reddit_thread`, `github`, `youtube_video`, `generic_article`, `placeholder` |
| `metadata`          | TEXT     | NULLABLE                 | JSON-serialized dict of type-specific fields                                         |
| `enrichment_status` | TEXT     | NOT NULL, DEFAULT `none` | One of: `none`, `pending`, `complete`, `failed`                                      |
| `enrichment_error`  | TEXT     | NULLABLE                 | Failure message if enrichment failed                                                 |
| `ingested_at`       | DATETIME | NOT NULL, DEFAULT NOW    | Timestamp of first capture                                                           |
| `updated_at`        | DATETIME | NOT NULL, DEFAULT NOW    | Timestamp of most recent update                                                      |

**Metadata field examples by content type**:

- `reddit_thread`: `{ "subreddit": "r/Python", "author": "user123", "upvote_ratio": "0.97", "comment_count": 42, "comments": [...] }`
- `youtube_video`: `{ "video_id": "dQw4w9WgXcQ", "uploader": "Channel Name", "duration": 213, "upload_date": "20231015", "view_count": 1200000 }`
- `github`: `{ "repo": "/user/repo" }`
- `generic_article`: `{}`
- `placeholder`: `{ "error": "Extraction failed. URL preserved." }`

**State transitions for `enrichment_status`**:

```
none        → (standard content types; no enrichment needed)
pending     → complete   (YouTube: yt-dlp fetch succeeded)
pending     → failed     (YouTube: yt-dlp fetch failed)
```

---

### EnrichmentJob

Tracks the lifecycle of server-side content fetching for YouTube submissions. Created when a YouTube submission is received; updated when enrichment completes or fails.

| Field            | Type     | Constraints                    | Description                                |
| ---------------- | -------- | ------------------------------ | ------------------------------------------ |
| `id`             | INTEGER  | PK, AUTOINCREMENT              | Internal row ID                            |
| `submission_url` | TEXT     | NOT NULL, FK → submissions.url | Associated submission                      |
| `status`         | TEXT     | NOT NULL, DEFAULT `pending`    | One of: `pending`, `complete`, `failed`    |
| `failure_reason` | TEXT     | NULLABLE                       | Error message on failure                   |
| `created_at`     | DATETIME | NOT NULL, DEFAULT NOW          | When the job was created                   |
| `completed_at`   | DATETIME | NULLABLE                       | When the job finished (success or failure) |

---

## Validation Rules

- `url` must be non-empty and a valid absolute URL.
- `content_type` must be one of the five recognized values; unknown types are stored as `placeholder`.
- `metadata` is stored as a JSON string; the receiver validates it is a valid JSON object before storing.
- YouTube submissions may omit `title` and `content_markdown` in the incoming payload — these are populated by the enrichment process.
- Standard submissions (non-YouTube) that omit `title` or `content_markdown` are still accepted; missing fields stored as NULL.

---

## Migration Scripts

Versioned SQL files applied in order on service startup.

```
db/migrations/
└── 001_init.sql     # Creates submissions and enrichment_jobs tables; enables WAL mode
```

`001_init.sql`:

```sql
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS submissions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    url               TEXT    NOT NULL UNIQUE,
    domain            TEXT    NOT NULL,
    title             TEXT,
    content_markdown  TEXT,
    content_type      TEXT    NOT NULL,
    metadata          TEXT,
    enrichment_status TEXT    NOT NULL DEFAULT 'none',
    enrichment_error  TEXT,
    ingested_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS enrichment_jobs (
    id              INTEGER  PRIMARY KEY AUTOINCREMENT,
    submission_url  TEXT     NOT NULL REFERENCES submissions(url),
    status          TEXT     NOT NULL DEFAULT 'pending',
    failure_reason  TEXT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    DATETIME
);

CREATE INDEX IF NOT EXISTS idx_submissions_content_type ON submissions(content_type);
CREATE INDEX IF NOT EXISTS idx_enrichment_jobs_status   ON enrichment_jobs(status);
```
