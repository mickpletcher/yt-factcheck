# EvidenceChain

EvidenceChain is a YouTube fact-checking app.

You give it a YouTube video or transcript. It finds factual claims, searches for evidence, scores each claim, and creates a report with citations.

The repo contains two parts:

- A Python FastAPI backend.
- A React dashboard frontend.

## What It Does

EvidenceChain follows this workflow:

1. Gets a transcript from a YouTube video or uploaded transcript file.
2. Splits the transcript into timestamped chunks.
3. Uses an LLM to find factual claims.
4. Searches the web for evidence.
5. Compares the evidence to each claim.
6. Scores each claim with an explainable verdict.
7. Creates JSON, HTML, and Markdown reports.

## Current Status

This is a working MVP.

Working now:

- YouTube transcript ingestion
- Transcript upload fallback
- Claim extraction
- LLM providers for OpenAI, Anthropic, Ollama, and LM Studio
- Brave Search evidence retrieval
- Evidence scoring
- Report generation
- Full pipeline queue API
- React dashboard
- Docker deployment
- GitHub Actions CI

Important limitation:

Brave Search is the only working live search provider right now. Tavily, Bing Search, and SerpAPI are reserved in configuration, but not implemented yet.

## Requirements

Install these before starting:

- Python 3.12
- Node.js 20 or newer
- Git
- VS Code or another editor

Optional:

- Docker Desktop, if you want to run the container version.
- An OpenAI, Anthropic, Ollama, or LM Studio setup for claim extraction.
- A Brave Search API key for live evidence search.

## First Time Setup

Open PowerShell in the repo folder:

```powershell
cd "C:\Users\mick0\OneDrive\Documents\Code & Dev\GitHub\yt-factcheck"
```

Create a Python virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install Python dependencies:

```powershell
pip install -r requirements.txt
```

Install this repo as a local Python package:

```powershell
pip install -e .
```

Create your local settings file:

```powershell
Copy-Item .env.example .env
```

The `.env` file is your local configuration. Do not commit real API keys.

## Configure API Keys

Open `.env`.

For the simplest live cloud setup, fill in:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_key_here
BRAVE_SEARCH_API_KEY=your_brave_search_key_here
```

For Anthropic:

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_key_here
BRAVE_SEARCH_API_KEY=your_brave_search_key_here
```

For Ollama:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
BRAVE_SEARCH_API_KEY=your_brave_search_key_here
```

For LM Studio:

```env
LLM_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_MODEL=local-model
BRAVE_SEARCH_API_KEY=your_brave_search_key_here
```

Without an LLM provider and search key, you can still run parts of the app, tests, and mocked workflows. Full live fact-checking needs both.

## Run The Backend

Start the backend API:

```powershell
uvicorn evidencechain.main:create_app --factory --reload
```

Leave this PowerShell window open.

Check that the backend works:

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

The backend is now running at:

```text
http://127.0.0.1:8000
```

## Run The Frontend

Open a second PowerShell window.

Go to the frontend folder:

```powershell
cd "C:\Users\mick0\OneDrive\Documents\Code & Dev\GitHub\yt-factcheck\frontend"
```

Install frontend dependencies:

```powershell
npm install
```

Start the dashboard:

```powershell
npm run dev
```

Open this URL in your browser:

```text
http://127.0.0.1:5173
```

The frontend sends API requests to the backend at `http://127.0.0.1:8000`.

## Using The App

The dashboard supports:

- Paste a YouTube URL.
- Upload a transcript file.
- Watch staged progress while it runs transcript, claim, evidence, scoring, and report endpoints.
- Review extracted claims.
- Expand evidence for each claim.
- Open timestamp links back to YouTube.
- Inspect verdicts.
- View HTML, Markdown, and JSON reports.

Transcript uploads support:

- `.txt`
- `.srt`
- `.vtt`
- JSON

## Run Tests

From the repo root with the virtual environment activated:

```powershell
pytest
```

Run lint:

```powershell
ruff check .
```

Run type checks:

```powershell
mypy src
```

Build the frontend:

```powershell
cd frontend
npm run build
```

## Run With Docker

Use this if you want the app in containers.

From the repo root:

```powershell
Copy-Item .env.local.example .env
.\scripts\start-local.ps1
```

Open:

```text
http://127.0.0.1:8080
```

