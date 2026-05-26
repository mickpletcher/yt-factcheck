# EvidenceChain

EvidenceChain is a Python 3.12 FastAPI backend for AI powered fact checking of YouTube videos.

The intended workflow is:

1. Extract a YouTube transcript.
2. Identify timestamped claims.
3. Retrieve evidence from trusted sources.
4. Compare evidence against each claim.
5. Generate a timestamped verification report with citations.

Claim extraction is implemented behind a minimal pluggable LLM provider interface. Provider transports are interface stubs for now and are intended to be replaced by the full provider system in prompt 08.

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
- Docker
- GitHub Actions

## Project Layout

```text
.
├── .github/workflows/ci.yml
├── reports/
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

## Test

```powershell
pytest
ruff check .
mypy src
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

## Development Notes

Transcript ingestion is implemented in `src/evidencechain/services/transcript_service.py`. It extracts YouTube metadata through `yt-dlp`, retrieves captions when available, normalizes uploaded fallback transcript files, preserves timestamps when present, stores transcript records in SQLite, and creates timestamped chunks.

Claim extraction is implemented in `src/evidencechain/services/claim_service.py`. It processes transcript chunks, prompts an injected LLM provider for structured JSON, validates provider output with Pydantic, stores claims in SQLite, preserves timestamps, and categorizes claims as scientific, historical, medical, political, financial, legal, technology, or product.

Detailed API docs are in `docs/transcripts-api.md` and `docs/claims-api.md`.
