# Pipelines API

The pipeline API queues full EvidenceChain fact check jobs through in process asyncio workers.

No Celery, Redis, or external queue is required. Jobs and stage progress are persisted in SQLite, so interrupted queued or running jobs are requeued when the app starts again.

## Stages

Each job runs these stages in order:

1. `transcript_ingestion`
2. `chunking`
3. `claim_extraction`
4. `evidence_retrieval`
5. `scoring`
6. `report_generation`

## Queue a Job

`POST /api/v1/pipelines/factcheck`

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=abc123"
}
```

Response:

```json
{
  "job_id": 1,
  "status": "queued"
}
```

## Job Status

`GET /api/v1/pipelines/jobs/{job_id}`

Returns job status, overall progress, current stage, stored transcript ID, claim IDs, report payload, retry count, and per stage status with timing metrics.

## List Jobs

`GET /api/v1/pipelines/jobs?limit=25`

Returns recent pipeline jobs.

## Retry Failed Job

`POST /api/v1/pipelines/jobs/{job_id}/retry`

Only failed jobs can be retried manually. Automatic retries are controlled by `PIPELINE_RETRY_ATTEMPTS` and `PIPELINE_RETRY_BACKOFF_SECONDS`.

## Events

`GET /api/v1/pipelines/jobs/{job_id}/events`

Returns structured job and stage events from SQLite.

## Metrics

`GET /api/v1/pipelines/metrics`

Returns job counts by status, average successful job duration, and average duration by stage.

## Worker Health

`GET /api/v1/pipelines/workers`

Returns the active backend, worker count, running state, and queue size.

The current backend is `asyncio`. The queue and worker interface is isolated so a future Celery or Redis backed implementation can enqueue the same job IDs without changing pipeline stage code.
