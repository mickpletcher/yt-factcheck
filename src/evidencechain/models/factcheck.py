from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl

from evidencechain.models.transcript import TranscriptSegment


class ClaimStatus(StrEnum):
    pending = "pending"
    supported = "supported"
    contradicted = "contradicted"
    inconclusive = "inconclusive"


class Claim(BaseModel):
    id: str
    text: str
    timestamp_seconds: float = Field(ge=0)
    source_segment: TranscriptSegment


class EvidenceSource(BaseModel):
    title: str
    url: HttpUrl
    publisher: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VerificationResult(BaseModel):
    claim: Claim
    status: ClaimStatus = ClaimStatus.pending
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[EvidenceSource] = Field(default_factory=list)
    rationale: str = ""
