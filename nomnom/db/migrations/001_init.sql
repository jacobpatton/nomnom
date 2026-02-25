PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS _schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS submissions (
    id                INTEGER  PRIMARY KEY AUTOINCREMENT,
    url               TEXT     NOT NULL UNIQUE,
    domain            TEXT     NOT NULL,
    title             TEXT,
    content_markdown  TEXT,
    content_type      TEXT     NOT NULL,
    metadata          TEXT,
    enrichment_status TEXT     NOT NULL DEFAULT 'none',
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
