from pathlib import Path

from evidencechain.core.config import Settings
from evidencechain.models.factcheck import Claim, EvidenceProvider, SearchResult
from evidencechain.services.evidence_service import EvidenceService
from evidencechain.storage.database import initialize_database


class FakeSearchProvider:
    name = "brave"

    def __init__(self) -> None:
        self.calls = 0

    async def search(self, query: str, count: int) -> list[SearchResult]:
        self.calls += 1
        return [
            SearchResult(
                title="CDC trial evidence",
                url="https://www.cdc.gov/example",
                snippet="The medicine reduced symptoms in a clinical trial with evidence.",
                publisher="CDC",
                provider=EvidenceProvider.brave,
                query=query,
            ),
            SearchResult(
                title="CDC trial evidence duplicate",
                url="https://cdc.gov/example?utm_source=test",
                snippet="Duplicate result.",
                publisher="CDC",
                provider=EvidenceProvider.brave,
                query=query,
            ),
            SearchResult(
                title="Forum post",
                url="https://example.com/forum",
                snippet="Someone said the same thing.",
                publisher="Example",
                provider=EvidenceProvider.brave,
                query=query,
            ),
        ]


async def test_retrieve_evidence_ranks_dedupes_and_stores_results(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'evidence.db'}")
    await initialize_database(settings)
    provider = FakeSearchProvider()
    service = EvidenceService(settings=settings, provider=provider)
    claim = Claim(
        text="The medicine reduced symptoms in the trial.",
        category="medical",
        confidence=0.9,
        start_seconds=1,
        end_seconds=2,
        source_text="The medicine reduced symptoms in the trial.",
    )

    result = await service.retrieve_evidence(claim, max_results=5)

    assert result.provider == EvidenceProvider.brave
    assert result.run_id > 0
    assert len(result.queries) == settings.evidence_search_max_queries
    assert len(result.evidence) == 2
    assert result.evidence[0].source_type == "government"
    assert result.evidence[0].credibility_score == 1.0
    assert result.evidence[0].ranking_score >= result.evidence[1].ranking_score
    assert "CDC trial evidence" in result.evidence[0].attribution


async def test_search_results_are_cached_by_provider_and_query(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'cache.db'}")
    await initialize_database(settings)
    provider = FakeSearchProvider()
    service = EvidenceService(settings=settings, provider=provider)
    claim = Claim(
        text="The medicine reduced symptoms in the trial.",
        category="medical",
        confidence=0.9,
        start_seconds=1,
        end_seconds=2,
        source_text="The medicine reduced symptoms in the trial.",
    )

    await service.retrieve_evidence(claim)
    first_call_count = provider.calls
    await service.retrieve_evidence(claim)

    assert first_call_count == settings.evidence_search_max_queries
    assert provider.calls == first_call_count
