# EvidenceChain

EvidenceChain is a Python 3.12 FastAPI backend for AI powered fact checking of YouTube videos.

The intended workflow is:

1. Extract a YouTube transcript.
2. Identify timestamped claims.
3. Retrieve evidence from trusted sources.
4. Compare evidence against each claim.
5. Generate a timestamped verification report with citations.

AI logic is not implemented yet. This repository currently focuses on the production project structure, service boundaries, configuration, logging, database startup, tests, Docker, and CI.

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

Only `sqlite+aiosqlite` database URLs are supported initially.

## Current API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Service health check |

## Development Notes

The service classes in `src/evidencechain/services/` are placeholders by design. They define the future boundaries for transcript extraction, claim extraction, evidence retrieval, and verification.

The pipeline in `src/evidencechain/pipelines/factcheck_pipeline.py` shows the intended orchestration flow without implementing AI behavior yet.
