from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from evidencechain.models.pipeline import (
    PipelineError,
    PipelineEvent,
    PipelineJobDetail,
    PipelineJobList,
    PipelineMetrics,
    PipelineRunRequest,
    PipelineRunResponse,
    WorkerHealth,
)
from evidencechain.pipelines.orchestration import FactCheckOrchestrator, PipelineNotFoundError

router = APIRouter(prefix="/pipelines")


def get_orchestrator(request: Request) -> FactCheckOrchestrator:
    orchestrator = getattr(request.app.state, "pipeline_orchestrator", None)
    if orchestrator is None:
        orchestrator = FactCheckOrchestrator(settings=request.app.state.settings)
        request.app.state.pipeline_orchestrator = orchestrator
    return orchestrator


@router.post(
    "/factcheck",
    response_model=PipelineRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def queue_factcheck_pipeline(
    request: PipelineRunRequest,
    orchestrator: Annotated[FactCheckOrchestrator, Depends(get_orchestrator)],
) -> PipelineRunResponse:
    job = await orchestrator.submit(str(request.youtube_url))
    return PipelineRunResponse(job_id=job.id, status=job.status)


@router.get("/jobs", response_model=PipelineJobList)
async def list_pipeline_jobs(
    orchestrator: Annotated[FactCheckOrchestrator, Depends(get_orchestrator)],
    limit: int = 25,
) -> PipelineJobList:
    return PipelineJobList(jobs=await orchestrator.repository.list_jobs(limit=limit))


@router.get(
    "/jobs/{job_id}",
    response_model=PipelineJobDetail,
    responses={status.HTTP_404_NOT_FOUND: {"model": PipelineError}},
)
async def get_pipeline_job(
    job_id: int,
    orchestrator: Annotated[FactCheckOrchestrator, Depends(get_orchestrator)],
) -> PipelineJobDetail:
    try:
        return await orchestrator.repository.get_job(job_id)
    except PipelineNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/jobs/{job_id}/retry",
    response_model=PipelineJobDetail,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": PipelineError},
        status.HTTP_404_NOT_FOUND: {"model": PipelineError},
    },
)
async def retry_pipeline_job(
    job_id: int,
    orchestrator: Annotated[FactCheckOrchestrator, Depends(get_orchestrator)],
) -> PipelineJobDetail:
    try:
        return await orchestrator.retry(job_id)
    except PipelineNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get(
    "/jobs/{job_id}/events",
    response_model=list[PipelineEvent],
    responses={status.HTTP_404_NOT_FOUND: {"model": PipelineError}},
)
async def list_pipeline_events(
    job_id: int,
    orchestrator: Annotated[FactCheckOrchestrator, Depends(get_orchestrator)],
    limit: int = 100,
) -> list[PipelineEvent]:
    try:
        return await orchestrator.repository.list_events(job_id, limit=limit)
    except PipelineNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/metrics", response_model=PipelineMetrics)
async def get_pipeline_metrics(
    orchestrator: Annotated[FactCheckOrchestrator, Depends(get_orchestrator)],
) -> PipelineMetrics:
    return await orchestrator.repository.metrics()


@router.get("/workers", response_model=WorkerHealth)
async def get_worker_health(
    orchestrator: Annotated[FactCheckOrchestrator, Depends(get_orchestrator)],
) -> WorkerHealth:
    return orchestrator.health()
