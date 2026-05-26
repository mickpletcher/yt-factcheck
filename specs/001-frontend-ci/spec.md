# Spec

## Current Behavior

`.github/workflows/ci.yml` runs one Python job.

It installs Python dependencies, runs Ruff, runs mypy, and runs pytest.

It does not install frontend dependencies or build the React dashboard.

## Target Behavior

CI has two jobs:

- `backend`: validates Python lint, typing, and tests.
- `frontend`: validates the React and Vite production build.

The frontend job checks out the repo, installs Node.js, runs `npm ci` in `frontend`, and runs `npm run build` in `frontend`.

## Acceptance Criteria

- CI still runs on push and pull request to `main`.
- Backend validation still runs.
- Frontend validation runs in its own job.
- `npm ci` is used for deterministic dependency installation.
- `npm run build` is the frontend validation command.

## Security and Operational Impact

No runtime behavior changes.

The CI workflow now catches frontend build failures before merge.
