from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class TranscriptSource(StrEnum):
    youtube = "youtube"
    upload = "upload"


class TranscriptFormat(StrEnum):
    txt = "txt"
    srt = "srt"
    vtt = "vtt"
    json = "json"


class VideoMetadata(BaseModel):
    video_id: str
    youtube_url: str
    title: str = ""
    channel: str = ""
    duration_seconds: int | None = Field(default=None, ge=0)
    upload_date: str | None = None


class TranscriptSegment(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.replace("\ufeff", "").split())

    @model_validator(mode="after")
    def validate_range(self) -> "TranscriptSegment":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
        return self


class TranscriptChunk(BaseModel):
    position: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str = Field(min_length=1)
    segment_start_index: int = Field(ge=0)
    segment_end_index: int = Field(ge=0)


class TranscriptRecord(BaseModel):
    id: int
    metadata: VideoMetadata
    source: TranscriptSource
    language: str = "en"
    raw_format: TranscriptFormat
    segment_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TranscriptDetail(TranscriptRecord):
    segments: list[TranscriptSegment]
    chunks: list[TranscriptChunk]


class TranscriptFromUrlRequest(BaseModel):
    youtube_url: HttpUrl
    language: str = "en"

    @field_validator("youtube_url")
    @classmethod
    def validate_youtube_url(cls, value: HttpUrl) -> HttpUrl:
        host = urlparse(str(value)).netloc.lower()
        allowed_hosts = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
        if host not in allowed_hosts:
            raise ValueError("youtube_url must use youtube.com or youtu.be")
        return value


class TranscriptChunkList(BaseModel):
    transcript_id: int
    chunks: list[TranscriptChunk]


class TranscriptError(BaseModel):
    detail: str
