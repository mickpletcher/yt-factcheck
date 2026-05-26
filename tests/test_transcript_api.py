from pathlib import Path

from httpx import ASGITransport, AsyncClient

from evidencechain.api.routes.transcripts import get_transcript_service
from evidencechain.core.config import Settings
from evidencechain.main import create_app
from evidencechain.services.transcript_service import TranscriptService
from evidencechain.storage.database import initialize_database


async def test_upload_transcript_endpoint_stores_segments_and_chunks(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    await initialize_database(settings)
    service = TranscriptService(settings=settings)
    app = create_app(settings)
    app.dependency_overrides[get_transcript_service] = lambda: service
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/transcripts/upload",
            data={
                "youtube_url": "https://www.youtube.com/watch?v=abc123",
                "title": "API upload",
                "video_id": "abc123",
            },
            files={
                "file": (
                    "api.vtt",
                    "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAPI transcript.\n",
                    "text/vtt",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["video_id"] == "abc123"
    assert payload["segments"][0]["text"] == "API transcript."
    assert payload["chunks"][0]["start_seconds"] == 1


async def test_missing_transcript_returns_404(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    await initialize_database(settings)
    service = TranscriptService(settings=settings)
    app = create_app(settings)
    app.dependency_overrides[get_transcript_service] = lambda: service
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/transcripts/999")

    assert response.status_code == 404
