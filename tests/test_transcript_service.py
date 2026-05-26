from pathlib import Path

import pytest

from evidencechain.core.config import Settings
from evidencechain.models.transcript import TranscriptFormat
from evidencechain.services.transcript_service import TranscriptParseError, TranscriptService
from evidencechain.storage.database import initialize_database


def test_parse_srt_preserves_timestamps() -> None:
    service = TranscriptService()
    content = """1
00:00:01,000 --> 00:00:03,500
First line.

2
00:00:04,000 --> 00:00:06,000
Second line.
"""

    segments = service.parse_transcript(content, TranscriptFormat.srt)

    assert len(segments) == 2
    assert segments[0].start_seconds == 1
    assert segments[0].end_seconds == 3.5
    assert segments[0].text == "First line."


def test_parse_vtt_normalizes_caption_tags() -> None:
    service = TranscriptService()
    content = """WEBVTT

00:00:01.000 --> 00:00:03.000
<c>Hello</c> &amp; welcome
"""

    segments = service.parse_transcript(content, TranscriptFormat.vtt)

    assert segments[0].text == "Hello & welcome"


def test_parse_json_supports_segments_shape() -> None:
    service = TranscriptService()
    content = """
    {
      "segments": [
        {"start": 2.0, "duration": 3.0, "text": "A JSON transcript."}
      ]
    }
    """

    segments = service.parse_transcript(content, TranscriptFormat.json)

    assert segments[0].start_seconds == 2
    assert segments[0].end_seconds == 5
    assert segments[0].text == "A JSON transcript."


def test_parse_empty_txt_fails() -> None:
    service = TranscriptService()

    with pytest.raises(TranscriptParseError):
        service.parse_transcript("   ", TranscriptFormat.txt)


async def test_store_and_load_transcript(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await initialize_database(settings)
    service = TranscriptService(settings=settings)

    detail = await service.create_from_upload(
        filename="sample.srt",
        content=b"1\n00:00:01,000 --> 00:00:02,000\nStored line.\n",
        youtube_url="https://www.youtube.com/watch?v=abc123",
        title="Stored",
        video_id="abc123",
    )
    loaded = await service.get_transcript(detail.id)

    assert loaded.metadata.video_id == "abc123"
    assert loaded.segment_count == 1
    assert loaded.chunk_count == 1
    assert loaded.segments[0].text == "Stored line."


async def test_create_from_youtube_url_retries_and_stores_metadata(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'youtube.db'}",
        transcript_retry_attempts=2,
        transcript_retry_backoff_seconds=0,
    )
    await initialize_database(settings)
    attempts = 0

    async def fetch_info(_url: str) -> dict:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("temporary failure")
        return {
            "id": "abc123",
            "title": "Video title",
            "channel": "Channel name",
            "duration": 42,
            "subtitles": {"en": [{"ext": "vtt", "url": "https://caption.example/vtt"}]},
        }

    service = TranscriptService(settings=settings, youtube_info_fetcher=fetch_info)

    async def download_text(_url: str) -> str:
        return "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nFetched transcript.\n"

    service._download_text = download_text  # type: ignore[method-assign]

    detail = await service.create_from_youtube_url("https://www.youtube.com/watch?v=abc123")

    assert attempts == 2
    assert detail.metadata.title == "Video title"
    assert detail.metadata.channel == "Channel name"
    assert detail.segments[0].text == "Fetched transcript."
