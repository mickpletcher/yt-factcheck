from pathlib import Path

from evidencechain.core.config import Settings
from evidencechain.models.transcript import TranscriptChunk
from evidencechain.providers.base import LLMRequest, SchemaT
from evidencechain.services.claim_service import ClaimService
from evidencechain.services.transcript_service import TranscriptService
from evidencechain.storage.database import initialize_database


class FakeClaimProvider:
    name = "fake"

    async def generate_structured(
        self,
        request: LLMRequest,
        output_schema: type[SchemaT],
    ) -> SchemaT:
        return output_schema.model_validate(
            {
                "claims": [
                    {
                        "text": "The device uses a lithium battery.",
                        "category": "technology",
                        "confidence": 0.91,
                        "start_seconds": 4.0,
                        "end_seconds": 9.0,
                    }
                ]
            }
        )


async def test_extract_claims_from_chunks_validates_provider_output() -> None:
    service = ClaimService(provider=FakeClaimProvider())
    chunks = [
        TranscriptChunk(
            position=0,
            start_seconds=4,
            end_seconds=9,
            text="The device uses a lithium battery. I think it is neat.",
            segment_start_index=0,
            segment_end_index=0,
        )
    ]

    claims = await service.extract_claims_from_chunks(chunks)

    assert len(claims) == 1
    assert claims[0].category == "technology"
    assert claims[0].confidence == 0.91
    assert claims[0].start_seconds == 4
    assert claims[0].source_text == chunks[0].text


async def test_extract_claims_for_transcript_stores_claims(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'claims.db'}")
    await initialize_database(settings)
    transcript_service = TranscriptService(settings=settings)
    claim_service = ClaimService(settings=settings, provider=FakeClaimProvider())

    transcript = await transcript_service.create_from_upload(
        filename="sample.vtt",
        content=(
            b"WEBVTT\n\n"
            b"00:00:04.000 --> 00:00:09.000\n"
            b"The device uses a lithium battery. I think it is neat.\n"
        ),
        youtube_url="https://www.youtube.com/watch?v=abc123",
        title="Claims",
        video_id="abc123",
    )

    result = await claim_service.extract_claims_for_transcript(transcript.id)
    stored = await claim_service.list_claims(transcript.id)

    assert result.provider == "fake"
    assert result.prompt_version == "claim-extraction-v1"
    assert len(result.claims) == 1
    assert stored[0].id is not None
    assert stored[0].transcript_id == transcript.id
