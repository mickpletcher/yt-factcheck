import re

from evidencechain.models.factcheck import (
    Claim,
    EvidenceComparison,
    EvidenceRelationship,
    RetrievedEvidence,
)


class EvidenceComparisonService:
    def compare(self, claim: Claim, evidence: list[RetrievedEvidence]) -> list[EvidenceComparison]:
        comparisons: list[EvidenceComparison] = []
        for item in evidence:
            if item.id is None:
                continue
            relevance = self._score_relevance(claim.text, f"{item.title} {item.snippet}")
            stance = self._score_stance(claim.text, item.snippet, relevance)
            relationship = EvidenceRelationship.neutral
            if relevance >= 0.25 and stance >= 0.25:
                relationship = EvidenceRelationship.supports
            elif relevance >= 0.25 and stance <= -0.25:
                relationship = EvidenceRelationship.contradicts
            comparisons.append(
                EvidenceComparison(
                    evidence_id=item.id,
                    relationship=relationship,
                    relevance_score=round(relevance, 3),
                    stance_score=round(stance, 3),
                    explanation=self._explain(item, relationship, relevance, stance),
                )
            )
        return comparisons

    def _score_stance(self, claim_text: str, evidence_text: str, relevance: float) -> float:
        if relevance < 0.15:
            return 0.0

        claim_negative = self._has_negation(claim_text)
        evidence_negative = self._has_negation(evidence_text)
        if claim_negative != evidence_negative:
            return -min(1.0, 0.45 + relevance)

        contradiction_phrases = (
            "no evidence",
            "not supported",
            "did not",
            "does not",
            "failed to",
            "false",
            "incorrect",
            "debunked",
            "refuted",
            "contradicts",
        )
        support_phrases = (
            "evidence shows",
            "study found",
            "confirmed",
            "reported",
            "according to",
            "supports",
            "reduced",
            "increased",
        )
        normalized = evidence_text.lower()
        if any(phrase in normalized for phrase in contradiction_phrases):
            return -min(1.0, 0.35 + relevance)
        if any(phrase in normalized for phrase in support_phrases):
            return min(1.0, 0.25 + relevance)
        return min(0.55, relevance)

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
            "were",
            "with",
        }
        return {
            token
            for token in re.findall(r"[a-z0-9]{3,}", value.lower())
            if token not in stop_words
        }

    def _has_negation(self, value: str) -> bool:
        pattern = r"\b(no|not|never|none|without|didn't|doesn't|isn't|aren't)\b"
        return bool(re.search(pattern, value.lower()))

    def _explain(
        self,
        evidence: RetrievedEvidence,
        relationship: EvidenceRelationship,
        relevance: float,
        stance: float,
    ) -> str:
        if relationship == EvidenceRelationship.supports:
            return (
                f"Stored evidence {evidence.id} is relevant and appears to support the claim "
                f"based on its title and snippet."
            )
        if relationship == EvidenceRelationship.contradicts:
            return (
                f"Stored evidence {evidence.id} is relevant and appears to contradict the claim "
                f"based on negation or refuting language."
            )
        return (
            f"Stored evidence {evidence.id} was not strong enough for support or contradiction "
            f"(relevance {relevance:.2f}, stance {stance:.2f})."
        )
