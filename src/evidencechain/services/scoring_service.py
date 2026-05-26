import json
from typing import Any

import aiosqlite
from pydantic import TypeAdapter

from evidencechain.core.config import Settings, get_settings
from evidencechain.models.factcheck import (
    Claim,
    EvidenceComparison,
    EvidenceRelationship,
    RetrievedEvidence,
    ScoringResult,
    Verdict,
    VerdictSafeguards,
)
from evidencechain.services.citation_validator import CitationValidationError, CitationValidator
from evidencechain.services.evidence_comparison_service import EvidenceComparisonService
from evidencechain.services.evidence_service import EvidenceNotFoundError, EvidenceService


class ScoringServiceError(Exception):
    pass


class ScoringNotFoundError(ScoringServiceError):
    pass


class ScoringEngine:
    def __init__(
        self,
        comparison_service: EvidenceComparisonService | None = None,
        citation_validator: CitationValidator | None = None,
    ) -> None:
        self.comparison_service = comparison_service or EvidenceComparisonService()
        self.citation_validator = citation_validator or CitationValidator()

    def score(
        self,
        claim: Claim,
        evidence: list[RetrievedEvidence],
        min_evidence: int = 2,
    ) -> ScoringResult:
        claim_id = self._require_claim_id(claim)
        stored_evidence = [
            item for item in evidence if item.id is not None and item.claim_id == claim_id
        ]
        blocked_reasons: list[str] = []
        if len(stored_evidence) < min_evidence:
            blocked_reasons.append(
                "Insufficient stored evidence: "
                f"found {len(stored_evidence)}, required {min_evidence}."
            )

        comparisons = self.comparison_service.compare(claim, stored_evidence)
        support = self._weighted_score(stored_evidence, comparisons, EvidenceRelationship.supports)
        contradiction = self._weighted_score(
            stored_evidence,
            comparisons,
            EvidenceRelationship.contradicts,
        )
        cited_ids = self._select_citations(stored_evidence, comparisons)
        citation_validation_passed = self._validate_citations(claim_id, stored_evidence, cited_ids)
        if not citation_validation_passed:
            blocked_reasons.append(
                "Citation validation failed or no stored evidence could be cited."
            )

        has_sufficient_evidence = (
            len(stored_evidence) >= min_evidence and citation_validation_passed
        )
        verdict = self._determine_verdict(
            has_sufficient_evidence,
            support,
            contradiction,
            comparisons,
        )
        confidence = self._confidence(
            has_sufficient_evidence,
            support,
            contradiction,
            stored_evidence,
        )
        safeguards = VerdictSafeguards(
            stored_evidence_only=len(stored_evidence) == len(evidence),
            has_sufficient_evidence=has_sufficient_evidence,
            citation_validation_passed=citation_validation_passed,
            blocked_reasons=blocked_reasons,
        )
        return ScoringResult(
            claim=claim,
            verdict=verdict,
            confidence=confidence,
            explanation=self._explain(verdict, support, contradiction, safeguards),
            evidence=stored_evidence,
            comparisons=comparisons,
            cited_evidence_ids=cited_ids,
            safeguards=safeguards,
        )

    def _determine_verdict(
        self,
        has_sufficient_evidence: bool,
        support: float,
        contradiction: float,
        comparisons: list[EvidenceComparison],
    ) -> Verdict:
        if not has_sufficient_evidence:
            return Verdict.unverified
        if support >= 0.7 and contradiction < 0.2:
            return Verdict.true
        if support >= 0.45 and contradiction < 0.3:
            return Verdict.mostly_true
        if contradiction >= 0.7 and support < 0.2:
            return Verdict.false
        if contradiction >= 0.45 and support < 0.4:
            return Verdict.misleading
        if support >= 0.35 and contradiction >= 0.35:
            return Verdict.needs_context
        if any(item.relationship != EvidenceRelationship.neutral for item in comparisons):
            return Verdict.needs_context
        return Verdict.unverified

    def _confidence(
        self,
        has_sufficient_evidence: bool,
        support: float,
        contradiction: float,
        evidence: list[RetrievedEvidence],
    ) -> float:
        if not has_sufficient_evidence:
            return 0.0
        separation = abs(support - contradiction)
        average_quality = sum(item.ranking_score for item in evidence) / len(evidence)
        confidence = (separation * 0.65) + (average_quality * 0.35)
        return round(min(1.0, confidence), 3)

    def _weighted_score(
        self,
        evidence: list[RetrievedEvidence],
        comparisons: list[EvidenceComparison],
        relationship: EvidenceRelationship,
    ) -> float:
        evidence_by_id = {item.id: item for item in evidence}
        matching = [item for item in comparisons if item.relationship == relationship]
        if not matching:
            return 0.0
        total = 0.0
        for comparison in matching:
            item = evidence_by_id.get(comparison.evidence_id)
            if item is None:
                continue
            total += item.ranking_score * abs(comparison.stance_score)
        return round(min(1.0, total / max(1, len(evidence))), 3)

    def _select_citations(
        self,
        evidence: list[RetrievedEvidence],
        comparisons: list[EvidenceComparison],
    ) -> list[int]:
        comparison_by_id = {item.evidence_id: item for item in comparisons}
        cited: list[RetrievedEvidence] = []
        for item in evidence:
            if item.id is None:
                continue
            comparison = comparison_by_id.get(item.id)
            if comparison and comparison.relationship != EvidenceRelationship.neutral:
                cited.append(item)
        if not cited:
            cited = evidence[:2]
        return [item.id for item in cited[:5] if item.id is not None]

    def _validate_citations(
        self,
        claim_id: int,
        evidence: list[RetrievedEvidence],
        cited_ids: list[int],
    ) -> bool:
        try:
            self.citation_validator.validate(claim_id, evidence, cited_ids)
        except CitationValidationError:
            return False
        return True

    def _explain(
        self,
        verdict: Verdict,
        support: float,
        contradiction: float,
        safeguards: VerdictSafeguards,
    ) -> str:
        if not safeguards.has_sufficient_evidence:
            return (
                "Insufficient stored evidence. The engine will not infer a factual verdict "
                "without validated stored citations."
            )
        return (
            f"Verdict is {verdict.value} with support score {support:.2f} and "
            f"contradiction score {contradiction:.2f}, based only on stored evidence objects."
        )

    def _require_claim_id(self, claim: Claim) -> int:
        if claim.id is None:
            raise ScoringServiceError("Scoring requires a stored claim id.")
        return claim.id


