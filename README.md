# EvidenceChain

EvidenceChain is a Python 3.12 FastAPI backend for AI powered fact checking of YouTube videos.

The intended workflow is:

1. Extract a YouTube transcript.
2. Identify timestamped claims.
3. Retrieve evidence from trusted sources.
4. Compare evidence against each claim.
5. Score an explainable verdict with stored evidence citations.
6. Generate a timestamped verification report with citations.

Claim extraction is implemented behind a minimal pluggable LLM provider interface. Evidence retrieval is implemented behind a swappable search provider interface. Brave Search is functional now. Tavily, Bing Search, and SerpAPI are wired as optional provider slots but are not implemented yet.

## Stack

- Python 3.12
- FastAPI
- Pydantic v2
- SQLite with async access through `aiosqlite`
- `.env` configuration through `pydantic-settings`
- Structured JSON logging
- pytest
- Ruff
- mypy
- React
- Vite
- TypeScript
- Docker
- GitHub Actions

## Project Layout

```text
.
├── .github/workflows/ci.yml
├── reports/
├── frontend/
├── storage/
├── src/evidencechain/
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── pipelines/
│   ├── prompts/
│   ├── reports/
│   ├── services/
│   ├── storage/
│   └── utils/
└── tests/
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Run Locally

```powershell
uvicorn evidencechain.main:create_app --factory --reload
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "evidencechain"
}
```

## Run Frontend

The React dashboard lives in `frontend/`.

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`, so start the FastAPI backend first.

The dashboard supports:

- YouTube URL transcript ingestion
- Transcript file upload
- Live client side pipeline progress
- Searchable claims
- Expandable evidence sections
- Timestamp links back to YouTube
- Verdict inspection
- HTML, Markdown, and JSON report viewing

## Test

```powershell
pytest
ruff check .
mypy src
cd frontend
npm run build
```

## Docker

Build:

```powershell
docker build -t evidencechain .
```

Run:

```powershell
docker run --rm -p 8000:8000 --env-file .env evidencechain
```

## Configuration

Configuration is loaded from environment variables and `.env`.

See `.env.example` for supported settings.

| Variable | Purpose |
| --- | --- |
| `APP_NAME` | FastAPI app name |
| `APP_ENV` | Runtime environment label |
| `APP_DEBUG` | Enables FastAPI debug mode |
| `LOG_LEVEL` | Python logging level |
| `DATABASE_URL` | SQLite database URL |
| `TRUSTED_SOURCE_DOMAINS` | Comma separated trusted evidence domains |
| `TRANSCRIPT_CHUNK_MAX_CHARS` | Maximum transcript characters per chunk |
| `TRANSCRIPT_CHUNK_OVERLAP_SEGMENTS` | Number of transcript segments repeated between chunks |
| `TRANSCRIPT_RETRY_ATTEMPTS` | Retry attempts for YouTube metadata and caption fetches |
| `TRANSCRIPT_RETRY_BACKOFF_SECONDS` | Base retry backoff in seconds |
| `TRANSCRIPT_FETCH_TIMEOUT_SECONDS` | HTTP timeout for caption download |
| `LLM_PROVIDER` | Default claim extraction provider name: `openai`, `anthropic`, or `ollama` |
| `OPENAI_MODEL` | OpenAI model setting reserved for the provider implementation |
| `ANTHROPIC_MODEL` | Anthropic model setting reserved for the provider implementation |
| `OLLAMA_MODEL` | Ollama model setting reserved for the provider implementation |
| `SEARCH_PROVIDER` | Default evidence search provider. Use `brave` for now |
| `BRAVE_SEARCH_API_KEY` | Required for live Brave Search evidence retrieval |
| `BRAVE_SEARCH_ENDPOINT` | Brave web search endpoint |
| `TAVILY_API_KEY` | Reserved for optional Tavily provider support |
| `BING_SEARCH_API_KEY` | Reserved for optional Bing Search provider support |
| `SERPAPI_API_KEY` | Reserved for optional SerpAPI provider support |
| `EVIDENCE_SEARCH_TIMEOUT_SECONDS` | HTTP timeout for evidence search |
| `EVIDENCE_SEARCH_RETRY_ATTEMPTS` | Retry attempts for evidence search |
| `EVIDENCE_SEARCH_RETRY_BACKOFF_SECONDS` | Base retry backoff for evidence search |
| `EVIDENCE_SEARCH_RATE_LIMIT_PER_SECOND` | Per provider search request rate limit |
| `EVIDENCE_SEARCH_CACHE_TTL_SECONDS` | SQLite search cache lifetime |
| `EVIDENCE_SEARCH_MAX_QUERIES` | Maximum optimized queries generated per claim |
| `EVIDENCE_SEARCH_RESULTS_PER_QUERY` | Results requested for each generated query |

