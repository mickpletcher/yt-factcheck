# Project Assessment

## Executive Summary

EvidenceChain is a working full-stack YouTube fact-checking application.

The backend is a Python 3.12 FastAPI service that ingests YouTube transcripts, extracts factual claims with an LLM provider, retrieves evidence through a search provider, scores verdicts against stored evidence, and generates reports. The frontend is a React and Vite dashboard for running and reviewing the pipeline.

The project is in a solid MVP state. The core architecture is clean, tests pass, CI exists, and Docker deployment is already wired. The biggest current risks are provider completeness, local environment sharp edges, and the limits of the scoring logic.

## Current Validation

Validated from the project virtual environment and frontend workspace:

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `.\\.venv\\Scripts\\python.exe -m pytest -q` | Passed, 28 tests |
| Backend lint | `.\\.venv\\Scripts\\python.exe -m ruff check .` | Passed |
| Backend typing | `.\\.venv\\Scripts\\python.exe -m mypy src` | Passed, 46 source files |
| Frontend build | `npm run build` from `frontend` | Passed |

Note: running `python -m pytest` with the Windows Store Python 3.11 failed because dependencies such as `aiosqlite` were not installed there. The repo targets Python 3.12 and the local `.venv` is the correct environment.

## Project Purpose

The project is designed to fact check YouTube videos through a repeatable evidence chain:

1. Ingest a YouTube transcript or uploaded transcript file.
2. Chunk the transcript while preserving timestamps.
3. Extract factual claims from transcript chunks.
4. Retrieve external evidence for each claim.
5. Compare evidence against claims.
6. Score verdicts with stored citations.
7. Generate JSON, HTML, and Markdown reports.
8. Display pipeline progress and results in a dashboard.

The project name in code and packaging is `evidencechain`. The repo folder is `yt-factcheck`.

## Architecture

### Backend

Backend source lives under `src/evidencechain`.

Key areas:

| Area | Path | Role |
| --- | --- | --- |
| App entry point | `src/evidencechain/main.py` | Creates FastAPI app, configures logging, initializes SQLite, starts pipeline workers |
| API routing | `src/evidencechain/api/` | REST endpoints grouped by health, transcripts, claims, evidence, scoring, reports, and pipelines |
| Settings | `src/evidencechain/core/config.py` | Loads `.env` settings through Pydantic Settings |
| Models | `src/evidencechain/models/` | Pydantic API and service models |
| Services | `src/evidencechain/services/` | Transcript, claim, evidence, scoring, report, and citation logic |
| Providers | `src/evidencechain/providers/` | LLM and search provider integrations |
| Pipeline | `src/evidencechain/pipelines/` | Asyncio job queue, stage execution, retries, recovery, metrics |
| Storage | `src/evidencechain/storage/database.py` | SQLite schema initialization |
| Utilities | `src/evidencechain/utils/` | Chunking and logging helpers |

The backend is modular enough for staged growth. Services are mostly injectable, which keeps tests practical and avoids hard coupling to live LLM or search APIs.

### Frontend

Frontend source lives under `frontend`.

Stack:

| Area | Path | Role |
| --- | --- | --- |
| App shell | `frontend/src/App.tsx` | Dashboard layout and main workflow |
| API client | `frontend/src/api/client.ts` | Calls backend endpoints |
| Pipeline hook | `frontend/src/hooks/usePipeline.ts` | Orchestrates frontend pipeline state |
| Components | `frontend/src/components/` | Claims, evidence, progress, reports, summary, verdict UI |
| Types | `frontend/src/types.ts` | Frontend data contracts |
| Styling | `frontend/src/styles.css` | Dashboard styling |

The dashboard is functional. It supports YouTube URLs, uploaded transcripts, live progress, searchable claims, evidence review, verdict inspection, and report viewing.

## Data Model

SQLite is the only supported database at this stage.

Important tables:

