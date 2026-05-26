# Claim API

Base path: `/api/v1`

## Extract Claims

`POST /claims/extract`

Processes stored transcript chunks and extracts factual claims through the configured LLM provider.

Request:

```json
{
  "transcript_id": 1,
  "provider": "openai"
}
```

`provider` is optional. Supported values are `openai`, `anthropic`, `ollama`, and `lmstudio`.
Pass comma separated values to use request level failover.

Success: `200 OK`

```json
{
  "transcript_id": 1,
  "provider": "openai",
  "prompt_version": "claim-extraction-v1",
  "claims": [
    {
      "id": 1,
      "transcript_id": 1,
      "chunk_position": 0,
      "text": "The device uses a lithium battery.",
      "category": "technology",
      "confidence": 0.91,
      "start_seconds": 4.0,
      "end_seconds": 9.0,
      "source_text": "The device uses a lithium battery.",
      "created_at": "2026-05-25T21:00:00"
    }
  ]
}
```

Errors:

| Status | Meaning |
| --- | --- |
| `404` | Transcript ID was not found |
| `502` | Provider name is invalid or the provider call failed |

## Provider Health

`GET /health/providers`

Returns the configured LLM provider health state. With failover configured, each provider is checked separately.

## List Transcript Claims

`GET /claims/transcripts/{transcript_id}`

Returns stored claims for a transcript.

## Get Claim

`GET /claims/{claim_id}`

Returns one stored claim.

Error:

| Status | Meaning |
| --- | --- |
| `404` | Claim ID was not found |

## Claim Categories

- `scientific`
- `historical`
- `medical`
- `political`
- `financial`
- `legal`
- `technology`
- `product`

Provider output is validated against Pydantic schemas before claims are returned or stored.
