from evidencechain.models.factcheck import Claim, RetrievedEvidence, VerificationResult


class VerificationService:
    async def verify_claim(
        self,
        claim: Claim,
        evidence: list[RetrievedEvidence],
    ) -> VerificationResult:
        raise NotImplementedError("Claim verification is not implemented yet.")
