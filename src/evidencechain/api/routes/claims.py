from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from evidencechain.models.factcheck import (
    Claim,
    ClaimError,
    ClaimExtractionRequest,
    ClaimExtractionResult,
    ClaimList,
)
from evidencechain.providers.registry import get_llm_provider
from evidencechain.services.claim_service import (
    ClaimNotFoundError,
    ClaimProviderError,
    ClaimService,
)

router = APIRouter(prefix="/claims")


def get_claim_service() -> ClaimService:
    return ClaimService()


@router.post(
    "/extract",
    response_model=ClaimExtractionResult,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ClaimError},
        status.HTTP_502_BAD_GATEWAY: {"model": ClaimError},
    },
)
async def extract_claims(
    request: ClaimExtractionRequest,
    service: Annotated[ClaimService, Depends(get_claim_service)],
) -> ClaimExtractionResult:
    try:
        if request.provider:
            service.provider = get_llm_provider(request.provider, service.settings)
        return await service.extract_claims_for_transcript(request.transcript_id)
    except ClaimNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (ClaimProviderError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.get(
    "/transcripts/{transcript_id}",
    response_model=ClaimList,
)
async def list_transcript_claims(
    transcript_id: int,
    service: Annotated[ClaimService, Depends(get_claim_service)],
) -> ClaimList:
    return ClaimList(transcript_id=transcript_id, claims=await service.list_claims(transcript_id))


@router.get(
    "/{claim_id}",
    response_model=Claim,
    responses={status.HTTP_404_NOT_FOUND: {"model": ClaimError}},
)
async def get_claim(
    claim_id: int,
    service: Annotated[ClaimService, Depends(get_claim_service)],
) -> Claim:
    try:
        return await service.get_claim(claim_id)
    except ClaimNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
