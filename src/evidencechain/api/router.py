from fastapi import APIRouter

from evidencechain.api.routes import (
    claims,
    evidence,
    health,
    pipelines,
    reports,
    scoring,
    transcripts,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(transcripts.router, tags=["transcripts"])
api_router.include_router(claims.router, tags=["claims"])
api_router.include_router(evidence.router, tags=["evidence"])
api_router.include_router(scoring.router, tags=["scoring"])
api_router.include_router(reports.router, tags=["reports"])
api_router.include_router(pipelines.router, tags=["pipelines"])
