# Scoring API

Verdict scoring compares stored claims against stored evidence objects.

The scoring engine does not create sources. It only cites rows already stored in `evidence_sources`. If evidence is missing, incomplete, or not linked to the claim, the result is marked `Unverified` with explicit safeguard reasons.

## Verdicts

- `True`
- `Mostly True`
- `Misleading`
- `Unverified`
- `False`
- `Needs Context`

## Score Claim

```http
POST /api/v1/scoring/score
```

Request:

```json
{
  "claim_id": 1,
  "min_evidence": 2
}
```

Response:

```json
{
  "id": 1,
  "claim": {
    "id": 1,
    "text": "The medicine reduced symptoms in the trial.",
    "category": "medical",
    "confidence": 0.86,
    "start_seconds": 1.0,
    "end_seconds": 3.0,
    "source_text": "The medicine reduced symptoms in the trial."
  },
  "verdict": "True",
  "confidence": 0.82,
  "explanation": "Verdict is True with support score 0.89 and contradiction score 0.00, based only on stored evidence objects.",
  "evidence": [
    {
      "id": 1,
      "claim_id": 1,
      "provider": "brave",
      "query": "\"The medicine reduced symptoms in the trial.\"",
      "title": "Example Study",
      "url": "https://www.nih.gov/example",
      "publisher": "NIH",
      "snippet": "A study found the medicine reduced symptoms in the trial.",
      "source_type": "government",
      "credibility_score": 1.0,
      "relevance_score": 1.0,
      "quality_score": 0.95,
      "ranking_score": 0.9,
      "attribution": "NIH. Example Study. https://www.nih.gov/example",
      "retrieved_at": "2026-05-25T22:00:00Z"
    }
  ],
  "comparisons": [
    {
      "evidence_id": 1,
      "relationship": "supports",
      "relevance_score": 1.0,
      "stance_score": 1.0,
      "explanation": "Stored evidence 1 is relevant and appears to support the claim based on its title and snippet."
    }
  ],
  "cited_evidence_ids": [1, 2],
  "safeguards": {
    "stored_evidence_only": true,
    "has_sufficient_evidence": true,
    "citation_validation_passed": true,
    "blocked_reasons": []
  },
  "created_at": "2026-05-25T22:00:00Z"
}
```

## Score Claim By Path

```http
POST /api/v1/scoring/claims/{claim_id}
```

Scores the claim with the default minimum evidence threshold.

## List Claim Scores

```http
GET /api/v1/scoring/claims/{claim_id}
```

Returns stored scoring results for the claim, newest first.

## Safeguards

The scorer enforces:

- Stored claim IDs only.
- Stored evidence rows only.
- Evidence must be linked to the scored claim.
- Cited evidence must include URL, attribution, and snippet.
- Insufficient evidence returns `Unverified`.
- No source text is generated beyond stored title, snippet, URL, publisher, and attribution fields.
