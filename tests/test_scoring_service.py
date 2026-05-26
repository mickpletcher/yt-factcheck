from pathlib import Path

import aiosqlite

from evidencechain.core.config import Settings
from evidencechain.models.factcheck import Claim, EvidenceProvider, SearchResult, Verdict
from evidencechain.services.evidence_service import EvidenceService
from evidencechain.services.scoring_service import ScoringEngine, ScoringService
from evidencechain.storage.database import initialize_database


class FakeSearchProvider:
    name = "brave"

    async def search(self, query: str, count: int) -> list[SearchResult]:
        return [
            SearchResult(
                title="NIH trial result",
                url="https://www.nih.gov/example-trial",
                snippet="A study found the medicine reduced symptoms in the trial.",
                publisher="NIH",
                provider=EvidenceProvider.brave,
                query=query,
            ),
            SearchResult(
                title="CDC clinical summary",
                url="https://www.cdc.gov/example-summary",
                snippet="Evidence shows the medicine reduced symptoms during the trial.",
                publisher="CDC",
                provider=EvidenceProvider.brave,
                query=query,
            ),
        ]


async def test_scoring_engine_returns_unverified_when_evidence_is_not_stored() -> None:
    claim = Claim(
        id=1,
        text="The medicine reduced symptoms in the trial.",
        category="medical",
        confidence=0.9,
        start_seconds=1,
        end_seconds=2,
        source_text="The medicine reduced symptoms in the trial.",
    )
    result = ScoringEngine().score(claim, evidence=[])

    assert result.verdict == Verdict.unverified
    assert result.confidence == 0.0
    assert result.safeguards.has_sufficient_evidence is False
    assert "Insufficient stored evidence" in result.explanation


async def test_scoring_service_scores_only_stored_evidence(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'scoring.db'}")
    await initialize_database(settings)
    claim = Claim(
        id=1,
        transcript_id=1,
        text="The medicine reduced symptoms in the trial.",
        category="medical",
        confidence=0.9,
        start_seconds=1,
        end_seconds=2,
        source_text="The medicine reduced symptoms in the trial.",
    )
    async with aiosqlite.connect(settings.sqlite_path) as connection:
        await connection.execute(
            """
            INSERT INTO transcripts (id, video_id, youtube_url, source, raw_format)
            VALUES (?, ?, ?, ?, ?)
            """,
            (1, "abc123", "https://www.youtube.com/watch?v=abc123", "upload", "text"),
        )
        await connection.execute(
            """
            INSERT INTO claim_extraction_runs (id, transcript_id, provider, prompt_version)
            VALUES (?, ?, ?, ?)
            """,
            (1, 1, "fake", "test"),
        )
        await connection.execute(
            """
            INSERT INTO claims (
                id, transcript_id, extraction_run_id, chunk_position, text, category,
                confidence, start_seconds, end_seconds, source_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                1,
                1,
                0,
                claim.text,
                claim.category.value,
                claim.confidence,
                claim.start_seconds,
                claim.end_seconds,
                claim.source_text,
            ),
        )
        await connection.commit()

    evidence_service = EvidenceService(settings=settings, provider=FakeSearchProvider())
    await evidence_service.retrieve_evidence_for_claim(1, max_results=5)
    scoring_service = ScoringService(settings=settings, evidence_service=evidence_service)
    scoring = await scoring_service.score_claim(1)

    assert scoring.verdict == Verdict.true
    assert scoring.confidence > 0.0
    assert scoring.safeguards.stored_evidence_only is True
    assert scoring.safeguards.citation_validation_passed is True
    assert len(scoring.cited_evidence_ids) >= 2
    assert all(item.id in scoring.cited_evidence_ids for item in scoring.evidence)
