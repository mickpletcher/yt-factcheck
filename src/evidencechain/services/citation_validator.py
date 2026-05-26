from evidencechain.models.factcheck import RetrievedEvidence


class CitationValidationError(Exception):
    pass


class CitationValidator:
    def validate(
        self,
        claim_id: int,
        evidence: list[RetrievedEvidence],
        cited_evidence_ids: list[int],
    ) -> None:
        if not cited_evidence_ids:
            raise CitationValidationError("Verdict must cite at least one stored evidence object.")

        stored_by_id = {item.id: item for item in evidence if item.id is not None}
        missing_ids = [
            evidence_id
            for evidence_id in cited_evidence_ids
            if evidence_id not in stored_by_id
        ]
        if missing_ids:
            raise CitationValidationError(
                f"Verdict cites evidence that is not stored: {missing_ids}."
            )

        invalid_claim_ids = [
            evidence_id
            for evidence_id in cited_evidence_ids
            if stored_by_id[evidence_id].claim_id != claim_id
        ]
        if invalid_claim_ids:
            raise CitationValidationError(
                f"Verdict cites evidence from another claim: {invalid_claim_ids}."
            )

        incomplete_ids = [
            evidence_id
            for evidence_id in cited_evidence_ids
            if not stored_by_id[evidence_id].url
            or not stored_by_id[evidence_id].attribution
            or not stored_by_id[evidence_id].snippet
        ]
        if incomplete_ids:
            raise CitationValidationError(
                f"Verdict cites incomplete evidence objects: {incomplete_ids}."
            )
