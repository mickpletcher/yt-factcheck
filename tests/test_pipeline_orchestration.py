from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from evidencechain.api.routes.pipelines import get_orchestrator
from evidencechain.core.config import Settings
from evidencechain.models.factcheck import EvidenceProvider, SearchResult
from evidencechain.pipelines.orchestration import FactCheckOrchestrator
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
                        "confidence": 0.9,
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
                title="CDC trial summary",
                url="https://www.cdc.gov/news/example",
                snippet="Evidence shows the medicine reduced symptoms during the trial.",
                publisher="CDC",
                provider=EvidenceProvider.brave,
                query=query,
            ),
        ]


async def fake_youtube_info(_: str) -> dict[str, object]:
    return {
        "id": "abc123",
        "title": "Medical Trial Review",
        "channel": "Evidence Lab",
        "subtitles": {"en": [{"ext": "vtt", "url": "https://captions.test/abc.vtt"}]},
    }


async def build_orchestrator(tmp_path: Path) -> FactCheckOrchestrator:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'pipeline.db'}")
    await initialize_database(settings)
    transcript_service = TranscriptService(
        settings=settings,
        youtube_info_fetcher=fake_youtube_info,
    )

    async def fake_download(_: str) -> str:
        return (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:03.000\n"
            "The medicine reduced symptoms in the trial.\n"
        )

    transcript_service._download_text = fake_download
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
    return FactCheckOrchestrator(
        settings=settings,
        transcript_service=transcript_service,
        claim_service=claim_service,
        evidence_service=evidence_service,
        scoring_service=scoring_service,
        report_service=report_service,
    )


async def test_pipeline_orchestrator_runs_all_stages(tmp_path: Path) -> None:
    orchestrator = await build_orchestrator(tmp_path)
    job = await orchestrator.submit("https://www.youtube.com/watch?v=abc123")

    completed = await orchestrator.run_job(job.id)
    metrics = await orchestrator.repository.metrics()
    events = await orchestrator.repository.list_events(job.id)

    assert completed.status == "succeeded"
    assert completed.progress == 1
    assert completed.transcript_id is not None
    assert len(completed.claim_ids) == 1
    assert completed.report is not None
    assert [stage.status for stage in completed.stages] == ["succeeded"] * 6
    assert metrics.succeeded == 1
    assert metrics.stage_average_duration_ms["report_generation"] >= 0
    assert any(event.event_type == "job_succeeded" for event in events)


async def test_pipeline_api_queues_and_reports_status(tmp_path: Path) -> None:
    orchestrator = await build_orchestrator(tmp_path)

    from evidencechain.main import create_app

    app = create_app(orchestrator.settings)
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/pipelines/factcheck",
            json={"youtube_url": "https://www.youtube.com/watch?v=abc123"},
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["job_id"] > 0
    assert payload["status"] == "queued"


async def test_pipeline_manual_retry_requires_failed_job(tmp_path: Path) -> None:
    orchestrator = await build_orchestrator(tmp_path)
    job = await orchestrator.submit("https://www.youtube.com/watch?v=abc123")

    with pytest.raises(ValueError, match="Only failed"):
        await orchestrator.retry(job.id)


async def test_pipeline_job_can_be_canceled_before_running(tmp_path: Path) -> None:
    orchestrator = await build_orchestrator(tmp_path)
    job = await orchestrator.submit("https://www.youtube.com/watch?v=abc123")

    canceled = await orchestrator.cancel(job.id)
    completed = await orchestrator.run_job(job.id)

    assert canceled.status == "canceled"
    assert completed.status == "canceled"
