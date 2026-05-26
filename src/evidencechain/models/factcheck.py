from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from evidencechain.models.transcript import TranscriptChunk, TranscriptSegment


class ClaimCategory(StrEnum):
    scientific = "scientific"
    historical = "historical"
    medical = "medical"
    political = "political"
    financial = "financial"
    legal = "legal"
    technology = "technology"
    product = "product"


class ClaimStatus(StrEnum):
    pending = "pending"
    supported = "supported"
    contradicted = "contradicted"
    inconclusive = "inconclusive"


class Claim(BaseModel):
    id: int | None = None
    transcript_id: int | None = None
    chunk_position: int = Field(default=0, ge=0)
    text: str
    category: ClaimCategory
    confidence: float = Field(ge=0.0, le=1.0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    source_text: str = Field(min_length=1)
    created_at: datetime | None = None

    @field_validator("text", "source_text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def validate_range(self) -> "Claim":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
        return self

    @property
    def timestamp_seconds(self) -> float:
        return self.start_seconds

    @property
    def source_segment(self) -> TranscriptSegment:
        return TranscriptSegment(
            start_seconds=self.start_seconds,
            end_seconds=self.end_seconds,
            text=self.source_text,
        )


class ClaimCandidate(BaseModel):
    text: str = Field(min_length=1)
    category: ClaimCategory
    confidence: float = Field(ge=0.0, le=1.0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def validate_range(self) -> "ClaimCandidate":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must be greater than or equal to start_seconds")
        return self


class ClaimExtractionChunk(BaseModel):
    position: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str = Field(min_length=1)

    @classmethod
    def from_transcript_chunk(cls, chunk: TranscriptChunk) -> "ClaimExtractionChunk":
        return cls(
            position=chunk.position,
            start_seconds=chunk.start_seconds,
            end_seconds=chunk.end_seconds,
            text=chunk.text,
        )


class ClaimExtractionProviderOutput(BaseModel):
    claims: list[ClaimCandidate] = Field(default_factory=list)


class ClaimExtractionRequest(BaseModel):
    transcript_id: int = Field(gt=0)
    provider: str | None = None


class ClaimExtractionResult(BaseModel):
    transcript_id: int
    provider: str
    prompt_version: str
    claims: list[Claim]


class ClaimList(BaseModel):
    transcript_id: int
    claims: list[Claim]


class ClaimError(BaseModel):
    detail: str


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
