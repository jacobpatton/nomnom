from abc import ABC, abstractmethod

from nomnom.models.submission import Submission


class AbstractSubmissionRepository(ABC):
    @abstractmethod
    def upsert(self, submission: Submission) -> bool:
        """Insert or update a submission. Returns True if inserted (new), False if updated."""

    @abstractmethod
    def create_enrichment_job(self, url: str) -> None:
        """Create a pending enrichment job for the given submission URL."""

    @abstractmethod
    def update_enrichment_job_status(
        self, url: str, status: str, failure_reason: str | None = None
    ) -> None:
        """Update the status of an enrichment job."""

    @abstractmethod
    def update_submission_content(
        self,
        url: str,
        content_markdown: str | None,
        enrichment_status: str,
        enrichment_error: str | None = None,
    ) -> None:
        """Update a submission's content after server-side enrichment. Title is preserved."""
