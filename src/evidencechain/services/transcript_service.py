import asyncio
import importlib
import json
import re
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import aiosqlite
import httpx
from pydantic import HttpUrl

from evidencechain.core.config import Settings, get_settings
from evidencechain.models.transcript import (
    TranscriptChunk,
    TranscriptDetail,
    TranscriptFormat,
    TranscriptSegment,
    TranscriptSource,
    VideoMetadata,
)
from evidencechain.utils.chunking import chunk_transcript

YoutubeInfoFetcher = Callable[[str], Coroutine[Any, Any, dict[str, Any]]]


class TranscriptServiceError(Exception):
    pass


class TranscriptNotFoundError(TranscriptServiceError):
    pass


class TranscriptParseError(TranscriptServiceError):
    pass


class TranscriptFetchError(TranscriptServiceError):
    pass


class TranscriptService:
    def __init__(
        self,
        settings: Settings | None = None,
        youtube_info_fetcher: YoutubeInfoFetcher | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.youtube_info_fetcher = youtube_info_fetcher or self._fetch_youtube_info

    async def extract_transcript(self, youtube_url: str) -> list[TranscriptSegment]:
        detail = await self.create_from_youtube_url(youtube_url)
        return detail.segments

    async def create_from_youtube_url(
        self,
        youtube_url: str | HttpUrl,
        language: str = "en",
    ) -> TranscriptDetail:
        url = str(youtube_url)
        info = await self._with_retry(lambda: self.youtube_info_fetcher(url))
        metadata = self._metadata_from_youtube_info(info, url)
        caption_url = self._select_caption_url(info, language)
        if not caption_url:
            raise TranscriptNotFoundError("No YouTube transcript was found for this video.")

        caption_text = await self._with_retry(lambda: self._download_text(caption_url))
        raw_format = self._format_from_caption_url(caption_url)
        segments = self.parse_transcript(caption_text, raw_format)

        return await self.store_transcript(
            metadata=metadata,
            source=TranscriptSource.youtube,
            raw_format=raw_format,
            language=language,
            segments=segments,
        )

    async def create_from_upload(
        self,
        filename: str,
        content: bytes,
        youtube_url: str | HttpUrl | None = None,
        title: str = "",
        video_id: str | None = None,
        language: str = "en",
    ) -> TranscriptDetail:
        raw_format = self._format_from_filename(filename)
        text = content.decode("utf-8-sig")
        segments = self.parse_transcript(text, raw_format)
        metadata = VideoMetadata(
            video_id=video_id or Path(filename).stem,
            youtube_url=str(youtube_url or "https://www.youtube.com/watch?v=uploaded"),
            title=title or Path(filename).stem,
        )

        return await self.store_transcript(
            metadata=metadata,
            source=TranscriptSource.upload,
            raw_format=raw_format,
            language=language,
            segments=segments,
        )

    def parse_transcript(
        self,
        text: str,
        raw_format: TranscriptFormat,
    ) -> list[TranscriptSegment]:
        if raw_format == TranscriptFormat.txt:
            return self._parse_txt(text)
        if raw_format == TranscriptFormat.srt:
            return self._parse_srt(text)
        if raw_format == TranscriptFormat.vtt:
            return self._parse_vtt(text)
        if raw_format == TranscriptFormat.json:
            return self._parse_json(text)
        raise TranscriptParseError(f"Unsupported transcript format: {raw_format}")

    async def store_transcript(
        self,
        metadata: VideoMetadata,
        source: TranscriptSource,
        raw_format: TranscriptFormat,
        language: str,
        segments: list[TranscriptSegment],
    ) -> TranscriptDetail:
        normalized_segments = self._normalize_segments(segments)
        chunks = chunk_transcript(
            normalized_segments,
            max_chars=self.settings.transcript_chunk_max_chars,
            overlap_segments=self.settings.transcript_chunk_overlap_segments,
        )

        database_path = self.settings.sqlite_path
        database_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(database_path) as connection:
            await connection.execute("PRAGMA foreign_keys = ON")
            cursor = await connection.execute(
                """
                INSERT INTO transcripts (
                    video_id, youtube_url, title, channel, duration_seconds, upload_date,
                    source, language, raw_format
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.video_id,
                    str(metadata.youtube_url),
                    metadata.title,
                    metadata.channel,
                    metadata.duration_seconds,
                    metadata.upload_date,
                    source.value,
                    language,
                    raw_format.value,
                ),
            )
            transcript_id = cursor.lastrowid
            if transcript_id is None:
                raise TranscriptServiceError("Failed to store transcript.")

            await connection.executemany(
                """
                INSERT INTO transcript_segments (
                    transcript_id, position, start_seconds, end_seconds, text
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (transcript_id, index, segment.start_seconds, segment.end_seconds, segment.text)
                    for index, segment in enumerate(normalized_segments)
                ],
            )
            await connection.executemany(
                """
                INSERT INTO transcript_chunks (
                    transcript_id, position, start_seconds, end_seconds, text,
                    segment_start_index, segment_end_index
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        transcript_id,
                        chunk.position,
                        chunk.start_seconds,
                        chunk.end_seconds,
                        chunk.text,
                        chunk.segment_start_index,
                        chunk.segment_end_index,
                    )
                    for chunk in chunks
                ],
            )
            await connection.commit()

        return await self.get_transcript(transcript_id)

    async def get_transcript(self, transcript_id: int) -> TranscriptDetail:
        database_path = self.settings.sqlite_path
        async with aiosqlite.connect(database_path) as connection:
            connection.row_factory = aiosqlite.Row
            transcript_row = await self._fetch_one(
                connection,
                "SELECT * FROM transcripts WHERE id = ?",
                (transcript_id,),
            )
            if transcript_row is None:
                raise TranscriptNotFoundError(f"Transcript {transcript_id} was not found.")

            segment_rows = await self._fetch_all(
                connection,
                """
                SELECT start_seconds, end_seconds, text
                FROM transcript_segments
                WHERE transcript_id = ?
                ORDER BY position
                """,
                (transcript_id,),
            )
            chunk_rows = await self._fetch_all(
                connection,
                """
                SELECT position, start_seconds, end_seconds, text,
                       segment_start_index, segment_end_index
                FROM transcript_chunks
                WHERE transcript_id = ?
                ORDER BY position
                """,
                (transcript_id,),
            )

        return self._detail_from_rows(transcript_row, segment_rows, chunk_rows)

    async def get_chunks(self, transcript_id: int) -> list[TranscriptChunk]:
        return (await self.get_transcript(transcript_id)).chunks

    async def _with_retry(self, operation: Callable[[], Coroutine[Any, Any, Any]]) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.transcript_retry_attempts + 1):
            try:
                return await operation()
            except (httpx.HTTPError, OSError, TranscriptFetchError) as error:
                last_error = error
                if attempt == self.settings.transcript_retry_attempts:
                    break
                await asyncio.sleep(self.settings.transcript_retry_backoff_seconds * attempt)
        raise TranscriptFetchError(str(last_error) if last_error else "Transcript fetch failed.")

    async def _fetch_youtube_info(self, youtube_url: str) -> dict[str, Any]:
        def fetch() -> dict[str, Any]:
            youtube_dl = importlib.import_module("yt_dlp")

            with youtube_dl.YoutubeDL(
                {"quiet": True, "skip_download": True, "no_warnings": True}
            ) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                if not isinstance(info, dict):
                    raise TranscriptFetchError("yt-dlp returned an invalid response.")
                return info

        return await asyncio.to_thread(fetch)

    async def _download_text(self, url: str) -> str:
        timeout = httpx.Timeout(self.settings.transcript_fetch_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _metadata_from_youtube_info(self, info: dict[str, Any], youtube_url: str) -> VideoMetadata:
        return VideoMetadata(
            video_id=str(info.get("id") or ""),
            youtube_url=youtube_url,
            title=str(info.get("title") or ""),
            channel=str(info.get("channel") or info.get("uploader") or ""),
            duration_seconds=info.get("duration"),
            upload_date=info.get("upload_date"),
        )

    def _select_caption_url(self, info: dict[str, Any], language: str) -> str | None:
        caption_groups = [info.get("subtitles") or {}, info.get("automatic_captions") or {}]
        for captions in caption_groups:
            entries = (
                captions.get(language)
                or captions.get(language.split("-")[0])
                or captions.get("en")
            )
            if not entries:
                continue
            sorted_entries = sorted(
                entries,
                key=lambda item: 0 if item.get("ext") in {"vtt", "json3"} else 1,
            )
            url = sorted_entries[0].get("url")
            if isinstance(url, str):
                return url
        return None

    def _format_from_caption_url(self, url: str) -> TranscriptFormat:
        if "fmt=json3" in url or url.endswith(".json"):
            return TranscriptFormat.json
        return TranscriptFormat.vtt

    def _format_from_filename(self, filename: str) -> TranscriptFormat:
        suffix = Path(filename).suffix.lower().lstrip(".")
        try:
            return TranscriptFormat(suffix)
        except ValueError as error:
            message = "Uploaded transcript must be .txt, .srt, .vtt, or .json."
            raise TranscriptParseError(message) from error

    def _parse_txt(self, text: str) -> list[TranscriptSegment]:
        normalized = " ".join(text.split())
        if not normalized:
            raise TranscriptParseError("Transcript text is empty.")
        return [TranscriptSegment(start_seconds=0, end_seconds=0, text=normalized)]

    def _parse_srt(self, text: str) -> list[TranscriptSegment]:
        return self._parse_timed_blocks(text)

    def _parse_vtt(self, text: str) -> list[TranscriptSegment]:
        lines = [
            line
            for line in text.splitlines()
            if line.strip()
            and not line.strip().startswith(("WEBVTT", "Kind:", "Language:", "NOTE"))
        ]
        return self._parse_timed_blocks("\n".join(lines))

    def _parse_timed_blocks(self, text: str) -> list[TranscriptSegment]:
        pattern = re.compile(
            r"(?P<start>\d{1,2}:)?\d{1,2}:\d{2}[\.,]\d{3}\s+-->\s+"
            r"(?P<end>(?:\d{1,2}:)?\d{1,2}:\d{2}[\.,]\d{3}).*?(?:\n(?P<body>.*?))"
            r"(?=\n\s*\n|\Z)",
            re.DOTALL,
        )
        segments: list[TranscriptSegment] = []
        for match in pattern.finditer(text.strip()):
            first_line = match.group(0).splitlines()[0]
            start_text, end_text = [part.strip().split()[0] for part in first_line.split("-->")]
            body = self._clean_caption_text(match.group("body") or "")
            if body:
                segments.append(
                    TranscriptSegment(
                        start_seconds=self._parse_timestamp(start_text),
                        end_seconds=self._parse_timestamp(end_text),
                        text=body,
                    )
                )
        if not segments:
            raise TranscriptParseError("No timed transcript segments were found.")
        return segments

    def _parse_json(self, text: str) -> list[TranscriptSegment]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise TranscriptParseError("Transcript JSON is invalid.") from error

        if isinstance(payload, dict) and "events" in payload:
            return self._parse_youtube_json3(payload)

        raw_segments = payload.get("segments") if isinstance(payload, dict) else payload
        if not isinstance(raw_segments, list):
            raise TranscriptParseError("Transcript JSON must be a list or contain a segments list.")

        segments: list[TranscriptSegment] = []
        for item in raw_segments:
            if not isinstance(item, dict):
                continue
            text_value = item.get("text")
            if not text_value:
                continue
            start = item.get("start_seconds", item.get("start", 0)) or 0
            end = item.get("end_seconds", item.get("end", start))
            if "duration" in item and "end" not in item and "end_seconds" not in item:
                end = float(start) + float(item["duration"])
            segments.append(
                TranscriptSegment(
                    start_seconds=float(start),
                    end_seconds=float(end or start),
                    text=str(text_value),
                )
            )

        if not segments:
            raise TranscriptParseError("Transcript JSON did not contain any segments.")
        return segments

    def _parse_youtube_json3(self, payload: dict[str, Any]) -> list[TranscriptSegment]:
        segments: list[TranscriptSegment] = []
        for event in payload.get("events", []):
            if not isinstance(event, dict) or "segs" not in event:
                continue
            text = "".join(
                str(seg.get("utf8", "")) for seg in event["segs"] if isinstance(seg, dict)
            )
            text = self._clean_caption_text(text)
            if not text:
                continue
            start = float(event.get("tStartMs", 0)) / 1000
            end = start + (float(event.get("dDurationMs", 0)) / 1000)
            segments.append(TranscriptSegment(start_seconds=start, end_seconds=end, text=text))
        if not segments:
            raise TranscriptParseError("YouTube JSON transcript did not contain any segments.")
        return segments

    def _normalize_segments(self, segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
        normalized = [
            TranscriptSegment(
                start_seconds=segment.start_seconds,
                end_seconds=segment.end_seconds,
                text=segment.text,
            )
            for segment in segments
            if segment.text.strip()
        ]
        if not normalized:
            raise TranscriptParseError("Transcript has no usable text.")
        return sorted(normalized, key=lambda segment: segment.start_seconds)

    def _parse_timestamp(self, value: str) -> float:
        normalized = value.replace(",", ".")
        parts = normalized.split(":")
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    def _clean_caption_text(self, value: str) -> str:
        no_tags = re.sub(r"<[^>]+>", "", value)
        no_entities = no_tags.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        return " ".join(no_entities.split())

    async def _fetch_one(
        self,
        connection: aiosqlite.Connection,
        query: str,
        parameters: tuple[Any, ...],
    ) -> aiosqlite.Row | None:
        cursor = await connection.execute(query, parameters)
        return await cursor.fetchone()

    async def _fetch_all(
        self,
        connection: aiosqlite.Connection,
        query: str,
        parameters: tuple[Any, ...],
    ) -> list[aiosqlite.Row]:
        cursor = await connection.execute(query, parameters)
        return list(await cursor.fetchall())

    def _detail_from_rows(
        self,
        transcript_row: aiosqlite.Row,
        segment_rows: list[aiosqlite.Row],
        chunk_rows: list[aiosqlite.Row],
    ) -> TranscriptDetail:
        metadata = VideoMetadata(
            video_id=transcript_row["video_id"],
            youtube_url=transcript_row["youtube_url"],
            title=transcript_row["title"],
            channel=transcript_row["channel"],
            duration_seconds=transcript_row["duration_seconds"],
            upload_date=transcript_row["upload_date"],
        )
        segments = [
            TranscriptSegment(
                start_seconds=row["start_seconds"],
                end_seconds=row["end_seconds"],
                text=row["text"],
            )
            for row in segment_rows
        ]
        chunks = [
            TranscriptChunk(
                position=row["position"],
                start_seconds=row["start_seconds"],
                end_seconds=row["end_seconds"],
                text=row["text"],
                segment_start_index=row["segment_start_index"],
                segment_end_index=row["segment_end_index"],
            )
            for row in chunk_rows
        ]
        return TranscriptDetail(
            id=transcript_row["id"],
            metadata=metadata,
            source=TranscriptSource(transcript_row["source"]),
            language=transcript_row["language"],
            raw_format=TranscriptFormat(transcript_row["raw_format"]),
            segment_count=len(segments),
            chunk_count=len(chunks),
            created_at=transcript_row["created_at"],
            segments=segments,
            chunks=chunks,
        )
