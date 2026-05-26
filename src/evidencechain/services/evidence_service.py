import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import aiosqlite
from pydantic import TypeAdapter

from evidencechain.core.config import Settings, get_settings
from evidencechain.models.factcheck import (
    Claim,
    ClaimCategory,
    EvidenceProvider,
    EvidenceRetrievalResult,
    EvidenceScore,
    EvidenceSourceType,
    RetrievedEvidence,
    SearchQuery,
    SearchResult,
)
from evidencechain.providers.base import SearchProvider, SearchProviderError
from evidencechain.providers.registry import get_search_provider
from evidencechain.services.admin_service import AdminService


class EvidenceServiceError(Exception):
    pass


class EvidenceProviderError(EvidenceServiceError):
    pass


class EvidenceNotFoundError(EvidenceServiceError):
    pass


class EvidenceService:
    def __init__(
        self,
        settings: Settings | None = None,
        provider: SearchProvider | None = None,
        admin_service: AdminService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider
        self.admin_service = admin_service or AdminService(self.settings)

    async def retrieve_evidence(
        self,
        claim: Claim,
        provider_name: EvidenceProvider | None = None,
        max_results: int | None = None,
    ) -> EvidenceRetrievalResult:
        try:
            provider = self.provider or get_search_provider(
                provider_name.value if provider_name else None,
                self.settings,
            )
            provider_enum = EvidenceProvider(provider.name)
        except (SearchProviderError, ValueError) as error:
            raise EvidenceProviderError(str(error)) from error
        queries = self.build_search_queries(claim)
        search_results = await self._search_queries(provider, queries)
        ranked = self.rank_evidence(claim, self.deduplicate_results(search_results))
        limit = max_results or self.settings.evidence_search_results_per_query
        evidence = ranked[:limit]
        run_id = await self._store_evidence_run(
            claim=claim,
            provider=provider_enum,
            queries=queries,
            evidence=evidence,
        )
        stored_evidence = await self.list_run_evidence(run_id)
        return EvidenceRetrievalResult(
            run_id=run_id,
            claim_id=claim.id,
            claim_text=claim.text,
            provider=provider_enum,
            queries=queries,
            evidence=stored_evidence,
        )

    async def retrieve_evidence_for_claim(
        self,
        claim_id: int,
        provider_name: EvidenceProvider | None = None,
        max_results: int | None = None,
    ) -> EvidenceRetrievalResult:
        claim = await self.get_claim(claim_id)
        return await self.retrieve_evidence(claim, provider_name, max_results)

    async def retrieve_evidence_for_text(
        self,
        claim_text: str,
        provider_name: EvidenceProvider | None = None,
        max_results: int | None = None,
    ) -> EvidenceRetrievalResult:
        claim = Claim(
            text=claim_text,
            category=ClaimCategory.scientific,
            confidence=1.0,
            start_seconds=0,
            end_seconds=0,
            source_text=claim_text,
        )
        return await self.retrieve_evidence(claim, provider_name, max_results)

    def build_search_queries(self, claim: Claim) -> list[SearchQuery]:
        normalized_claim = " ".join(claim.text.split())
        quoted_claim = f'"{normalized_claim}"'
        category_terms = {
            "medical": "clinical trial study evidence",
            "scientific": "study evidence research",
            "financial": "official data report",
            "legal": "government law statute",
            "political": "official source fact check",
            "historical": "archive university source",
            "technology": "documentation research report",
            "product": "official documentation review",
        }
        trusted_filters = ["site:.gov", "site:.edu", "site:nih.gov", "site:reuters.com"]
        query_specs = [
            (quoted_claim, "exact"),
            (f"{normalized_claim} {category_terms.get(claim.category.value, 'evidence')}", "broad"),
        ]
        query_specs.extend((f"{normalized_claim} {site}", "trusted") for site in trusted_filters)
        unique_queries: list[SearchQuery] = []
        seen: set[str] = set()
        for query, purpose in query_specs:
            if query.lower() in seen:
                continue
            seen.add(query.lower())
            unique_queries.append(SearchQuery(query=query, purpose=purpose))
            if len(unique_queries) >= self.settings.evidence_search_max_queries:
                break
        return unique_queries

    async def _search_queries(
        self,
        provider: SearchProvider,
        queries: list[SearchQuery],
    ) -> list[SearchResult]:
        tasks = [self._cached_or_search(provider, query) for query in queries]
        try:
            nested_results = await asyncio.gather(*tasks)
        except SearchProviderError as error:
            raise EvidenceProviderError(str(error)) from error
        return [result for results in nested_results for result in results]

    async def _cached_or_search(
        self,
        provider: SearchProvider,
        query: SearchQuery,
    ) -> list[SearchResult]:
        cached = await self._get_cached_results(provider.name, query.query)
        if cached is not None:
            await self.admin_service.record_search_event(provider.name, query.query, True, True)
            return cached
        try:
            results = await provider.search(
                query.query,
                count=self.settings.evidence_search_results_per_query,
            )
        except SearchProviderError as error:
            await self.admin_service.record_search_event(
                provider.name,
                query.query,
                False,
                False,
                str(error),
            )
            raise
        await self.admin_service.record_search_event(provider.name, query.query, False, True)
        await self._set_cached_results(provider.name, query.query, results)
        return results

    def deduplicate_results(self, results: list[SearchResult]) -> list[SearchResult]:
        deduplicated: list[SearchResult] = []
        seen: set[str] = set()
        for result in results:
            key = self._canonical_url(str(result.url))
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(result)
        return deduplicated

    def rank_evidence(self, claim: Claim, results: list[SearchResult]) -> list[RetrievedEvidence]:
        evidence: list[RetrievedEvidence] = []
        for result in results:
            score = self.score_result(claim, result)
            evidence.append(
                RetrievedEvidence(
                    claim_id=claim.id,
                    provider=result.provider,
                    query=result.query,
                    title=result.title,
                    url=result.url,
                    publisher=result.publisher,
                    snippet=result.snippet,
                    source_type=score.source_type,
                    credibility_score=score.credibility_score,
                    relevance_score=score.relevance_score,
                    quality_score=score.quality_score,
                    ranking_score=score.ranking_score,
                    attribution=self._build_attribution(result),
                )
            )
        return sorted(evidence, key=lambda item: item.ranking_score, reverse=True)

    def score_result(self, claim: Claim, result: SearchResult) -> EvidenceScore:
        source_type, credibility_score = self._score_source_credibility(str(result.url))
        relevance_score = self._score_relevance(claim.text, f"{result.title} {result.snippet}")
        has_title = 1.0 if result.title else 0.0
        has_snippet = 1.0 if len(result.snippet) >= 80 else 0.5 if result.snippet else 0.0
        quality_score = min(
            1.0,
            (credibility_score * 0.55) + (has_title * 0.15) + (has_snippet * 0.3),
        )
        ranking_score = min(
            1.0,
            (credibility_score * 0.45) + (relevance_score * 0.35) + (quality_score * 0.2),
        )
        return EvidenceScore(
            source_type=source_type,
            credibility_score=round(credibility_score, 3),
            relevance_score=round(relevance_score, 3),
            quality_score=round(quality_score, 3),
            ranking_score=round(ranking_score, 3),
        )

    async def get_claim(self, claim_id: int) -> Claim:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            connection.row_factory = aiosqlite.Row
            cursor = await connection.execute("SELECT * FROM claims WHERE id = ?", (claim_id,))
            row = await cursor.fetchone()
        if row is None:
            raise EvidenceNotFoundError(f"Claim {claim_id} was not found.")
        return Claim(
            id=row["id"],
            transcript_id=row["transcript_id"],
            chunk_position=row["chunk_position"],
            text=row["text"],
            category=row["category"],
            confidence=row["confidence"],
            start_seconds=row["start_seconds"],
            end_seconds=row["end_seconds"],
            source_text=row["source_text"],
            created_at=row["created_at"],
        )

    async def list_claim_evidence(self, claim_id: int) -> list[RetrievedEvidence]:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            connection.row_factory = aiosqlite.Row
            rows = await self._fetch_all(
                connection,
                """
                SELECT *
                FROM evidence_sources
                WHERE claim_id = ?
                ORDER BY ranking_score DESC, id
                """,
                (claim_id,),
            )
        return [self._evidence_from_row(row) for row in rows]

    async def list_run_evidence(self, run_id: int) -> list[RetrievedEvidence]:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            connection.row_factory = aiosqlite.Row
            rows = await self._fetch_all(
                connection,
                """
                SELECT *
                FROM evidence_sources
                WHERE run_id = ?
                ORDER BY ranking_score DESC, id
                """,
                (run_id,),
            )
        return [self._evidence_from_row(row) for row in rows]

    async def _store_evidence_run(
        self,
        claim: Claim,
        provider: EvidenceProvider,
        queries: list[SearchQuery],
        evidence: list[RetrievedEvidence],
    ) -> int:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            await connection.execute("PRAGMA foreign_keys = ON")
            cursor = await connection.execute(
                """
                INSERT INTO evidence_retrieval_runs (claim_id, claim_text, provider, queries_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    claim.id,
                    claim.text,
                    provider.value,
                    json.dumps([query.model_dump(mode="json") for query in queries]),
                ),
            )
            run_id = cursor.lastrowid
            if run_id is None:
                raise EvidenceServiceError("Failed to store evidence retrieval run.")
            for item in evidence:
                await connection.execute(
                    """
                    INSERT OR IGNORE INTO evidence_sources (
                        run_id, claim_id, provider, query, title, url, publisher, snippet,
                        source_type, credibility_score, relevance_score, quality_score,
                        ranking_score, attribution, raw_result_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        claim.id,
                        item.provider.value,
                        item.query,
                        item.title,
                        str(item.url),
                        item.publisher,
                        item.snippet,
                        item.source_type.value,
                        item.credibility_score,
                        item.relevance_score,
                        item.quality_score,
                        item.ranking_score,
                        item.attribution,
                        "{}",
                    ),
                )
            await connection.commit()
        return run_id

    async def _get_cached_results(
        self,
        provider_name: str,
        query: str,
    ) -> list[SearchResult] | None:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            connection.row_factory = aiosqlite.Row
            row = await self._fetch_one(
                connection,
                """
                SELECT response_json, expires_at
                FROM search_cache
                WHERE provider = ? AND query = ?
                """,
                (provider_name, query),
            )
        if row is None:
            return None
        expires_at = datetime.fromisoformat(str(row["expires_at"]))
        if expires_at <= datetime.now(UTC):
            return None
        adapter = TypeAdapter(list[SearchResult])
        return adapter.validate_json(str(row["response_json"]))

    async def _set_cached_results(
        self,
        provider_name: str,
        query: str,
        results: list[SearchResult],
    ) -> None:
        expires_at = datetime.now(UTC) + timedelta(
            seconds=self.settings.evidence_search_cache_ttl_seconds
        )
        payload = json.dumps([result.model_dump(mode="json") for result in results])
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            await connection.execute(
                """
                INSERT OR REPLACE INTO search_cache (provider, query, response_json, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (provider_name, query, payload, expires_at.isoformat()),
            )
            await connection.commit()

    def _score_source_credibility(self, url: str) -> tuple[EvidenceSourceType, float]:
        hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
        if hostname.endswith(".gov") or any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in self.settings.trusted_source_domains
            if domain == "gov" or domain.endswith(".gov")
        ):
            return EvidenceSourceType.government, 1.0
        academic_domains = ("edu", "ac.uk", "edu.au")
        if hostname.endswith(academic_domains) or any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in self.settings.trusted_source_domains
            if domain == "edu" or domain.endswith(".edu")
        ):
            return EvidenceSourceType.academic, 0.92
        peer_reviewed_domains = (
            "pubmed.ncbi.nlm.nih.gov",
            "ncbi.nlm.nih.gov",
            "nature.com",
            "science.org",
            "nejm.org",
            "thelancet.com",
            "bmj.com",
            "jamanetwork.com",
        )
        if any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in peer_reviewed_domains
        ):
            return EvidenceSourceType.peer_reviewed, 0.95
        journalism_domains = (
            "reuters.com",
            "apnews.com",
            "bbc.com",
            "npr.org",
            "pbs.org",
            "nytimes.com",
            "washingtonpost.com",
            "wsj.com",
        )
        if any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in journalism_domains
        ):
            return EvidenceSourceType.established_journalism, 0.82
        if any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in self.settings.trusted_source_domains
        ):
            return EvidenceSourceType.general, 0.75
        return EvidenceSourceType.general, 0.45

    def _score_relevance(self, claim_text: str, evidence_text: str) -> float:
        claim_terms = self._keywords(claim_text)
        evidence_terms = self._keywords(evidence_text)
        if not claim_terms or not evidence_terms:
            return 0.0
        overlap = claim_terms.intersection(evidence_terms)
        return min(1.0, len(overlap) / max(4, len(claim_terms)))

    def _keywords(self, value: str) -> set[str]:
        stop_words = {
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "by",
            "for",
            "from",
            "in",
            "is",
            "it",
            "of",
            "on",
            "or",
            "that",
            "the",
            "to",
            "was",
            "with",
        }
        return {
            token
            for token in re.findall(r"[a-z0-9]{3,}", value.lower())
            if token not in stop_words
        }

    def _canonical_url(self, url: str) -> str:
        parsed = urlparse(url)
        filtered_query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
        ]
        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower().removeprefix("www."),
                parsed.path.rstrip("/"),
                "",
                urlencode(filtered_query),
                "",
            )
        )

    def _build_attribution(self, result: SearchResult) -> str:
        publisher = result.publisher or urlparse(str(result.url)).hostname or "Unknown source"
        return f"{publisher}. {result.title}. {result.url}"

    async def _fetch_one(
        self,
        connection: aiosqlite.Connection,
        query: str,
        parameters: tuple[Any, ...],
    ) -> aiosqlite.Row | None:
        cursor = await connection.execute(query, parameters)
        return await cursor.fetchone()

    async def _fetch_all(
        self,
        connection: aiosqlite.Connection,
        query: str,
        parameters: tuple[Any, ...],
    ) -> list[aiosqlite.Row]:
        cursor = await connection.execute(query, parameters)
        return list(await cursor.fetchall())

    def _evidence_from_row(self, row: aiosqlite.Row) -> RetrievedEvidence:
        return RetrievedEvidence(
            id=row["id"],
            claim_id=row["claim_id"],
            provider=row["provider"],
            query=row["query"],
            title=row["title"],
            url=row["url"],
            publisher=row["publisher"],
            snippet=row["snippet"],
            source_type=row["source_type"],
            credibility_score=row["credibility_score"],
            relevance_score=row["relevance_score"],
            quality_score=row["quality_score"],
            ranking_score=row["ranking_score"],
            attribution=row["attribution"],
            retrieved_at=row["retrieved_at"],
        )
