# Changelog

## 2026-05-25

- Added a workspace-local `pre-push` hook under `.githooks` to block `git push` from this clone.
- Added `Prompts/` to `.gitignore` so prompt files are not tracked or pushed.
- Added `*.code-workspace` to `.gitignore` so local VS Code workspace files are not tracked.