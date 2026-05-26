import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import aiosqlite

from evidencechain.core.config import Settings, get_settings
from evidencechain.models.pipeline import (
    PipelineEvent,
    PipelineJobDetail,
    PipelineJobStatus,
    PipelineMetrics,
    PipelineStage,
    PipelineStageRun,
    PipelineStageStatus,
    WorkerHealth,
)
from evidencechain.services.claim_service import ClaimService
from evidencechain.services.evidence_service import EvidenceService
from evidencechain.services.report_service import ReportService
from evidencechain.services.scoring_service import ScoringService
from evidencechain.services.transcript_service import TranscriptService
from evidencechain.utils.logging import get_logger

StageHandler = Callable[[PipelineJobDetail], Awaitable[dict[str, Any]]]

PIPELINE_STAGES = [
    PipelineStage.transcript_ingestion,
    PipelineStage.chunking,
    PipelineStage.claim_extraction,
    PipelineStage.evidence_retrieval,
    PipelineStage.scoring,
    PipelineStage.report_generation,
]


class PipelineNotFoundError(Exception):
    pass


class PipelineCanceledError(Exception):
    pass


class PipelineQueue(Protocol):
    async def enqueue(self, job_id: int) -> None:
        ...

    async def dequeue(self) -> int:
        ...

    def size(self) -> int:
        ...


class AsyncioPipelineQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[int] = asyncio.Queue()

    async def enqueue(self, job_id: int) -> None:
        await self._queue.put(job_id)

    async def dequeue(self) -> int:
        return await self._queue.get()

    def size(self) -> int:
        return self._queue.qsize()

    def task_done(self) -> None:
        self._queue.task_done()


class PipelineRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def create_job(
        self,
        youtube_url: str,
        max_attempts: int,
        transcript_id: int | None = None,
    ) -> PipelineJobDetail:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            cursor = await connection.execute(
                """
                INSERT INTO pipeline_jobs (youtube_url, status, max_attempts, transcript_id)
                VALUES (?, ?, ?, ?)
                """,
                (youtube_url, PipelineJobStatus.queued.value, max_attempts, transcript_id),
            )
            job_id = cursor.lastrowid
            if job_id is None:
                raise RuntimeError("Failed to create pipeline job.")
            for stage in PIPELINE_STAGES:
                await connection.execute(
                    """
                    INSERT INTO pipeline_stage_runs (job_id, stage, status)
                    VALUES (?, ?, ?)
                    """,
                    (job_id, stage.value, PipelineStageStatus.pending.value),
                )
            await connection.commit()
        await self.add_event(job_id, None, "job_queued", "Pipeline job queued.")
        return await self.get_job(job_id)

    async def get_job(self, job_id: int) -> PipelineJobDetail:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            connection.row_factory = aiosqlite.Row
            job_row = await self._fetch_one(
                connection,
                "SELECT * FROM pipeline_jobs WHERE id = ?",
                (job_id,),
            )
            if job_row is None:
                raise PipelineNotFoundError(f"Pipeline job {job_id} was not found.")
            stage_rows = await self._fetch_all(
                connection,
                """
                SELECT *
                FROM pipeline_stage_runs
                WHERE job_id = ?
                ORDER BY id
                """,
                (job_id,),
            )
        return self._job_from_rows(job_row, stage_rows)

    async def list_jobs(self, limit: int = 25) -> list[PipelineJobDetail]:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            connection.row_factory = aiosqlite.Row
            rows = await self._fetch_all(
                connection,
                """
                SELECT id
                FROM pipeline_jobs
                ORDER BY queued_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
        return [await self.get_job(row["id"]) for row in rows]

    async def recoverable_job_ids(self) -> list[int]:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            connection.row_factory = aiosqlite.Row
            rows = await self._fetch_all(
                connection,
                """
                SELECT id
                FROM pipeline_jobs
                WHERE status IN (?, ?, ?)
                ORDER BY queued_at, id
                """,
                (
                    PipelineJobStatus.queued.value,
                    PipelineJobStatus.running.value,
                    PipelineJobStatus.retrying.value,
                ),
            )
            await connection.execute(
                """
                UPDATE pipeline_jobs
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE status IN (?, ?)
                """,
                (
                    PipelineJobStatus.queued.value,
                    PipelineJobStatus.running.value,
                    PipelineJobStatus.retrying.value,
                ),
            )
            await connection.commit()
        return [row["id"] for row in rows]

    async def mark_job_running(self, job_id: int) -> None:
        await self._execute(
            """
            UPDATE pipeline_jobs
            SET status = ?, started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                error_message = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (PipelineJobStatus.running.value, job_id),
        )

    async def update_job_progress(
        self,
        job_id: int,
        stage: PipelineStage,
        progress: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._execute(
            """
            UPDATE pipeline_jobs
            SET current_stage = ?, progress = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (stage.value, progress, job_id),
        )
        if metadata:
            await self.add_event(
                job_id,
                stage,
                "stage_progress",
                "Pipeline stage progressed.",
                metadata,
            )

    async def update_context(
        self,
        job_id: int,
        transcript_id: int | None = None,
        claim_ids: list[int] | None = None,
        report: dict[str, Any] | None = None,
    ) -> None:
        assignments = ["updated_at = CURRENT_TIMESTAMP"]
        parameters: list[Any] = []
        if transcript_id is not None:
            assignments.append("transcript_id = ?")
            parameters.append(transcript_id)
        if claim_ids is not None:
            assignments.append("claim_ids_json = ?")
            parameters.append(json.dumps(claim_ids))
        if report is not None:
            assignments.append("report_json = ?")
            parameters.append(json.dumps(report, default=str))
        parameters.append(job_id)
        await self._execute(
            f"UPDATE pipeline_jobs SET {', '.join(assignments)} WHERE id = ?",
            tuple(parameters),
        )

    async def mark_job_succeeded(self, job_id: int) -> None:
        await self._execute(
            """
            UPDATE pipeline_jobs
            SET status = ?, progress = 1, current_stage = NULL, completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (PipelineJobStatus.succeeded.value, job_id),
        )
        await self.add_event(job_id, None, "job_succeeded", "Pipeline job completed.")

    async def mark_job_failed(self, job_id: int, error: str) -> None:
        await self._execute(
            """
            UPDATE pipeline_jobs
            SET status = ?, error_message = ?, current_stage = NULL,
                completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (PipelineJobStatus.failed.value, error, job_id),
        )
        await self.add_event(job_id, None, "job_failed", "Pipeline job failed.", {"error": error})

    async def cancel_job(self, job_id: int) -> None:
        job = await self.get_job(job_id)
        if job.status not in {
            PipelineJobStatus.queued,
            PipelineJobStatus.running,
            PipelineJobStatus.retrying,
        }:
            raise ValueError("Only queued, running, or retrying jobs can be canceled.")
        await self._execute(
            """
            UPDATE pipeline_jobs
            SET status = ?, error_message = NULL, current_stage = NULL,
                completed_at = CURRENT_TIMESTAMP, cancelled_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (PipelineJobStatus.canceled.value, job_id),
        )
        await self.add_event(job_id, None, "job_canceled", "Pipeline job canceled.")

    async def is_canceled(self, job_id: int) -> bool:
        job = await self.get_job(job_id)
        return job.status == PipelineJobStatus.canceled

    async def mark_job_retrying(self, job_id: int, error: str) -> bool:
        job = await self.get_job(job_id)
        next_retry_count = job.retry_count + 1
        if next_retry_count >= job.max_attempts:
            return False
        await self._execute(
            """
            UPDATE pipeline_jobs
            SET status = ?, retry_count = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (PipelineJobStatus.retrying.value, next_retry_count, error, job_id),
        )
        await self.add_event(
            job_id,
            job.current_stage,
            "job_retrying",
            "Pipeline job will retry.",
            {"retry_count": next_retry_count, "error": error},
        )
        return True

    async def reset_failed_job(self, job_id: int) -> None:
        job = await self.get_job(job_id)
        if job.status != PipelineJobStatus.failed:
            raise ValueError("Only failed pipeline jobs can be retried manually.")
        await self._execute(
            """
            UPDATE pipeline_jobs
            SET status = ?, error_message = NULL, completed_at = NULL,
                current_stage = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (PipelineJobStatus.queued.value, job_id),
        )
        await self.add_event(job_id, None, "job_requeued", "Pipeline job requeued.")

    async def start_stage(self, job_id: int, stage: PipelineStage, attempt: int) -> None:
        await self._execute(
            """
            UPDATE pipeline_stage_runs
            SET status = ?, attempt = ?, progress = 0, started_at = CURRENT_TIMESTAMP,
                completed_at = NULL, duration_ms = NULL, error_message = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ? AND stage = ?
            """,
            (PipelineStageStatus.running.value, attempt, job_id, stage.value),
        )
        await self.add_event(job_id, stage, "stage_started", "Pipeline stage started.")

    async def complete_stage(
        self,
        job_id: int,
        stage: PipelineStage,
        started_at: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
        await self._execute(
            """
            UPDATE pipeline_stage_runs
            SET status = ?, progress = 1, completed_at = CURRENT_TIMESTAMP,
                duration_ms = ?, metadata_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ? AND stage = ?
            """,
            (
                PipelineStageStatus.succeeded.value,
                duration_ms,
                json.dumps(metadata or {}, default=str),
                job_id,
                stage.value,
            ),
        )
        await self.add_event(
            job_id,
            stage,
            "stage_succeeded",
            "Pipeline stage completed.",
            {"duration_ms": duration_ms, **(metadata or {})},
        )

    async def fail_stage(
        self,
        job_id: int,
        stage: PipelineStage,
        started_at: float,
        error: str,
    ) -> None:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
        await self._execute(
            """
            UPDATE pipeline_stage_runs
            SET status = ?, completed_at = CURRENT_TIMESTAMP, duration_ms = ?,
                error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ? AND stage = ?
            """,
            (PipelineStageStatus.failed.value, duration_ms, error, job_id, stage.value),
        )
        await self.add_event(
            job_id,
            stage,
            "stage_failed",
            "Pipeline stage failed.",
            {"duration_ms": duration_ms, "error": error},
        )

    async def add_event(
        self,
        job_id: int,
        stage: PipelineStage | None,
        event_type: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._execute(
            """
            INSERT INTO pipeline_events (job_id, stage, event_type, message, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                job_id,
                stage.value if stage else None,
                event_type,
                message,
                json.dumps(metadata or {}),
            ),
        )

    async def list_events(self, job_id: int, limit: int = 100) -> list[PipelineEvent]:
        await self.get_job(job_id)
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            connection.row_factory = aiosqlite.Row
            rows = await self._fetch_all(
                connection,
                """
                SELECT *
                FROM pipeline_events
                WHERE job_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (job_id, limit),
            )
        return [self._event_from_row(row) for row in rows]

    async def metrics(self) -> PipelineMetrics:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            connection.row_factory = aiosqlite.Row
            status_rows = await self._fetch_all(
                connection,
                "SELECT status, COUNT(*) AS total FROM pipeline_jobs GROUP BY status",
                (),
            )
            duration_row = await self._fetch_one(
                connection,
                """
                SELECT AVG(
                    (julianday(completed_at) - julianday(started_at)) * 86400000.0
                ) AS average_duration_ms
                FROM pipeline_jobs
                WHERE status = ? AND started_at IS NOT NULL AND completed_at IS NOT NULL
                """,
                (PipelineJobStatus.succeeded.value,),
            )
            stage_rows = await self._fetch_all(
                connection,
                """
                SELECT stage, AVG(duration_ms) AS average_duration_ms
                FROM pipeline_stage_runs
                WHERE status = ? AND duration_ms IS NOT NULL
                GROUP BY stage
                """,
                (PipelineStageStatus.succeeded.value,),
            )
        counts = {row["status"]: row["total"] for row in status_rows}
        total = sum(counts.values())
        return PipelineMetrics(
            queued=counts.get(PipelineJobStatus.queued.value, 0),
            running=counts.get(PipelineJobStatus.running.value, 0),
            retrying=counts.get(PipelineJobStatus.retrying.value, 0),
            succeeded=counts.get(PipelineJobStatus.succeeded.value, 0),
            failed=counts.get(PipelineJobStatus.failed.value, 0),
            total=total,
            average_duration_ms=(
                round(float(duration_row["average_duration_ms"]), 3)
                if duration_row and duration_row["average_duration_ms"] is not None
                else None
            ),
            stage_average_duration_ms={
                row["stage"]: round(float(row["average_duration_ms"]), 3)
                for row in stage_rows
                if row["average_duration_ms"] is not None
            },
        )

    async def _execute(self, query: str, parameters: tuple[Any, ...]) -> None:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            await connection.execute(query, parameters)
            await connection.commit()

    async def _fetch_one(
        self,
        connection: aiosqlite.Connection,
        query: str,
        parameters: tuple[Any, ...],
    ) -> aiosqlite.Row | None:
        cursor = await connection.execute(query, parameters)
        return await cursor.fetchone()

    async def _fetch_all(
        self,
        connection: aiosqlite.Connection,
        query: str,
        parameters: tuple[Any, ...],
    ) -> list[aiosqlite.Row]:
        cursor = await connection.execute(query, parameters)
        return list(await cursor.fetchall())

    def _job_from_rows(
        self,
        job_row: aiosqlite.Row,
        stage_rows: list[aiosqlite.Row],
    ) -> PipelineJobDetail:
        return PipelineJobDetail(
            id=job_row["id"],
            youtube_url=job_row["youtube_url"],
            status=job_row["status"],
            progress=job_row["progress"],
            current_stage=job_row["current_stage"],
            transcript_id=job_row["transcript_id"],
            claim_ids=json.loads(job_row["claim_ids_json"] or "[]"),
            report=json.loads(job_row["report_json"]) if job_row["report_json"] else None,
            error_message=job_row["error_message"],
            retry_count=job_row["retry_count"],
            max_attempts=job_row["max_attempts"],
            queued_at=job_row["queued_at"],
            started_at=job_row["started_at"],
            completed_at=job_row["completed_at"],
            updated_at=job_row["updated_at"],
            stages=[self._stage_from_row(row) for row in stage_rows],
        )

    def _stage_from_row(self, row: aiosqlite.Row) -> PipelineStageRun:
        return PipelineStageRun(
            stage=row["stage"],
            status=row["status"],
            attempt=row["attempt"],
            progress=row["progress"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            duration_ms=row["duration_ms"],
            error_message=row["error_message"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def _event_from_row(self, row: aiosqlite.Row) -> PipelineEvent:
        return PipelineEvent(
            id=row["id"],
            job_id=row["job_id"],
            stage=row["stage"],
            event_type=row["event_type"],
            message=row["message"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=row["created_at"],
        )


class FactCheckOrchestrator:
    def __init__(
        self,
        settings: Settings | None = None,
        repository: PipelineRepository | None = None,
        queue: PipelineQueue | None = None,
        transcript_service: TranscriptService | None = None,
        claim_service: ClaimService | None = None,
        evidence_service: EvidenceService | None = None,
        scoring_service: ScoringService | None = None,
        report_service: ReportService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or PipelineRepository(self.settings)
        self.queue = queue or AsyncioPipelineQueue()
        self.transcript_service = transcript_service or TranscriptService(settings=self.settings)
        self.claim_service = claim_service or ClaimService(settings=self.settings)
        self.evidence_service = evidence_service or EvidenceService(settings=self.settings)
        self.scoring_service = scoring_service or ScoringService(
            settings=self.settings,
            evidence_service=self.evidence_service,
        )
        self.report_service = report_service or ReportService(
            settings=self.settings,
            transcript_service=self.transcript_service,
            claim_service=self.claim_service,
            evidence_service=self.evidence_service,
            scoring_service=self.scoring_service,
        )
        self.logger = get_logger(__name__)
        self._workers: list[asyncio.Task[None]] = []
        self._running = False
        self._handlers: dict[PipelineStage, StageHandler] = {
            PipelineStage.transcript_ingestion: self._transcript_ingestion,
            PipelineStage.chunking: self._chunking,
            PipelineStage.claim_extraction: self._claim_extraction,
            PipelineStage.evidence_retrieval: self._evidence_retrieval,
            PipelineStage.scoring: self._scoring,
            PipelineStage.report_generation: self._report_generation,
        }

    async def submit(self, youtube_url: str, transcript_id: int | None = None) -> PipelineJobDetail:
        job = await self.repository.create_job(
            youtube_url=youtube_url,
            max_attempts=self.settings.pipeline_retry_attempts,
            transcript_id=transcript_id,
        )
        await self.queue.enqueue(job.id)
        self.logger.info(
            "pipeline_job_queued",
            extra={"job_id": job.id, "backend": "asyncio", "youtube_url": youtube_url},
        )
        return job

    async def retry(self, job_id: int) -> PipelineJobDetail:
        await self.repository.reset_failed_job(job_id)
        await self.queue.enqueue(job_id)
        return await self.repository.get_job(job_id)

    async def cancel(self, job_id: int) -> PipelineJobDetail:
        await self.repository.cancel_job(job_id)
        return await self.repository.get_job(job_id)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        for job_id in await self.repository.recoverable_job_ids():
            await self.queue.enqueue(job_id)
        for index in range(self.settings.pipeline_worker_count):
            self._workers.append(asyncio.create_task(self._worker(index)))
        self.logger.info(
            "pipeline_workers_started",
            extra={"worker_count": self.settings.pipeline_worker_count, "backend": "asyncio"},
        )

    async def stop(self) -> None:
        self._running = False
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self.logger.info("pipeline_workers_stopped", extra={"backend": "asyncio"})

    def health(self) -> WorkerHealth:
        return WorkerHealth(
            running=self._running,
            worker_count=len(self._workers),
            queue_size=self.queue.size(),
        )

    async def _worker(self, worker_id: int) -> None:
        while self._running:
            job_id = await self.queue.dequeue()
            try:
                await self.run_job(job_id, worker_id=worker_id)
            finally:
                if isinstance(self.queue, AsyncioPipelineQueue):
                    self.queue.task_done()

    async def run_job(self, job_id: int, worker_id: int | None = None) -> PipelineJobDetail:
        if await self.repository.is_canceled(job_id):
            return await self.repository.get_job(job_id)
        await self.repository.mark_job_running(job_id)
        self.logger.info("pipeline_job_started", extra={"job_id": job_id, "worker_id": worker_id})
        try:
            for index, stage in enumerate(PIPELINE_STAGES):
                if await self.repository.is_canceled(job_id):
                    raise PipelineCanceledError("Pipeline job was canceled.")
                progress = index / len(PIPELINE_STAGES)
                await self.repository.update_job_progress(job_id, stage, progress)
                await self._run_stage(job_id, stage)
            await self.repository.mark_job_succeeded(job_id)
        except Exception as error:
            if isinstance(error, PipelineCanceledError):
                return await self.repository.get_job(job_id)
            message = user_facing_pipeline_error(str(error))
            should_retry = await self.repository.mark_job_retrying(job_id, message)
            if should_retry:
                delay = self.settings.pipeline_retry_backoff_seconds
                self.logger.warning(
                    "pipeline_job_retrying",
                    extra={"job_id": job_id, "delay_seconds": delay, "error": message},
                )
                await asyncio.sleep(delay)
                await self.queue.enqueue(job_id)
            else:
                await self.repository.mark_job_failed(job_id, message)
                self.logger.exception("pipeline_job_failed", extra={"job_id": job_id})
        return await self.repository.get_job(job_id)

    async def _run_stage(self, job_id: int, stage: PipelineStage) -> None:
        if await self.repository.is_canceled(job_id):
            raise PipelineCanceledError("Pipeline job was canceled.")
        job = await self.repository.get_job(job_id)
        attempt = job.retry_count + 1
        await self.repository.start_stage(job_id, stage, attempt)
        started_at = time.perf_counter()
        self.logger.info(
            "pipeline_stage_started",
            extra={"job_id": job_id, "stage": stage.value, "attempt": attempt},
        )
        try:
            metadata = await self._handlers[stage](job)
            await self.repository.complete_stage(job_id, stage, started_at, metadata)
            self.logger.info(
                "pipeline_stage_succeeded",
                extra={"job_id": job_id, "stage": stage.value, **metadata},
            )
        except Exception as error:
            await self.repository.fail_stage(job_id, stage, started_at, str(error))
            raise

    async def _transcript_ingestion(self, job: PipelineJobDetail) -> dict[str, Any]:
        if job.transcript_id is not None:
            return {"transcript_id": job.transcript_id, "recovered": True}
        transcript = await self.transcript_service.create_from_youtube_url(job.youtube_url)
        await self.repository.update_context(job.id, transcript_id=transcript.id)
        return {
            "transcript_id": transcript.id,
            "segments": transcript.segment_count,
            "chunks": transcript.chunk_count,
        }

    async def _chunking(self, job: PipelineJobDetail) -> dict[str, Any]:
        transcript_id = self._require_transcript_id(await self.repository.get_job(job.id))
        transcript = await self.transcript_service.get_transcript(transcript_id)
        return {"transcript_id": transcript_id, "chunks": transcript.chunk_count}

    async def _claim_extraction(self, job: PipelineJobDetail) -> dict[str, Any]:
        transcript_id = self._require_transcript_id(await self.repository.get_job(job.id))
        result = await self.claim_service.extract_claims_for_transcript(transcript_id)
        claim_ids = [claim.id for claim in result.claims if claim.id is not None]
        await self.repository.update_context(job.id, claim_ids=claim_ids)
        return {"transcript_id": transcript_id, "claims": len(claim_ids)}

    async def _evidence_retrieval(self, job: PipelineJobDetail) -> dict[str, Any]:
        current = await self.repository.get_job(job.id)
        claim_ids = self._require_claim_ids(current)
        evidence_count = 0
        for claim_id in claim_ids:
            result = await self.evidence_service.retrieve_evidence_for_claim(
                claim_id,
                max_results=10,
            )
            evidence_count += len(result.evidence)
        return {"claims": len(claim_ids), "evidence_sources": evidence_count}

    async def _scoring(self, job: PipelineJobDetail) -> dict[str, Any]:
        current = await self.repository.get_job(job.id)
        claim_ids = self._require_claim_ids(current)
        scored = 0
        for claim_id in claim_ids:
            await self.scoring_service.score_claim(claim_id)
            scored += 1
        return {"claims": scored}

    async def _report_generation(self, job: PipelineJobDetail) -> dict[str, Any]:
        transcript_id = self._require_transcript_id(await self.repository.get_job(job.id))
        report = await self.report_service.build_report(transcript_id)
        report_payload = report.model_dump(mode="json")
        await self.repository.update_context(job.id, report=report_payload)
        return {
            "transcript_id": transcript_id,
            "claims": report.verdict_summary.total_claims,
            "average_confidence": report.verdict_summary.average_confidence,
        }

    def _require_transcript_id(self, job: PipelineJobDetail) -> int:
        if job.transcript_id is None:
            raise RuntimeError("Pipeline job has no transcript id.")
        return job.transcript_id

    def _require_claim_ids(self, job: PipelineJobDetail) -> list[int]:
        if not job.claim_ids:
            raise RuntimeError("Pipeline job has no stored claim ids.")
        return job.claim_ids


def user_facing_pipeline_error(message: str) -> str:
    lowered = message.lower()
    if "caption" in lowered and any(term in lowered for term in ("missing", "not found", "none")):
        return (
            "No usable captions were found for this video. "
            "Upload a transcript file and run again."
        )
    if "caption" in lowered and any(
        term in lowered for term in ("blocked", "disabled", "unavailable")
    ):
        return (
            "YouTube captions are blocked or unavailable for this video. "
            "Upload a transcript file instead."
        )
    if "metadata" in lowered or "video" in lowered and "not found" in lowered:
        return "Video metadata could not be read. Check that the URL is public and valid."
    if "provider" in lowered or "api key" in lowered or "search" in lowered or "llm" in lowered:
        return f"Provider error. Check configured LLM and search credentials. Details: {message}"
    return message or "Pipeline failed."
