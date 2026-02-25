from pydantic import BaseModel, field_validator


class IngestRequest(BaseModel):
    url: str
    domain: str
    title: str | None = None
    content_markdown: str | None = None
    metadata: dict = {}

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("url must not be empty")
        return v

    @field_validator("domain")
    @classmethod
    def domain_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("domain must not be empty")
        return v


class IngestResponse(BaseModel):
    status: str
    message: str