Health checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/healthz
Invoke-RestMethod http://127.0.0.1:8080/api/v1/health
```

More deployment details are in `docs/deployment.md`.

## Project Layout

```text
.
├── .github/workflows/     GitHub Actions workflows
├── docs/                  API and deployment docs
├── frontend/              React dashboard
├── nginx/                 Nginx config for Docker
├── reports/               Exported reports
├── scripts/               Local and deployment scripts
├── specs/                 Spec workflow packages
├── src/evidencechain/     Backend source code
├── storage/               Local SQLite database location
├── tests/                 Backend tests
├── assessment.md          Current project assessment
├── completed-upgrades.md  Completed upgrade log
├── future-upgrades.md     Active upgrade backlog
└── README.md              This guide
```

## Main Backend Folders

```text
src/evidencechain/
├── api/        FastAPI routes
├── core/       App settings
├── models/     Pydantic models
├── pipelines/  Full fact-check job pipeline
├── prompts/    LLM prompts
├── providers/  LLM and search provider integrations
├── reports/    Report templates
├── services/   Main app logic
├── storage/    SQLite setup
└── utils/      Shared helpers
```

## Important Files

| File | Purpose |
| --- | --- |
| `.env.example` | Full local settings template |
| `.env.local.example` | Local Docker settings template |
| `.env.production.example` | Production settings template |
| `Dockerfile` | Production API and frontend image build |
| `docker-compose.yml` | Local or VPS container stack |
| `assessment.md` | Current project assessment |
| `future-upgrades.md` | Active upgrade backlog |
| `completed-upgrades.md` | Completed upgrade history |
| `CHANGELOG.md` | Release and change history |
| `docs/deployment.md` | Deployment guide |

## API Summary

The API is under `/api/v1`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Service health check |
| `GET` | `/api/v1/health/providers` | LLM provider health checks |
| `POST` | `/api/v1/transcripts/from-url` | Create a transcript from a YouTube URL |
| `POST` | `/api/v1/transcripts/upload` | Upload a transcript file |
| `GET` | `/api/v1/transcripts/{transcript_id}` | Get transcript details |
| `POST` | `/api/v1/claims/extract` | Extract claims from transcript chunks |
| `GET` | `/api/v1/claims/transcripts/{transcript_id}` | Get claims for a transcript |
| `POST` | `/api/v1/evidence/retrieve` | Retrieve evidence for a claim |
| `GET` | `/api/v1/evidence/claims/{claim_id}` | Get evidence for a claim |
| `POST` | `/api/v1/scoring/claims/{claim_id}` | Score a claim |
| `GET` | `/api/v1/reports/transcripts/{transcript_id}` | Get JSON report |
| `GET` | `/api/v1/reports/transcripts/{transcript_id}.html` | Get HTML report |
| `GET` | `/api/v1/reports/transcripts/{transcript_id}.md` | Get Markdown report |
| `POST` | `/api/v1/pipelines/factcheck` | Queue a full fact-check job |
| `GET` | `/api/v1/pipelines/jobs` | List recent jobs |
| `GET` | `/api/v1/pipelines/jobs/{job_id}` | Get job progress |
| `POST` | `/api/v1/pipelines/jobs/{job_id}/retry` | Retry a failed job |
| `GET` | `/api/v1/pipelines/jobs/{job_id}/events` | Get job events |
| `GET` | `/api/v1/pipelines/metrics` | Get pipeline metrics |
| `GET` | `/api/v1/pipelines/workers` | Get worker health |

Detailed endpoint docs:

- `docs/transcripts-api.md`
- `docs/claims-api.md`
- `docs/evidence-api.md`
- `docs/scoring-api.md`
- `docs/reports-api.md`
- `docs/pipelines-api.md`

## Configuration Reference

Configuration is loaded from `.env`.

Most users only need these at first:

| Variable | Meaning |
| --- | --- |
| `LLM_PROVIDER` | Which LLM provider to use: `openai`, `anthropic`, `ollama`, or `lmstudio` |
| `OPENAI_API_KEY` | OpenAI API key, if using OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic API key, if using Anthropic |
| `BRAVE_SEARCH_API_KEY` | Brave Search API key for live evidence retrieval |
| `DATABASE_URL` | SQLite database location |
| `SEARCH_PROVIDER` | Search provider. Use `brave` for now |

Advanced settings are already documented in `.env.example`.

## How The Main Pieces Work

Transcript ingestion lives in `src/evidencechain/services/transcript_service.py`.

Claim extraction lives in `src/evidencechain/services/claim_service.py`.

Evidence retrieval lives in `src/evidencechain/services/evidence_service.py`.

Verdict scoring lives in `src/evidencechain/services/scoring_service.py`.

Report rendering lives in `src/evidencechain/services/report_service.py`.

Pipeline orchestration lives in `src/evidencechain/pipelines/orchestration.py`.

## Spec Workflow

Use the numbered spec workflow under `specs/` for non-trivial changes.

Current specs:

| Spec | Purpose | Status |
| --- | --- | --- |
| `specs/001-frontend-ci` | Add frontend dependency install and build validation to CI | Implemented |

Reusable Copilot prompts live in `.github/prompts/`.

Repo-specific Copilot guidance lives in `.github/copilot-instructions.md`.

## Troubleshooting

### PowerShell blocks script activation

If this fails:

```powershell
.\.venv\Scripts\Activate.ps1
```

Run this, then try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### `pytest` cannot find packages

Make sure the virtual environment is activated:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then install dependencies again:

```powershell
pip install -r requirements.txt
```

### Backend works but frontend fails

Make sure the backend is still running at:

```text
http://127.0.0.1:8000
```

Then restart the frontend:

```powershell
cd frontend
npm run dev
```

### Full fact-checking fails

Check `.env`.

You need:

- A configured LLM provider.
- A valid API key for that provider, unless using a local model.
- `BRAVE_SEARCH_API_KEY` for live evidence retrieval.

### YouTube transcript fails

Some videos have no captions, blocked captions, bad metadata, or fetch issues.

Use transcript upload as the fallback.

## License

MIT. See `LICENSE`.
