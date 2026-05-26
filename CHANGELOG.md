# Changelog

## Unreleased

- Added transcript ingestion endpoints for YouTube URL retrieval and upload fallback.
- Added transcript models, SQLite transcript storage, timestamp preserving parsing, chunking, retry logic, and API docs.
- Added tests for transcript parsing, storage, chunking, and upload API behavior.
- Added claim extraction schemas, prompt templates, provider interface stubs, SQLite claim tables, claim API endpoints, and tests.

## 2026-05-25

- Added a workspace-local `pre-push` hook under `.githooks` to block `git push` from this clone.
- Added `Prompts/` to `.gitignore` so prompt files are not tracked or pushed.
- Added `*.code-workspace` to `.gitignore` so local VS Code workspace files are not tracked.
