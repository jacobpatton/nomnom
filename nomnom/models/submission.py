from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Submission:
    url: str
    domain: str
    content_type: str
    title: str | None = None
    content_markdown: str | None = None
    metadata: dict = field(default_factory=dict)
    enrichment_status: str = "none"
    enrichment_error: str | None = None
    ingested_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EnrichmentJob:
    submission_url: str
    status: str = "pending"
    failure_reason: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
