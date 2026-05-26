from httpx import ASGITransport, AsyncClient

from evidencechain.core.config import Settings
from evidencechain.main import create_app


async def test_health_endpoint() -> None:
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "evidencechain"}


async def test_api_access_token_is_required_when_configured() -> None:
    app = create_app(Settings(api_access_token="secret"))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rejected = await client.get("/api/v1/health")
        accepted = await client.get("/api/v1/health", headers={"x-api-key": "secret"})

    assert rejected.status_code == 401
    assert accepted.status_code == 200


async def test_api_rate_limit_rejects_excess_requests() -> None:
    app = create_app(Settings(api_rate_limit_per_minute=1))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.get("/api/v1/health")
        second = await client.get("/api/v1/health")

    assert first.status_code == 200
    assert second.status_code == 429


async def test_provider_readiness_reports_llm_and_search_state() -> None:
    app = create_app(Settings(llm_provider="ollama", search_provider="brave"))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert {item["provider_type"] for item in payload["providers"]} == {"llm", "search"}
