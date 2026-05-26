from fastapi import APIRouter, Request

from evidencechain.services.admin_service import AdminService

router = APIRouter(prefix="/admin")


@router.get("/providers")
async def get_provider_metrics(request: Request) -> dict[str, object]:
    service = AdminService(settings=request.app.state.settings)
    return await service.provider_metrics()
