from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from evidencechain.models.factcheck import ClaimError, ScoringList, ScoringRequest, ScoringResult
from evidencechain.services.scoring_service import ScoringNotFoundError, ScoringService

router = APIRouter(prefix="/scoring")


def get_scoring_service() -> ScoringService:
    return ScoringService()


@router.post(
    "/score",
    response_model=ScoringResult,
    responses={status.HTTP_404_NOT_FOUND: {"model": ClaimError}},
)
async def score_claim(
    request: ScoringRequest,
    service: Annotated[ScoringService, Depends(get_scoring_service)],
) -> ScoringResult:
    try:
        return await service.score_claim(request.claim_id, request.min_evidence)
    except ScoringNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/claims/{claim_id}",
    response_model=ScoringResult,
    responses={status.HTTP_404_NOT_FOUND: {"model": ClaimError}},
)
async def score_claim_by_id(
    claim_id: int,
    service: Annotated[ScoringService, Depends(get_scoring_service)],
) -> ScoringResult:
    try:
        return await service.score_claim(claim_id)
    except ScoringNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get(
    "/claims/{claim_id}",
    response_model=ScoringList,
    responses={status.HTTP_404_NOT_FOUND: {"model": ClaimError}},
)
async def list_claim_scores(
    claim_id: int,
    service: Annotated[ScoringService, Depends(get_scoring_service)],
) -> ScoringList:
    try:
        return ScoringList(claim_id=claim_id, results=await service.list_results(claim_id))
    except ScoringNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