class ScoringService:
    def __init__(
        self,
        settings: Settings | None = None,
        evidence_service: EvidenceService | None = None,
        engine: ScoringEngine | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.evidence_service = evidence_service or EvidenceService(settings=self.settings)
        self.engine = engine or ScoringEngine()

    async def score_claim(self, claim_id: int, min_evidence: int = 2) -> ScoringResult:
        try:
            claim = await self.evidence_service.get_claim(claim_id)
        except EvidenceNotFoundError as error:
            raise ScoringNotFoundError(str(error)) from error
        evidence = await self.evidence_service.list_claim_evidence(claim_id)
        result = self.engine.score(claim, evidence, min_evidence)
        return await self._store_result(result)

    async def list_results(self, claim_id: int) -> list[ScoringResult]:
        try:
            claim = await self.evidence_service.get_claim(claim_id)
        except EvidenceNotFoundError as error:
            raise ScoringNotFoundError(str(error)) from error
        evidence = await self.evidence_service.list_claim_evidence(claim_id)
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            connection.row_factory = aiosqlite.Row
            rows = await self._fetch_all(
                connection,
                """
                SELECT *
                FROM scoring_results
                WHERE claim_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (claim_id,),
            )
        return [self._result_from_row(row, claim, evidence) for row in rows]

    async def _store_result(self, result: ScoringResult) -> ScoringResult:
        claim_id = self.engine._require_claim_id(result.claim)
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            cursor = await connection.execute(
                """
                INSERT INTO scoring_results (
                    claim_id, verdict, confidence, explanation, cited_evidence_ids_json,
                    comparisons_json, safeguards_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    result.verdict.value,
                    result.confidence,
                    result.explanation,
                    json.dumps(result.cited_evidence_ids),
                    json.dumps([item.model_dump(mode="json") for item in result.comparisons]),
                    result.safeguards.model_dump_json(),
                ),
            )
            result_id = cursor.lastrowid
            await connection.commit()
        stored = await self.list_results(claim_id)
        for item in stored:
            if item.id == result_id:
                return item
        raise ScoringServiceError("Failed to store scoring result.")

    def _result_from_row(
        self,
        row: aiosqlite.Row,
        claim: Claim,
        evidence: list[RetrievedEvidence],
    ) -> ScoringResult:
        comparison_adapter = TypeAdapter(list[EvidenceComparison])
        cited_ids = TypeAdapter(list[int]).validate_json(str(row["cited_evidence_ids_json"]))
        comparisons = comparison_adapter.validate_json(str(row["comparisons_json"]))
        safeguards = VerdictSafeguards.model_validate_json(str(row["safeguards_json"]))
        cited_id_set = set(cited_ids)
        cited_evidence = [item for item in evidence if item.id in cited_id_set]
        return ScoringResult(
            id=row["id"],
            claim=claim,
            verdict=row["verdict"],
            confidence=row["confidence"],
            explanation=row["explanation"],
            evidence=cited_evidence,
            comparisons=comparisons,
            cited_evidence_ids=cited_ids,
            safeguards=safeguards,
            created_at=row["created_at"],
        )

    async def _fetch_all(
        self,
        connection: aiosqlite.Connection,
        query: str,
        parameters: tuple[Any, ...],
    ) -> list[aiosqlite.Row]:
        cursor = await connection.execute(query, parameters)
        return list(await cursor.fetchall())
