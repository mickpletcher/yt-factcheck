from fastapi import APIRouter

from evidencechain.api.routes import claims, health, transcripts

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(transcripts.router, tags=["transcripts"])
api_router.include_router(claims.router, tags=["claims"])
