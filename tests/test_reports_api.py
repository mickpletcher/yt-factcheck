from pathlib import Path

from httpx import ASGITransport, AsyncClient

from evidencechain.api.routes.reports import get_report_service
from evidencechain.core.config import Settings
from evidencechain.models.factcheck import EvidenceProvider, SearchResult
from evidencechain.models.report import ReportFormat
from evidencechain.providers.base import LLMRequest, SchemaT
from evidencechain.services.claim_service import ClaimService
from evidencechain.services.evidence_service import EvidenceService
from evidencechain.services.report_service import ReportService
from evidencechain.services.scoring_service import ScoringService
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
                snippet="A study found the medicine reduced symptoms in the trial.",
                publisher="NIH",
                provider=EvidenceProvider.brave,
                query=query,
            ),
            SearchResult(
                title="CDC medical summary",
                url="https://www.cdc.gov/news/example",
                snippet="Evidence shows the medicine reduced symptoms during the trial.",
                publisher="CDC",
                provider=EvidenceProvider.brave,
                query=query,
            ),
        ]


async def build_report_fixture(tmp_path: Path) -> tuple[int, ReportService]:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'reports-api.db'}")
    await initialize_database(settings)
    transcript_service = TranscriptService(settings=settings)
    claim_service = ClaimService(settings=settings, provider=FakeClaimProvider())
    evidence_service = EvidenceService(settings=settings, provider=FakeSearchProvider())
    scoring_service = ScoringService(settings=settings, evidence_service=evidence_service)
    report_service = ReportService(
        settings=settings,
        transcript_service=transcript_service,
        claim_service=claim_service,
        evidence_service=evidence_service,
        scoring_service=scoring_service,
    )
    transcript = await transcript_service.create_from_upload(
        filename="medical.vtt",
        content=(
            b"WEBVTT\n\n"
            b"00:00:01.000 --> 00:00:03.000\n"
            b"The medicine reduced symptoms in the trial.\n"
        ),
        youtube_url="https://www.youtube.com/watch?v=abc123",
        title="Medical Trial Review",
        video_id="abc123",
    )
    claim_result = await claim_service.extract_claims_for_transcript(transcript.id)
    claim_id = claim_result.claims[0].id
    assert claim_id is not None
    await evidence_service.retrieve_evidence_for_claim(claim_id, max_results=5)
    await scoring_service.score_claim(claim_id)
    return transcript.id, report_service


async def test_report_json_endpoint_returns_public_report(tmp_path: Path) -> None:
    transcript_id, report_service = await build_report_fixture(tmp_path)

    from evidencechain.main import create_app

    app = create_app(report_service.settings)
    app.dependency_overrides[get_report_service] = lambda: report_service
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v1/reports/transcripts/{transcript_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["video"]["title"] == "Medical Trial Review"
    assert payload["verdict_summary"]["total_claims"] == 1
    assert payload["claims"][0]["verdict"] == "True"
    assert payload["claims"][0]["citations"][0]["publisher"] == "NIH"
    assert payload["claims"][0]["evidence_links"][0]["url"].startswith("https://")


async def test_report_html_and_markdown_render_public_outputs(tmp_path: Path) -> None:
    transcript_id, report_service = await build_report_fixture(tmp_path)

    html = await report_service.render_report(transcript_id, ReportFormat.html)
    markdown = await report_service.render_report(transcript_id, ReportFormat.markdown)
    exported = await report_service.export_report(
        transcript_id,
        ReportFormat.json,
        output_dir=tmp_path,
    )

    assert "<h1>Medical Trial Review</h1>" in html
    assert "Verdict Summary" in html
    assert "NIH medical study" in html
    assert "# Medical Trial Review" in markdown
    assert "Evidence:" in markdown
    assert exported.exists()