| Table | Purpose |
| --- | --- |
| `transcripts` | Transcript metadata |
| `transcript_segments` | Timestamped source transcript segments |
| `transcript_chunks` | Chunked transcript text for LLM processing |
| `claim_extraction_runs` | Claim extraction run metadata |
| `claims` | Stored factual claims |
| `evidence_retrieval_runs` | Search run metadata |
| `evidence_sources` | Stored retrieved evidence |
| `scoring_results` | Verdicts, comparisons, safeguards, cited evidence IDs |
| `search_cache` | Cached provider search responses |
| `pipeline_jobs` | Full pipeline job state |
| `pipeline_stage_runs` | Per-stage status and timing |
| `pipeline_events` | Structured pipeline event log |

The schema is simple and easy to inspect. There is no migration system yet, so schema changes currently depend on editing the initialization script.

## API Surface

The API is mounted under `/api/v1`.

Implemented groups:

| Group | Main capability |
| --- | --- |
| Health | Service and provider health checks |
| Transcripts | YouTube transcript ingestion, upload fallback, chunk retrieval |
| Claims | Claim extraction and claim lookup |
| Evidence | Evidence retrieval and stored evidence lookup |
| Scoring | Claim scoring and verdict lookup |
| Reports | JSON, HTML, Markdown, and exported reports |
| Pipelines | Full fact-check job queue, retries, events, metrics, worker health |

The API has good coverage for the MVP workflow. The docs folder mirrors the main endpoint groups.

## Provider Support

### LLM Providers

Implemented:

| Provider | Status |
| --- | --- |
| OpenAI | Implemented |
| Anthropic | Implemented |
| Ollama | Implemented |
| LM Studio | Implemented |
| Failover chain | Implemented |

The provider layer supports health checks, structured JSON output, usage tracking, and optional cost rates.

### Search Providers

Implemented:

| Provider | Status |
| --- | --- |
| Brave Search | Implemented |

Reserved but not implemented:

| Provider | Status |
| --- | --- |
| Tavily | Wired placeholder |
| Bing Search | Wired placeholder |
| SerpAPI | Wired placeholder |

This is one of the main product limitations. Evidence retrieval depends on Brave Search for live operation.

## Pipeline

The pipeline is an in-process asyncio worker system.

Stages:

1. Transcript ingestion
2. Chunking
3. Claim extraction
4. Evidence retrieval
5. Scoring
6. Report generation

Strengths:

- Jobs are persisted in SQLite.
- Stage status is persisted.
- Events are persisted.
- Failed jobs can retry automatically.
- Failed jobs can be retried manually.
- Startup recovery requeues queued, running, and retrying jobs.
- Worker health and metrics endpoints exist.

Limitations:

- Queue execution is in process, not distributed.
- Long-running jobs share the FastAPI process.
- Horizontal scaling would require external queue coordination.
- There is no cancellation endpoint.

The current design is fine for a single-node MVP or small VPS deployment.

## Deployment

Deployment support is better than typical MVP level.

Existing deployment assets:

| Asset | Purpose |
| --- | --- |
| `Dockerfile` | Multi-stage frontend build, API runtime, and Nginx web runtime |
| `docker-compose.yml` | Local or VPS stack with API, web, named volumes, health checks |
| `nginx/nginx.conf` | Reverse proxy and static frontend serving |
| `scripts/start-local.ps1` | Windows local Docker startup |
| `scripts/start-api.sh` | Container API startup |
| `scripts/deploy-vps.sh` | VPS helper |
| `.github/workflows/deploy.yml` | Builds and pushes GHCR images, optional VPS deploy |
| `docs/deployment.md` | Deployment guide |

Security minded details already present:

- Non-root API runtime user.
- Nginx unprivileged image.
- Dropped Linux capabilities in Compose.
- `no-new-privileges`.
- Web container read-only mode.
- Named volumes for data and reports.
- Health checks on both services.

## Testing and Quality

Current test coverage is focused on backend logic and API behavior.

Covered areas:

- Health API
- Transcript parsing and API behavior
- Claim extraction service and API behavior
- Evidence service and API behavior
- LLM provider behavior
- Scoring service and API behavior
- Report API behavior
- Pipeline orchestration
- Transcript chunking

Quality tools:

