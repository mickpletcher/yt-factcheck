# Future Upgrades

Active upgrade backlog for EvidenceChain.

When an item is completed, remove it from this file and add it to `completed-upgrades.md` with the completion date, summary, touched areas, and validation.

## Tier 1: Near Term

These are the highest value upgrades for making the MVP easier to operate and safer to change.

- [ ] Add Docker Compose integration tests that verify API and web health checks.

## Tier 2: Mid Term

These improve accuracy, usability, and day to day workflow once the core operational gaps are handled.

- [ ] Add optional LLM assisted evidence comparison with strict citation constraints.
- [ ] Keep the current heuristic scorer as a fallback and guardrail for unsupported verdicts.
- [ ] Add source quality weighting for trusted domains, government sources, academic sources, and low quality sources.
- [ ] Add claim grouping so repeated or near duplicate claims are scored once and reused across reports.
- [ ] Add saved run history in the frontend with filtering by video, verdict, provider, and date.
- [ ] Add report comparison between multiple runs of the same video.
- [ ] Add editable trusted source domain management from the dashboard.
- [ ] Add API contract tests that compare backend response models with frontend TypeScript types.

## Tier 3: Long Term

These are larger product, scale, and reliability upgrades.

- [ ] Move pipeline execution to a durable external queue when multi-worker deployment is needed.
- [ ] Add PostgreSQL support for shared deployments and larger datasets.
- [ ] Add multi-user accounts, saved workspaces, and per-user report history.
- [ ] Add team review workflows for accepting, rejecting, or annotating verdicts.
- [ ] Add batch processing for playlists, channels, and uploaded transcript sets.
- [ ] Add semantic evidence retrieval using embeddings and a local vector index.
- [ ] Add source page archiving so reports can preserve evidence snapshots.
- [ ] Add scheduled re-checks for videos or claims when new evidence appears.
- [ ] Add a browser extension or share target for sending YouTube videos into EvidenceChain.
- [ ] Add deployment profiles for local only, private VPS, and hosted multi-user operation.
