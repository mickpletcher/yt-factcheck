from httpx import ASGITransport, AsyncClient

from evidencechain.main import create_app


async def test_health_endpoint() -> None:
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "evidencechain"}
