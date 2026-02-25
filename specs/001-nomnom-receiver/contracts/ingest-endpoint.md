# Contract: Ingest Endpoint

**Feature**: 001-nomnom-receiver | **Date**: 2026-02-24

This document defines the HTTP contract between the NomNom Tampermonkey userscript (client) and the NomNom receiver (server). This contract must not be broken without a corresponding update to the userscript.

---

## Endpoint

```
POST http://localhost:3002/
Content-Type: application/json
Origin: <any>
```

The receiver listens on port 3002 by default (configurable via `PORT` environment variable). The userscript targets the root path `/`.

---

## CORS

The receiver accepts cross-origin requests from any origin (`Access-Control-Allow-Origin: *`). This is required for Tampermonkey to successfully POST from browser extension context.

Preflight (`OPTIONS`) requests must be handled and return `200 OK`.

---

## Request Payloads

### Standard Content Types

Used for `reddit_thread`, `github`, `generic_article`, `placeholder`.

```json
{
  "url": "https://www.reddit.com/r/Python/comments/abc123/some_thread/",
  "domain": "www.reddit.com",
  "title": "Some thread title",
  "content_markdown": "# Heading\n\nBody text here...",
  "metadata": {
    "type": "reddit_thread",
    "subreddit": "r/Python",
    "author": "some_user",
    "upvote_ratio": "0.97",
    "comment_count": 42,
    "comments": [
      { "author": "user2", "score": "15", "body": "Great post", "depth": 0 }
    ]
  }
}
```

**Required fields**: `url`, `domain`, `metadata.type`
**Optional fields**: `title`, `content_markdown`, all other `metadata` fields

### YouTube Submissions

The userscript sends a minimal payload for YouTube. All content is fetched server-side.

```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "domain": "www.youtube.com",
  "title": "Rick Astley - Never Gonna Give You Up (Official Music Video) - YouTube",
  "content_markdown": "Processing on server...",
  "metadata": {
    "type": "youtube_video",
    "video_id": "dQw4w9WgXcQ",
    "note": "Server-side processing requested"
  }
}
```

The receiver ignores `title` and `content_markdown` for YouTube submissions and fetches authoritative content server-side. The `video_id` field in metadata is used as the primary YouTube identifier.

---

## Responses

### Success (Queued)

```
HTTP/1.1 200 OK
Content-Type: application/json

{ "status": "queued", "message": "Queued" }
```

The submission has been accepted and will be written to the database asynchronously. The userscript treats any `200` response as success and shows the success toast. Both `"ok"` and `"queued"` values for `status` are treated as success.

### Filtered (Skipped)

```
HTTP/1.1 200 OK
Content-Type: application/json

{ "status": "skipped", "message": "Filtered: Reddit non-post URL" }
```

The submission was intentionally ignored (e.g., a Reddit homepage or subreddit listing rather than a post). No record is stored. The userscript treats this as a success response.

### Validation Error

```
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{ "status": "error", "message": "Missing required field: url" }
```

### Server Error

```
HTTP/1.1 500 Internal Server Error
Content-Type: application/json

{ "status": "error", "message": "Internal server error" }
```

The userscript treats any non-`200` response as an error and shows the error toast.

---

## Health Check Endpoint

```
GET http://localhost:3002/health
```

Used by Docker Compose healthcheck. Returns `200 OK` when the service is ready.

```json
{ "status": "ok" }
```

---

## Behaviour Notes

- **Upsert semantics**: Submitting an existing URL updates the record rather than creating a duplicate. The `ingested_at` timestamp is preserved; `updated_at` is refreshed.
- **YouTube URL normalization**: Any YouTube URL submitted with a `video_id` in metadata is normalized to `https://www.youtube.com/watch?v={video_id}` before storage. URLs with timestamps (`&t=`), playlist params (`&list=`), or other variants all deduplicate to the same canonical URL.
- **Reddit filtering**: Submissions with `metadata.type = "reddit_thread"` are only stored if the URL contains `/comments/` in the path. Homepage, subreddit listings, and user profiles are silently filtered — the endpoint returns `{"status":"skipped"}`.
- **Async write**: All accepted submissions are written to the database asynchronously after the response is sent. The `200 OK` with `status="queued"` confirms the submission was accepted, not that it was written.
- **YouTube enrichment**: For YouTube submissions, the receiver returns `200 OK` immediately after accepting the payload. Enrichment runs asynchronously — the userscript does not wait for it.
- **Enrichment failure**: A failed YouTube enrichment does not cause the endpoint to return an error. The submission is stored and the failure is recorded internally.
