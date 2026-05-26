from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from evidencechain.models.factcheck import (
    ClaimError,
    EvidenceList,
    EvidenceRetrievalRequest,
    EvidenceRetrievalResult,
)
from evidencechain.services.evidence_service import (
    EvidenceNotFoundError,
    EvidenceProviderError,
    EvidenceService,
)

router = APIRouter(prefix="/evidence")


def get_evidence_service() -> EvidenceService:
    return EvidenceService()


@router.post(
    "/retrieve",
    response_model=EvidenceRetrievalResult,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ClaimError},
        status.HTTP_502_BAD_GATEWAY: {"model": ClaimError},
    },
)
async def retrieve_evidence(
    request: EvidenceRetrievalRequest,
    service: Annotated[EvidenceService, Depends(get_evidence_service)],
) -> EvidenceRetrievalResult:
    try:
        if request.claim_id is not None:
            return await service.retrieve_evidence_for_claim(
                request.claim_id,
                provider_name=request.provider,
                max_results=request.max_results,
            )
        if request.claim_text is None:
            raise ValueError("claim_id or claim_text is required")
        return await service.retrieve_evidence_for_text(
            request.claim_text,
            provider_name=request.provider,
            max_results=request.max_results,
        )
    except EvidenceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (EvidenceProviderError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.get(
    "/claims/{claim_id}",
    response_model=EvidenceList,
)
async def list_claim_evidence(
    claim_id: int,
    service: Annotated[EvidenceService, Depends(get_evidence_service)],
) -> EvidenceList:
    return EvidenceList(
        claim_id=claim_id,
        evidence=await service.list_claim_evidence(claim_id),
    )
