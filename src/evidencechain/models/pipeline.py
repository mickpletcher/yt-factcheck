from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class PipelineStage(StrEnum):
    transcript_ingestion = "transcript_ingestion"
    chunking = "chunking"
    claim_extraction = "claim_extraction"
    evidence_retrieval = "evidence_retrieval"
    scoring = "scoring"
    report_generation = "report_generation"


class PipelineJobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    retrying = "retrying"
    canceled = "canceled"


class PipelineStageStatus(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class PipelineRunRequest(BaseModel):
    youtube_url: HttpUrl | None = None
    transcript_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_url_or_transcript(self) -> "PipelineRunRequest":
        if self.youtube_url is None and self.transcript_id is None:
            raise ValueError("youtube_url or transcript_id is required")
        return self


class PipelineRunResponse(BaseModel):
    job_id: int
    status: PipelineJobStatus


class PipelineStageRun(BaseModel):
    stage: PipelineStage
    status: PipelineStageStatus
    attempt: int = Field(ge=1)
    progress: float = Field(ge=0, le=1)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineJobDetail(BaseModel):
    id: int
    youtube_url: str
    status: PipelineJobStatus
    progress: float = Field(ge=0, le=1)
    current_stage: PipelineStage | None = None
    transcript_id: int | None = None
    claim_ids: list[int] = Field(default_factory=list)
    report: dict[str, Any] | None = None
    error_message: str | None = None
    retry_count: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime
    stages: list[PipelineStageRun] = Field(default_factory=list)


class PipelineEvent(BaseModel):
    id: int
    job_id: int
    stage: PipelineStage | None = None
    event_type: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PipelineJobList(BaseModel):
    jobs: list[PipelineJobDetail]


class PipelineMetrics(BaseModel):
    queued: int = 0
    running: int = 0
    retrying: int = 0
    succeeded: int = 0
    failed: int = 0
    total: int = 0
    average_duration_ms: float | None = None
    stage_average_duration_ms: dict[str, float] = Field(default_factory=dict)


class PipelineError(BaseModel):
    detail: str


class PipelineBackend(StrEnum):
    asyncio = "asyncio"
    celery = "celery"
    redis = "redis"


class WorkerHealth(BaseModel):
    backend: PipelineBackend = PipelineBackend.asyncio
    running: bool
    worker_count: int
    queue_size: int

    @field_validator("queue_size")
    @classmethod
    def require_non_negative_queue_size(cls, value: int) -> int:
        if value < 0:
            raise ValueError("queue_size must be non-negative")
        return value
