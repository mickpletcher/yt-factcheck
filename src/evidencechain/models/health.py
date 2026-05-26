from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class ProviderCapability(BaseModel):
    provider_type: str
    provider: str
    configured: bool
    healthy: bool
    message: str = ""


class ProviderReadinessResponse(BaseModel):
    ready: bool
    providers: list[ProviderCapability]
