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


class Verdict(StrEnum):
    true = "True"
    mostly_true = "Mostly True"
    misleading = "Misleading"
    unverified = "Unverified"
    false = "False"
    needs_context = "Needs Context"


class EvidenceRelationship(StrEnum):
    supports = "supports"
    contradicts = "contradicts"
    neutral = "neutral"


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


class EvidenceProvider(StrEnum):
    brave = "brave"
    tavily = "tavily"
    bing = "bing"
    serpapi = "serpapi"


class EvidenceSourceType(StrEnum):
    government = "government"
    academic = "academic"
    peer_reviewed = "peer_reviewed"
    established_journalism = "established_journalism"
    general = "general"


class SearchQuery(BaseModel):
    query: str = Field(min_length=1)
    purpose: str = "general"

    @field_validator("query", "purpose")
    @classmethod
    def normalize_query_text(cls, value: str) -> str:
        return " ".join(value.split())


class SearchResult(BaseModel):
    title: str = ""
    url: HttpUrl
    snippet: str = ""
    publisher: str = ""
    provider: EvidenceProvider
    query: str
    published_at: str | None = None
    raw: dict[str, object] = Field(default_factory=dict)

    @field_validator("title", "snippet", "publisher", "query")
    @classmethod
    def normalize_result_text(cls, value: str) -> str:
        return " ".join(value.split())


class EvidenceScore(BaseModel):
    source_type: EvidenceSourceType = EvidenceSourceType.general
    credibility_score: float = Field(ge=0.0, le=1.0)
    relevance_score: float = Field(ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=1.0)
    ranking_score: float = Field(ge=0.0, le=1.0)


class RetrievedEvidence(BaseModel):
    id: int | None = None
    claim_id: int | None = None
    provider: EvidenceProvider
    query: str
    title: str
    url: HttpUrl
    publisher: str
    snippet: str = ""
    source_type: EvidenceSourceType = EvidenceSourceType.general
    credibility_score: float = Field(ge=0.0, le=1.0)
    relevance_score: float = Field(ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=1.0)
    ranking_score: float = Field(ge=0.0, le=1.0)
    attribution: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvidenceRetrievalRequest(BaseModel):
    claim_id: int | None = Field(default=None, gt=0)
    claim_text: str | None = Field(default=None, min_length=1)
    provider: EvidenceProvider | None = None
    max_results: int = Field(default=10, ge=1, le=50)

    @field_validator("claim_text")
    @classmethod
    def normalize_claim_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.split())

    @model_validator(mode="after")
    def require_claim_id_or_text(self) -> "EvidenceRetrievalRequest":
        if self.claim_id is None and not self.claim_text:
            raise ValueError("claim_id or claim_text is required")
        return self


class EvidenceRetrievalResult(BaseModel):
    run_id: int
    claim_id: int | None = None
    claim_text: str
    provider: EvidenceProvider
    queries: list[SearchQuery]
    evidence: list[RetrievedEvidence]


class EvidenceList(BaseModel):
    claim_id: int
    evidence: list[RetrievedEvidence]


class VerificationResult(BaseModel):
    claim: Claim
    status: ClaimStatus = ClaimStatus.pending
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[RetrievedEvidence] = Field(default_factory=list)
    rationale: str = ""


class EvidenceComparison(BaseModel):
    evidence_id: int = Field(gt=0)
    relationship: EvidenceRelationship
    relevance_score: float = Field(ge=0.0, le=1.0)
    stance_score: float = Field(ge=-1.0, le=1.0)
    explanation: str


class VerdictSafeguards(BaseModel):
    stored_evidence_only: bool
    has_sufficient_evidence: bool
    citation_validation_passed: bool
    blocked_reasons: list[str] = Field(default_factory=list)


class ScoringRequest(BaseModel):
    claim_id: int = Field(gt=0)
    min_evidence: int = Field(default=2, ge=1, le=10)


class ScoringResult(BaseModel):
    id: int | None = None
    claim: Claim
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence: list[RetrievedEvidence]
    comparisons: list[EvidenceComparison]
    cited_evidence_ids: list[int]
    safeguards: VerdictSafeguards
    created_at: datetime | None = None


class ScoringList(BaseModel):
    claim_id: int
    results: list[ScoringResult]
