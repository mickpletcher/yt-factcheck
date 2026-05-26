from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from evidencechain.models.factcheck import ClaimCategory, Verdict
from evidencechain.models.transcript import VideoMetadata


class ReportFormat(StrEnum):
    html = "html"
    markdown = "markdown"
    json = "json"


class ReportEvidenceLink(BaseModel):
    id: int
    title: str
    url: str
    publisher: str
    snippet: str
    source_type: str
    ranking_score: float = Field(ge=0.0, le=1.0)
    retrieved_at: datetime | str
    attribution: str
    cited: bool = False


class ReportClaimSummary(BaseModel):
    id: int
    text: str
    category: ClaimCategory
    timestamp_seconds: float = Field(ge=0)
    timestamp_label: str
    claim_confidence: float = Field(ge=0.0, le=1.0)
    verdict: Verdict
    verdict_confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    citations: list[ReportEvidenceLink] = Field(default_factory=list)
    evidence_links: list[ReportEvidenceLink] = Field(default_factory=list)


class ReportVerdictBucket(BaseModel):
    verdict: Verdict
    count: int = Field(ge=0)
    percentage: float = Field(ge=0.0, le=100.0)


class ReportVerdictSummary(BaseModel):
    total_claims: int = Field(ge=0)
    average_confidence: float = Field(ge=0.0, le=1.0)
    buckets: list[ReportVerdictBucket] = Field(default_factory=list)


class ReportExport(BaseModel):
    transcript_id: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    video: VideoMetadata
    verdict_summary: ReportVerdictSummary
    claims: list[ReportClaimSummary] = Field(default_factory=list)
