# Changelog

## Unreleased

- Added transcript ingestion endpoints for YouTube URL retrieval and upload fallback.
- Added transcript models, SQLite transcript storage, timestamp preserving parsing, chunking, retry logic, and API docs.
- Added tests for transcript parsing, storage, chunking, and upload API behavior.
- Added claim extraction schemas, prompt templates, provider interface stubs, SQLite claim tables, claim API endpoints, and tests.
- Added the evidence retrieval engine with swappable search provider abstractions, functional Brave Search support, scoring, dedupe, caching, storage, API endpoints, and tests.
- Added the verdict scoring engine with stored evidence comparison, citation validation, hallucination safeguards, scoring API endpoints, docs, and tests.
- Added the reporting engine with JSON, HTML, Markdown, disk exports, public report templates, report API endpoints, docs, and tests.
- Added asyncio pipeline orchestration with persistent queue state, worker lifecycle, retries, failure recovery, progress tracking, structured events, metrics, API endpoints, docs, and tests.
- Added production Docker targets for the FastAPI API and Nginx web frontend.
- Added Docker Compose deployment with health checks, named volumes, and container hardening.
- Added local and production environment templates, startup scripts, VPS deployment support, and deployment documentation.
- Added GitHub Actions image build, GHCR push, and optional VPS deployment workflow.
- Added GitHub Copilot spec workflow files and the first numbered spec for frontend CI.
- Added frontend `npm ci` and `npm run build` validation to CI.

## 2026-05-25

- Added a workspace-local `pre-push` hook under `.githooks` to block `git push` from this clone.
- Added `Prompts/` to `.gitignore` so prompt files are not tracked or pushed.
- Added `*.code-workspace` to `.gitignore` so local VS Code workspace files are not tracked.
