from evidencechain.models.factcheck import VerificationResult
from evidencechain.services.claim_service import ClaimService
from evidencechain.services.evidence_service import EvidenceService
from evidencechain.services.transcript_service import TranscriptService
from evidencechain.services.verification_service import VerificationService


class FactCheckPipeline:
    def __init__(
        self,
        transcript_service: TranscriptService,
        claim_service: ClaimService,
        evidence_service: EvidenceService,
        verification_service: VerificationService,
    ) -> None:
        self.transcript_service = transcript_service
        self.claim_service = claim_service
        self.evidence_service = evidence_service
        self.verification_service = verification_service

    async def run(self, youtube_url: str) -> list[VerificationResult]:
        segments = await self.transcript_service.extract_transcript(youtube_url)
        claims = await self.claim_service.extract_claims(segments)

        results: list[VerificationResult] = []
        for claim in claims:
            evidence = await self.evidence_service.retrieve_evidence(claim)
            result = await self.verification_service.verify_claim(claim, evidence)
            results.append(result)

        return results
