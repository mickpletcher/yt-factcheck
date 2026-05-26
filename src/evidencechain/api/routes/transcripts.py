from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from evidencechain.models.transcript import (
    TranscriptChunkList,
    TranscriptDetail,
    TranscriptError,
    TranscriptFromUrlRequest,
)
from evidencechain.services.transcript_service import (
    TranscriptFetchError,
    TranscriptNotFoundError,
    TranscriptParseError,
    TranscriptService,
)

router = APIRouter(prefix="/transcripts")


def get_transcript_service() -> TranscriptService:
    return TranscriptService()


@router.post(
    "/from-url",
    response_model=TranscriptDetail,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": TranscriptError},
        status.HTTP_502_BAD_GATEWAY: {"model": TranscriptError},
    },
)
async def create_transcript_from_url(
    request: TranscriptFromUrlRequest,
    service: Annotated[TranscriptService, Depends(get_transcript_service)],
) -> TranscriptDetail:
    try:
        return await service.create_from_youtube_url(request.youtube_url, request.language)
    except TranscriptNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except TranscriptFetchError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.post(
    "/upload",
    response_model=TranscriptDetail,
    responses={status.HTTP_400_BAD_REQUEST: {"model": TranscriptError}},
)
async def upload_transcript(
    service: Annotated[TranscriptService, Depends(get_transcript_service)],
    file: Annotated[
        UploadFile,
        File(description="Transcript file. Supports .txt, .srt, .vtt, .json."),
    ],
    youtube_url: Annotated[str | None, Form()] = None,
    title: Annotated[str, Form()] = "",
    video_id: Annotated[str | None, Form()] = None,
    language: Annotated[str, Form()] = "en",
) -> TranscriptDetail:
    try:
        content = await file.read()
        return await service.create_from_upload(
            filename=file.filename or "transcript.txt",
            content=content,
            youtube_url=youtube_url,
            title=title,
            video_id=video_id,
            language=language,
        )
    except (UnicodeDecodeError, TranscriptParseError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get(
    "/{transcript_id}",
    response_model=TranscriptDetail,
    responses={status.HTTP_404_NOT_FOUND: {"model": TranscriptError}},
)
async def get_transcript(
    transcript_id: int,
    service: Annotated[TranscriptService, Depends(get_transcript_service)],
) -> TranscriptDetail:
    try:
        return await service.get_transcript(transcript_id)
    except TranscriptNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get(
    "/{transcript_id}/chunks",
    response_model=TranscriptChunkList,
    responses={status.HTTP_404_NOT_FOUND: {"model": TranscriptError}},
)
async def get_transcript_chunks(
    transcript_id: int,
    service: Annotated[TranscriptService, Depends(get_transcript_service)],
) -> TranscriptChunkList:
    try:
        chunks = await service.get_chunks(transcript_id)
        return TranscriptChunkList(transcript_id=transcript_id, chunks=chunks)
    except TranscriptNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
