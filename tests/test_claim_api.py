from pathlib import Path

from httpx import ASGITransport, AsyncClient

from evidencechain.api.routes.claims import get_claim_service
from evidencechain.core.config import Settings
from evidencechain.main import create_app
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
                        "text": "The medicine reduced symptoms in the trial.",
                        "category": "medical",
                        "confidence": 0.86,
                        "start_seconds": 1.0,
                        "end_seconds": 3.0,
                    }
                ]
            }
        )


async def test_claim_extract_endpoint_returns_structured_claims(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'claim-api.db'}")
    await initialize_database(settings)
    transcript_service = TranscriptService(settings=settings)
    claim_service = ClaimService(settings=settings, provider=FakeClaimProvider())
    transcript = await transcript_service.create_from_upload(
        filename="medical.vtt",
        content=(
            b"WEBVTT\n\n"
            b"00:00:01.000 --> 00:00:03.000\n"
            b"The medicine reduced symptoms in the trial.\n"
        ),
        youtube_url="https://www.youtube.com/watch?v=abc123",
        title="Medical",
        video_id="abc123",
    )
    app = create_app(settings)
    app.dependency_overrides[get_claim_service] = lambda: claim_service
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/claims/extract",
            json={"transcript_id": transcript.id},
        )
        list_response = await client.get(f"/api/v1/claims/transcripts/{transcript.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "fake"
    assert payload["claims"][0]["category"] == "medical"
    assert payload["claims"][0]["confidence"] == 0.86
    assert list_response.status_code == 200
    assert (
        list_response.json()["claims"][0]["text"]
        == "The medicine reduced symptoms in the trial."
    )
