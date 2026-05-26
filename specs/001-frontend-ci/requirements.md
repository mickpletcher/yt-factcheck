# Requirements

## Problem

The frontend build passes locally, but GitHub Actions CI only validates the Python backend.

This lets TypeScript, Vite, dependency, or build errors reach `main` unnoticed.

## Goals

- Run frontend dependency installation in CI.
- Run the production frontend build in CI.
- Keep backend validation unchanged.
- Keep the workflow simple and readable.

## Non-goals

- Add frontend unit tests.
- Add browser end-to-end tests.
- Change the frontend build scripts.
- Change deployment behavior.

## Functional Requirements

- CI must run on pushes and pull requests targeting `main`.
- CI must install frontend dependencies from `frontend/package-lock.json`.
- CI must run `npm run build` from `frontend`.
- Backend lint, type check, and tests must keep running.

## Operational Requirements

- Use a current Node.js LTS version.
- Use `npm ci` instead of `npm install` in CI.
- Keep the frontend job separate from the backend job so failures are easy to identify.

## Validation Requirements

- Run the frontend build locally.
- Confirm the CI workflow defines both backend and frontend validation.
