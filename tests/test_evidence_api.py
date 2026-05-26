from pathlib import Path

from httpx import ASGITransport, AsyncClient

from evidencechain.api.routes.evidence import get_evidence_service
from evidencechain.core.config import Settings
from evidencechain.models.factcheck import EvidenceProvider, SearchResult
from evidencechain.providers.base import LLMRequest, SchemaT
from evidencechain.services.claim_service import ClaimService
from evidencechain.services.evidence_service import EvidenceService
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


class FakeSearchProvider:
    name = "brave"

    async def search(self, query: str, count: int) -> list[SearchResult]:
        return [
            SearchResult(
                title="NIH medical study",
                url="https://www.nih.gov/news-events/example",
                snippet="A medical study reported reduced symptoms in the trial.",
                publisher="NIH",
                provider=EvidenceProvider.brave,
                query=query,
            )
        ]


async def test_evidence_retrieve_endpoint_returns_stored_evidence(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'evidence-api.db'}")
    await initialize_database(settings)
    transcript_service = TranscriptService(settings=settings)
    claim_service = ClaimService(settings=settings, provider=FakeClaimProvider())
    evidence_service = EvidenceService(settings=settings, provider=FakeSearchProvider())
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
    claim_result = await claim_service.extract_claims_for_transcript(transcript.id)
    claim_id = claim_result.claims[0].id
    assert claim_id is not None

    from evidencechain.main import create_app

    app = create_app(settings)
    app.dependency_overrides[get_evidence_service] = lambda: evidence_service
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/evidence/retrieve",
            json={"claim_id": claim_id, "max_results": 3},
        )
        list_response = await client.get(f"/api/v1/evidence/claims/{claim_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["claim_id"] == claim_id
    assert payload["provider"] == "brave"
    assert payload["evidence"][0]["publisher"] == "NIH"
    assert payload["evidence"][0]["source_type"] == "government"
    assert list_response.status_code == 200
    assert list_response.json()["evidence"][0]["title"] == "NIH medical study"
