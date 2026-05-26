# EvidenceChain Copilot Instructions

Use the repo's spec workflow for non-trivial changes.

## Project Context

EvidenceChain is a full-stack YouTube fact-checking app.

- Backend: Python 3.12, FastAPI, Pydantic v2, SQLite, asyncio workers.
- Frontend: React, Vite, TypeScript.
- Deployment: Docker, Docker Compose, Nginx, GitHub Actions.
- Tests: pytest, ruff, mypy, frontend TypeScript build.

## Working Rules

- Read the current code before proposing changes.
- Keep backend changes under `src/evidencechain` unless the change is clearly deployment, docs, or test related.
- Keep frontend changes under `frontend`.
- Keep API docs in `docs` aligned with endpoint behavior.
- Keep `README.md`, `CHANGELOG.md`, and `assessment.md` aligned when shipped behavior changes.
- Do not add compatibility shims for replaced behavior unless the spec explicitly requires it.
- Prefer simple implementation over new abstraction.

## Spec Workflow

Use numbered spec folders under `specs/`.

Each spec folder should contain:

- `README.md`
- `requirements.md`
- `spec.md`
- `plan.md`
- `tasks.md`

Flow:

1. Requirements
2. Spec
3. Plan
4. Tasks
5. Implementation
6. Audit
7. Regression test

Small fixes can skip a new spec when the risk and scope are low.

## Validation

Run the checks that match the touched area:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src
cd frontend
npm run build
```