- `pytest`
- `pytest-asyncio`
- `ruff`
- `mypy` in strict mode
- Frontend TypeScript build
- GitHub Actions CI for Python checks

Gap:

The CI workflow does not currently build the frontend. The frontend build passes locally, but CI only runs Python lint, type checks, and tests.

## Documentation

The repo has useful docs:

| File | Purpose |
| --- | --- |
| `README.md` | Main setup, run, test, Docker, API, and architecture guide |
| `CHANGELOG.md` | Change history |
| `docs/transcripts-api.md` | Transcript endpoint details |
| `docs/claims-api.md` | Claim endpoint details |
| `docs/evidence-api.md` | Evidence endpoint details |
| `docs/scoring-api.md` | Scoring endpoint details |
| `docs/reports-api.md` | Report endpoint details |
| `docs/pipelines-api.md` | Pipeline endpoint details |
| `docs/deployment.md` | Local, VPS, and cloud deployment |

The README is current with the live repo structure and major capabilities.

## Strengths

- Clean FastAPI service organization.
- Strong Pydantic model usage.
- Async SQLite access is used consistently.
- Pipeline state is durable enough for MVP recovery.
- LLM providers are abstracted cleanly.
- Search provider boundary is already in place.
- Scoring blocks unsupported verdicts when stored evidence is insufficient.
- Citation validation exists to reduce fabricated citation risk.
- Docker deployment is practical and already hardened in basic ways.
- Tests, lint, and strict typing pass in the project virtual environment.
- Frontend is not just a placeholder. It supports the actual workflow.

## Risks and Weak Spots

### 1. No database migrations

The SQLite schema is initialized from one large script. That is acceptable now, but it will become painful once real user data exists.

Recommended fix:

Add a migration tool or a small repo-local migration runner before making breaking schema changes.

### 2. Search provider coverage is thin

Only Brave Search is implemented. Tavily, Bing, and SerpAPI are placeholders.

Recommended fix:

Implement at least one backup search provider and add failover behavior for evidence retrieval.

### 3. Scoring logic is heuristic

The scoring engine uses relevance, ranking, simple comparison relationships, and thresholds. It is explainable, but not deeply semantic.

Recommended fix:

Add an optional LLM assisted evidence comparison stage with strict citation constraints, then keep the current heuristic scorer as a fallback or guardrail.

### 4. Frontend is not in CI

The frontend build passes locally but is not part of the CI workflow.

Recommended fix:

Add a CI job for `frontend`: `npm ci` and `npm run build`.

### 5. Runtime depends on external services

Real fact-check runs need at least one configured LLM provider and Brave Search key. Without those, only mocked or partial workflows work.

Recommended fix:

Add a startup diagnostics command or endpoint that reports which workflow capabilities are actually configured.

### 6. In-process pipeline limits scaling

The current queue is fine for local and single VPS use. It is not a durable distributed queue.

Recommended fix:

Keep the current queue for MVP. Move to Redis, Postgres advisory locks, or another external queue only when multi-worker deployment becomes necessary.

### 7. YouTube transcript availability will vary

Some videos have no captions, blocked captions, bad metadata, or anti-bot friction.

Recommended fix:

Keep uploaded transcript fallback prominent. Add clearer user-facing failure messages for missing captions and fetch failures.

## Suggested Next Work

Priority order:

1. Add frontend CI.
2. Add a database migration path.
3. Implement one more evidence search provider.
4. Add a provider readiness endpoint or CLI diagnostic.
5. Improve user-facing pipeline failure messages.
6. Add cancellation support for queued and running jobs.
7. Add report export cleanup or retention controls.
8. Add integration tests for Docker Compose health checks.
9. Add authenticated access before exposing this publicly.
10. Add rate limiting if deployed beyond personal use.

## Bottom Line

This is not just a scaffold. It is a functioning MVP with backend services, frontend workflow, tests, CI, Docker packaging, and deployment documentation.

The next jump is operational hardening: migrations, CI coverage for the frontend, provider failover, better runtime diagnostics, and basic auth or access control before public exposure.
