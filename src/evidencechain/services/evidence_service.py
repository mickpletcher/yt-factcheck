from evidencechain.models.factcheck import Claim, EvidenceSource


class EvidenceService:
    async def retrieve_evidence(self, claim: Claim) -> list[EvidenceSource]:
        raise NotImplementedError("Evidence retrieval is not implemented yet.")