Only `sqlite+aiosqlite` database URLs are supported initially.

## Current API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Service health check |
| `POST` | `/api/v1/transcripts/from-url` | Create a stored transcript from a YouTube URL |
| `POST` | `/api/v1/transcripts/upload` | Upload a `.txt`, `.srt`, `.vtt`, or JSON transcript fallback |
| `GET` | `/api/v1/transcripts/{transcript_id}` | Return stored transcript metadata, segments, and chunks |
| `GET` | `/api/v1/transcripts/{transcript_id}/chunks` | Return stored chunks for a transcript |
| `POST` | `/api/v1/claims/extract` | Extract factual claims from stored transcript chunks |
| `GET` | `/api/v1/claims/transcripts/{transcript_id}` | Return claims stored for a transcript |
| `GET` | `/api/v1/claims/{claim_id}` | Return one stored claim |
| `POST` | `/api/v1/evidence/retrieve` | Retrieve, rank, dedupe, and store evidence for a claim |
| `GET` | `/api/v1/evidence/claims/{claim_id}` | Return stored evidence for a claim |
| `POST` | `/api/v1/scoring/score` | Score a stored claim using stored evidence |
| `POST` | `/api/v1/scoring/claims/{claim_id}` | Score a stored claim by path id |
| `GET` | `/api/v1/scoring/claims/{claim_id}` | Return stored scoring results for a claim |
| `GET` | `/api/v1/reports/transcripts/{transcript_id}` | Return a structured JSON report |
| `GET` | `/api/v1/reports/transcripts/{transcript_id}.html` | Return a public HTML report |
| `GET` | `/api/v1/reports/transcripts/{transcript_id}.md` | Return a Markdown report |
| `POST` | `/api/v1/reports/transcripts/{transcript_id}/exports/{report_format}` | Export a report to disk |

## Development Notes

Transcript ingestion is implemented in `src/evidencechain/services/transcript_service.py`. It extracts YouTube metadata through `yt-dlp`, retrieves captions when available, normalizes uploaded fallback transcript files, preserves timestamps when present, stores transcript records in SQLite, and creates timestamped chunks.

Claim extraction is implemented in `src/evidencechain/services/claim_service.py`. It processes transcript chunks, prompts an injected LLM provider for structured JSON, validates provider output with Pydantic, stores claims in SQLite, preserves timestamps, and categorizes claims as scientific, historical, medical, political, financial, legal, technology, or product.

Evidence retrieval is implemented in `src/evidencechain/services/evidence_service.py`. It converts a claim into optimized search queries, runs async parallel searches, caches provider results in SQLite, removes duplicate URLs, scores source credibility and relevance, stores evidence retrieval runs, and preserves source attribution.

Verdict scoring is implemented in `src/evidencechain/services/scoring_service.py`. It compares stored evidence snippets against stored claims, assigns support or contradiction relationships, validates cited evidence IDs, blocks fabricated citations, and returns `Unverified` when evidence is insufficient.

Report rendering is implemented in `src/evidencechain/services/report_service.py`. It builds one JSON report object, then renders HTML, Markdown, or JSON exports with video metadata, verdict summaries, confidence indicators, citations, and linked evidence.

Detailed API docs are in `docs/transcripts-api.md`, `docs/claims-api.md`, `docs/evidence-api.md`, `docs/scoring-api.md`, and `docs/reports-api.md`.
