# Completed Upgrades

Completed upgrade log for EvidenceChain.

When a planned upgrade is finished, move it from `future-upgrades.md` to this file. Include the completion date, summary, touched areas, and validation.

## Completed

### 2026-05-26: Public readiness and queued dashboard hardening

Summary:

- Added API access token enforcement and per-client request rate limiting.
- Added SQLite schema migration tracking and provider usage event storage.
- Added Tavily and Bing Search providers plus search failover.
- Added provider readiness and admin provider metrics endpoints.
- Wired URL-based React dashboard runs to the queued pipeline API with polling and cancellation.
- Added clearer pipeline failure messages for caption, metadata, and provider failures.
- Added queued and running pipeline job cancellation.
- Added report export cleanup controls.
- Added frontend linting and dashboard flow tests.

Touched areas:

- `src/evidencechain/api/`
- `src/evidencechain/core/config.py`
- `src/evidencechain/providers/`
- `src/evidencechain/services/`
- `src/evidencechain/pipelines/orchestration.py`
- `src/evidencechain/storage/database.py`
- `frontend/`
- `.github/workflows/ci.yml`
- `.env*.example`
- `docs/`
- `tests/`

Validation:

- `.\\.venv\\Scripts\\python.exe -m ruff check .`
- `.\\.venv\\Scripts\\python.exe -m mypy src`
- `.\\.venv\\Scripts\\python.exe -m pytest -q`
- `npm run lint` from `frontend`
- `npm test` from `frontend`
- `npm run build` from `frontend`

### 2026-05-25: Frontend CI validation

Summary:

- Added frontend dependency install and build validation to CI.
- Added a separate frontend CI job.
- Preserved the backend CI job for Python validation.

Touched areas:

- `.github/workflows/ci.yml`
- `specs/001-frontend-ci/`
- `CHANGELOG.md`
- `assessment.md`

Validation:

- `npm run build` from `frontend`
- CI workflow review

### 2026-05-25: Production Docker deployment assets

Summary:

- Added production Docker targets for the FastAPI API and Nginx web frontend.
- Added Docker Compose deployment with health checks, named volumes, and container hardening.
- Added local and production environment templates.
- Added startup and VPS deployment scripts.
- Added deployment documentation.

Touched areas:

- `Dockerfile`
- `docker-compose.yml`
- `nginx/nginx.conf`
- `scripts/`
- `docs/deployment.md`
- `.env.local.example`
- `.env.production.example`

Validation:

- Docker health checks documented for `/healthz` and `/api/v1/health`

### 2026-05-25: Full MVP pipeline

Summary:

- Added transcript ingestion, timestamp preserving chunking, claim extraction, evidence retrieval, scoring, reporting, and pipeline orchestration.
- Added persisted pipeline jobs, stage runs, events, retries, recovery, metrics, and worker health.
- Added REST API groups and endpoint docs for transcripts, claims, evidence, scoring, reports, and pipelines.

Touched areas:

- `src/evidencechain/api/`
- `src/evidencechain/models/`
- `src/evidencechain/services/`
- `src/evidencechain/pipelines/`
- `src/evidencechain/storage/`
- `docs/`
- `tests/`

Validation:

- Backend tests
- Ruff
- mypy

### 2026-05-25: React dashboard

Summary:

- Added a React and Vite dashboard for running and reviewing fact-check jobs.
- Added YouTube URL transcript ingestion, transcript upload, live pipeline progress, searchable claims, expandable evidence sections, verdict inspection, and report viewing.

Touched areas:

- `frontend/`
- `README.md`
- `assessment.md`

Validation:

- `npm run build` from `frontend`

### 2026-05-25: Repo safety and local hygiene

Summary:

- Added a workspace-local pre-push hook to block accidental pushes from this clone.
- Ignored prompt files and local VS Code workspace files.

Touched areas:

- `.githooks/`
- `.gitignore`

Validation:

- Git ignore and hook configuration review
