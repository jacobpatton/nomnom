from pydantic import BaseModel, field_validator, model_validator


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

    @model_validator(mode="after")
    def normalize_youtube_url(self) -> "IngestRequest":
        if self.metadata.get("type") == "youtube_video":
            video_id = self.metadata.get("video_id")
            if video_id:
                self.url = f"https://www.youtube.com/watch?v={video_id}"
        return self


class IngestResponse(BaseModel):
    status: str
    message: str
