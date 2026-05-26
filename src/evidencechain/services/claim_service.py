from evidencechain.models.factcheck import Claim, TranscriptSegment


class ClaimService:
    async def extract_claims(self, segments: list[TranscriptSegment]) -> list[Claim]:
        raise NotImplementedError("Claim extraction is not implemented yet.")
