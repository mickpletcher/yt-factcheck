# Reports API

Reports turn stored transcript, claim, evidence, and scoring rows into public sharing exports.

The report engine does not create verdicts or fetch evidence. It renders the latest stored scoring result for each claim and links the evidence rows already stored for that claim.

## JSON Report

```http
GET /api/v1/reports/transcripts/{transcript_id}
```

Returns a structured report export with:

- `generated_at`
- video metadata
- verdict summary buckets
- claim summaries
- confidence indicators
- citations
- linked evidence

## HTML Report

```http
GET /api/v1/reports/transcripts/{transcript_id}.html
```

Returns a readable public HTML page with video metadata, verdict charts, claim summaries, confidence, timestamps, citations, and evidence links.

## Markdown Report

```http
GET /api/v1/reports/transcripts/{transcript_id}.md
```

Returns a Markdown report for GitHub, notes, or static publishing.

## Export Report To Disk

```http
POST /api/v1/reports/transcripts/{transcript_id}/exports/{report_format}
```

Supported `report_format` values:

- `html`
- `markdown`
- `json`

Response:

```json
{
  "path": "reports/transcript-1.html",
  "format": "html"
}
```

Exports are written under `reports/` by default.
