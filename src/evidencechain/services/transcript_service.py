from evidencechain.models.factcheck import TranscriptSegment


class TranscriptService:
    async def extract_transcript(self, youtube_url: str) -> list[TranscriptSegment]:
        raise NotImplementedError("Transcript extraction is not implemented yet.")
