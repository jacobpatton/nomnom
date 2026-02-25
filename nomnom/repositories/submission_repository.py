import json
import logging

from nomnom.db.connection import get_connection
from nomnom.models.submission import Submission
from nomnom.repositories.base import AbstractSubmissionRepository

logger = logging.getLogger(__name__)


class SubmissionRepository(AbstractSubmissionRepository):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def upsert(self, submission: Submission) -> bool:
        """
        Insert or update a submission keyed by URL.
        Preserves ingested_at on update. Returns True if inserted, False if updated.
        """
        metadata_json = json.dumps(submission.metadata)
        with get_connection(self._db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO submissions
                    (url, domain, title, content_markdown, content_type,
                     metadata, enrichment_status, enrichment_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    domain            = excluded.domain,
                    title             = excluded.title,
                    content_markdown  = excluded.content_markdown,
                    content_type      = excluded.content_type,
                    metadata          = excluded.metadata,
                    enrichment_status = excluded.enrichment_status,
                    enrichment_error  = excluded.enrichment_error,
                    ingested_at       = submissions.ingested_at,
                    updated_at        = CURRENT_TIMESTAMP
                """,
                (
                    submission.url,
                    submission.domain,
                    submission.title,
                    submission.content_markdown,
                    submission.content_type,
                    metadata_json,
                    submission.enrichment_status,
                    submission.enrichment_error,
                ),
            )
            conn.commit()
            # lastrowid is set on INSERT; on UPDATE it equals the existing rowid
            # changes() == 1 for both, so we use rowid change behaviour:
            # SQLite sets last_insert_rowid to 0 on UPDATE with ON CONFLICT
            is_insert = cursor.lastrowid != 0 and conn.execute(
                "SELECT changes()"
            ).fetchone()[0] == 1
            # Simpler: check if updated_at == ingested_at (new row) via direct query
            row = conn.execute(
                "SELECT (ingested_at = updated_at) as is_new FROM submissions WHERE url = ?",
                (submission.url,),
            ).fetchone()
            return bool(row["is_new"]) if row else True

    def create_enrichment_job(self, url: str) -> None:
        with get_connection(self._db_path) as conn:
            conn.execute(
                "INSERT INTO enrichment_jobs (submission_url) VALUES (?)", (url,)
            )
            conn.commit()

    def update_enrichment_job_status(
        self, url: str, status: str, failure_reason: str | None = None
    ) -> None:
        with get_connection(self._db_path) as conn:
            conn.execute(
                """
                UPDATE enrichment_jobs
                SET status = ?, failure_reason = ?, completed_at = CURRENT_TIMESTAMP
                WHERE submission_url = ? AND status = 'pending'
                """,
                (status, failure_reason, url),
            )
            conn.commit()

    def update_submission_content(
        self,
        url: str,
        title: str,
        content_markdown: str,
        metadata: dict,
        enrichment_status: str,
        enrichment_error: str | None = None,
    ) -> None:
        """Update a submission's content after server-side enrichment."""
        with get_connection(self._db_path) as conn:
            conn.execute(
                """
                UPDATE submissions
                SET title = ?, content_markdown = ?, metadata = ?,
                    enrichment_status = ?, enrichment_error = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE url = ?
                """,
                (title, content_markdown, json.dumps(metadata), enrichment_status, enrichment_error, url),
            )
            conn.commit()
