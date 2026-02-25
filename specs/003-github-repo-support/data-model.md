# Data Model: GitHub Repository Support

**Feature**: `003-github-repo-support`
**Date**: 2026-02-24

---

## Storage: Existing `submissions` Table

No new tables. GitHub repository records are stored in the existing `submissions` table using `content_type = "github_repo"` as the discriminator.

### Column Mapping

| Column              | Type        | GitHub Repo Value                   | Notes                                                       |
| ------------------- | ----------- | ----------------------------------- | ----------------------------------------------------------- |
| `url`               | TEXT UNIQUE | `https://github.com/<owner>/<repo>` | Canonical URL; unique key; fragments and sub-paths stripped |
| `domain`            | TEXT        | `"github.com"`                      | Used to detect GitHub submissions                           |
| `title`             | TEXT        | `"<owner>/<repo>"`                  | Human-readable identifier                                   |
| `content_markdown`  | TEXT        | README.md content                   | Empty string if fetch fails or no README exists             |
| `content_type`      | TEXT        | `"github_repo"`                     | New discriminator value; indexed in existing schema         |
| `metadata`          | TEXT (JSON) | `{"owner": "...", "repo": "..."}`   | Parsed owner and repo name                                  |
| `enrichment_status` | TEXT        | `"none"`                            | README fetched synchronously; no async enrichment needed    |
| `ingested_at`       | DATETIME    | Set on insert                       | Not updated on duplicate submission                         |
| `updated_at`        | DATETIME    | Set on insert                       | Not updated on duplicate submission                         |

### Uniqueness & Deduplication

- **Unique key**: `url` column (enforced by `UNIQUE` constraint in existing schema)
- **Canonical form**: `https://github.com/<owner>/<repo>` — lowercase owner and repo, no trailing slash, no fragment, no sub-path
- **On duplicate**: existing record is left unchanged (no update); ingestion returns a skipped status

---

## New Content Type Value

`"github_repo"` is added to the set of valid `content_type` values alongside existing types (e.g., `"youtube"`, `"web_page"`).

---

## URL Normalization Rules

Input URL → Canonical URL transformation:

1. Parse the URL: scheme, host, path, fragment
2. Verify host is `github.com`
3. Split path into segments (filter empty strings)
4. If fewer than 2 segments → **reject** (user/org profile or GitHub root)
5. If first segment is in blocklist `{orgs, users, features, marketplace, settings, notifications, dashboard, explore, pulls, issues, sponsors}` → **reject**
6. Canonical URL = `https://github.com/<segments[0]>/<segments[1]>`

---

## GitHub Repository Entity (Logical)

| Attribute       | Source                                                                 | Constraint          |
| --------------- | ---------------------------------------------------------------------- | ------------------- |
| Owner username  | URL segment[0]                                                         | Non-empty string    |
| Repository name | URL segment[1]                                                         | Non-empty string    |
| Canonical URL   | Derived (`github.com/<owner>/<repo>`)                                  | Globally unique     |
| README content  | Fetched from `raw.githubusercontent.com/<owner>/<repo>/HEAD/README.md` | May be empty string |

---

## No Schema Migration Required

The existing `submissions` table already has all needed columns. No `ALTER TABLE` or new migration file is needed.
