from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, PlainTextResponse

from evidencechain.models.factcheck import ClaimError
from evidencechain.models.report import ReportExport, ReportFormat
from evidencechain.services.report_service import ReportNotFoundError, ReportService

router = APIRouter(prefix="/reports")


def get_report_service() -> ReportService:
    return ReportService()


@router.get(
    "/transcripts/{transcript_id}",
    response_model=ReportExport,
    responses={status.HTTP_404_NOT_FOUND: {"model": ClaimError}},
)
async def get_report(
    transcript_id: int,
    service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportExport:
    try:
        return await service.build_report(transcript_id)
    except ReportNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get(
    "/transcripts/{transcript_id}.html",
    response_class=HTMLResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": ClaimError}},
)
async def get_html_report(
    transcript_id: int,
    service: Annotated[ReportService, Depends(get_report_service)],
) -> HTMLResponse:
    try:
        return HTMLResponse(await service.render_report(transcript_id, ReportFormat.html))
    except ReportNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get(
    "/transcripts/{transcript_id}.md",
    response_class=PlainTextResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": ClaimError}},
)
async def get_markdown_report(
    transcript_id: int,
    service: Annotated[ReportService, Depends(get_report_service)],
) -> PlainTextResponse:
    try:
        return PlainTextResponse(
            await service.render_report(transcript_id, ReportFormat.markdown),
            media_type="text/markdown; charset=utf-8",
        )
    except ReportNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/transcripts/{transcript_id}/exports/{report_format}",
    response_model=dict[str, str],
    responses={status.HTTP_404_NOT_FOUND: {"model": ClaimError}},
)
async def export_report(
    transcript_id: int,
    report_format: ReportFormat,
    service: Annotated[ReportService, Depends(get_report_service)],
) -> dict[str, str]:
    try:
        path = await service.export_report(transcript_id, report_format)
    except ReportNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return {"path": str(path), "format": report_format.value}
