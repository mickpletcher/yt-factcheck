# Evidence API

Evidence retrieval converts claims into search queries, retrieves web evidence, ranks quality, removes duplicates, stores results, and preserves attribution.

Brave Search is the functional provider for this stage. Tavily, Bing Search, and SerpAPI are present behind the provider abstraction but return configuration errors until their transports are implemented.

## Retrieve Evidence

```http
POST /api/v1/evidence/retrieve
```

Retrieve evidence for a stored claim:

```json
{
  "claim_id": 1,
  "provider": "brave",
  "max_results": 10
}
```

Retrieve evidence for ad hoc claim text:

```json
{
  "claim_text": "The medicine reduced symptoms in the trial.",
  "provider": "brave",
  "max_results": 10
}
```

Response:

```json
{
  "run_id": 1,
  "claim_id": 1,
  "claim_text": "The medicine reduced symptoms in the trial.",
  "provider": "brave",
  "queries": [
    {
      "query": "\"The medicine reduced symptoms in the trial.\"",
      "purpose": "exact"
    }
  ],
  "evidence": [
    {
      "id": 1,
      "claim_id": 1,
      "provider": "brave",
      "query": "\"The medicine reduced symptoms in the trial.\"",
      "title": "Example Study",
      "url": "https://www.nih.gov/example",
      "publisher": "NIH",
      "snippet": "A study summary.",
      "source_type": "government",
      "credibility_score": 1.0,
      "relevance_score": 0.75,
      "quality_score": 0.95,
      "ranking_score": 0.9,
      "attribution": "NIH. Example Study. https://www.nih.gov/example",
      "retrieved_at": "2026-05-25T21:00:00Z"
    }
  ]
}
```

## List Claim Evidence

```http
GET /api/v1/evidence/claims/{claim_id}
```

Returns stored evidence for the claim, sorted by ranking score.

## Ranking

Evidence is ranked using:

- Source credibility: government, academic, peer reviewed, established journalism, then general web sources.
- Claim relevance: keyword overlap between claim text and title plus snippet.
- Result quality: title and snippet completeness.

## Storage

The database stores:

- Evidence retrieval runs.
- Retrieved evidence sources.
- Provider, query, URL, title, publisher, snippet, source type, scores, and attribution.
- Cached search responses by provider and query.

## Brave Configuration

Set `BRAVE_SEARCH_API_KEY` in `.env`.

The Brave web search provider calls:

```text
https://api.search.brave.com/res/v1/web/search
```

with the `X-Subscription-Token` header.
