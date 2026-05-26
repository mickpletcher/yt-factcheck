# Plan

## Files to Change

- `.github/workflows/ci.yml`
- `CHANGELOG.md`
- `assessment.md`

## Implementation

1. Rename the existing CI job to `backend`.
2. Add a separate `frontend` job.
3. Set up Node.js in the frontend job.
4. Run `npm ci` from `frontend`.
5. Run `npm run build` from `frontend`.
6. Update docs that mention the frontend CI gap.

## Test Plan

Run:

```powershell
cd frontend
npm run build
```

Review `.github/workflows/ci.yml` for the expected backend and frontend jobs.

## Risks

The frontend job can add CI time because it installs Node dependencies.

## Rollback

Remove the `frontend` job from `.github/workflows/ci.yml`.
