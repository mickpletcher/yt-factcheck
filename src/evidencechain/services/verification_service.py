from evidencechain.models.factcheck import Claim, EvidenceSource, VerificationResult


class VerificationService:
    async def verify_claim(
        self,
        claim: Claim,
        evidence: list[EvidenceSource],
    ) -> VerificationResult:
        raise NotImplementedError("Claim verification is not implemented yet.")
