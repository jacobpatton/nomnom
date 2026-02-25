# API Contract: Ingest Endpoint (GitHub Extension)

**Feature**: `003-github-repo-support`
**Date**: 2026-02-24

---

## Endpoint: `POST /`

No changes to the endpoint signature. The existing `IngestRequest` schema handles GitHub submissions — the receiver detects GitHub by inspecting `domain`.

### Request Schema (unchanged)

```json
{
  "url": "string (required)",
  "domain": "string (required)",
  "title": "string (optional)",
  "content_markdown": "string (optional)",
  "metadata": "object (optional)"
}
```

### GitHub-Specific Behavior

When `domain == "github.com"` and the URL resolves to a valid repository path:

1. The receiver **ignores** `title`, `content_markdown`, and `metadata` from the request — all values are derived server-side.
2. The URL is normalized to `https://github.com/<owner>/<repo>`.
3. README is fetched from `raw.githubusercontent.com/<owner>/<repo>/HEAD/README.md`.
4. The record is saved with `content_type = "github_repo"`.

### Response Schema (unchanged)

```json
{
  "status": "string",
  "message": "string"
}
```

### Response Status Values (GitHub-specific additions)

| status      | Condition                                                             |
| ----------- | --------------------------------------------------------------------- |
| `"saved"`   | New repo record created successfully                                  |
| `"skipped"` | Record already exists for this canonical URL; no update made          |
| `"skipped"` | URL is a GitHub page but not a repository (profile, org, system page) |

### Example: Deep link normalized and saved

**Request**

```json
{
  "url": "https://github.com/owner/repo/blob/main/src/main.py",
  "domain": "github.com",
  "title": "owner/repo/blob/main/src/main.py"
}
```

**Response**

```json
{
  "status": "saved",
  "message": "GitHub repository owner/repo saved."
}
```

**Stored record**

```json
{
  "url": "https://github.com/owner/repo",
  "domain": "github.com",
  "title": "owner/repo",
  "content_type": "github_repo",
  "content_markdown": "<README content>",
  "metadata": { "owner": "owner", "repo": "repo" },
  "enrichment_status": "none"
}
```

### Example: Anchor link deduplicated

**Request**

```json
{
  "url": "https://github.com/owner/repo#readme",
  "domain": "github.com"
}
```

**Response** (record already exists)

```json
{
  "status": "skipped",
  "message": "GitHub repository owner/repo already saved."
}
```

### Example: Non-repo URL rejected

**Request**

```json
{
  "url": "https://github.com/owner",
  "domain": "github.com"
}
```

**Response**

```json
{
  "status": "skipped",
  "message": "Not a GitHub repository URL."
}
```
