from evidencechain.models.factcheck import Claim, ClaimStatus, RetrievedEvidence, VerificationResult
from evidencechain.services.scoring_service import ScoringEngine


class VerificationService:
    def __init__(self, engine: ScoringEngine | None = None) -> None:
        self.engine = engine or ScoringEngine()

    async def verify_claim(
        self,
        claim: Claim,
        evidence: list[RetrievedEvidence],
    ) -> VerificationResult:
        if claim.id is None:
            return VerificationResult(
                claim=claim,
                status=ClaimStatus.inconclusive,
                confidence=0.0,
                evidence=[],
                rationale="Verification requires a stored claim and stored evidence objects.",
            )
        scoring = self.engine.score(claim, evidence)
        if scoring.verdict.value in {"True", "Mostly True"}:
            status = ClaimStatus.supported
        elif scoring.verdict.value in {"False", "Misleading"}:
            status = ClaimStatus.contradicted
        else:
            status = ClaimStatus.inconclusive
        return VerificationResult(
            claim=claim,
            status=status,
            confidence=scoring.confidence,
            evidence=scoring.evidence,
            rationale=scoring.explanation,
        )
