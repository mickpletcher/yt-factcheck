from typing import Any

import aiosqlite

from evidencechain.core.config import Settings, get_settings
from evidencechain.models.factcheck import (
    Claim,
    ClaimExtractionChunk,
    ClaimExtractionProviderOutput,
    ClaimExtractionResult,
)
from evidencechain.models.transcript import TranscriptChunk, TranscriptSegment
from evidencechain.prompts.claim_extraction import (
    CLAIM_EXTRACTION_PROMPT_VERSION,
    CLAIM_EXTRACTION_SYSTEM_PROMPT,
    build_claim_extraction_prompt,
)
from evidencechain.providers.base import LLMProvider, LLMProviderError, LLMRequest
from evidencechain.providers.registry import get_llm_provider
from evidencechain.utils.chunking import chunk_transcript


class ClaimServiceError(Exception):
    pass


class ClaimProviderError(ClaimServiceError):
    pass


class ClaimNotFoundError(ClaimServiceError):
    pass


class ClaimService:
    def __init__(
        self,
        settings: Settings | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or get_llm_provider(settings=self.settings)

    async def extract_claims(self, segments: list[TranscriptSegment]) -> list[Claim]:
        chunks = chunk_transcript(
            segments,
            max_chars=self.settings.transcript_chunk_max_chars,
            overlap_segments=self.settings.transcript_chunk_overlap_segments,
        )
        return await self.extract_claims_from_chunks(chunks)

    async def extract_claims_for_transcript(self, transcript_id: int) -> ClaimExtractionResult:
        chunks = await self._get_transcript_chunks(transcript_id)
        claims = await self.extract_claims_from_chunks(chunks, transcript_id=transcript_id)
        stored_claims = await self._store_claims(transcript_id, claims)
        return ClaimExtractionResult(
            transcript_id=transcript_id,
            provider=self.provider.name,
            prompt_version=CLAIM_EXTRACTION_PROMPT_VERSION,
            claims=stored_claims,
        )

    async def extract_claims_from_chunks(
        self,
        chunks: list[TranscriptChunk],
        transcript_id: int | None = None,
    ) -> list[Claim]:
        claims: list[Claim] = []
        for chunk in chunks:
            extraction_chunk = ClaimExtractionChunk.from_transcript_chunk(chunk)
            provider_output = await self._extract_chunk_claims(extraction_chunk)
            for candidate in provider_output.claims:
                claims.append(
                    Claim(
                        transcript_id=transcript_id,
                        chunk_position=chunk.position,
                        text=candidate.text,
                        category=candidate.category,
                        confidence=candidate.confidence,
                        start_seconds=candidate.start_seconds,
                        end_seconds=candidate.end_seconds,
                        source_text=chunk.text,
                    )
                )
        return claims

    async def list_claims(self, transcript_id: int) -> list[Claim]:
        database_path = self.settings.sqlite_path
        async with aiosqlite.connect(database_path) as connection:
            connection.row_factory = aiosqlite.Row
            rows = await self._fetch_all(
                connection,
                """
                SELECT *
                FROM claims
                WHERE transcript_id = ?
                ORDER BY start_seconds, id
                """,
                (transcript_id,),
            )
        return [self._claim_from_row(row) for row in rows]

    async def get_claim(self, claim_id: int) -> Claim:
        database_path = self.settings.sqlite_path
        async with aiosqlite.connect(database_path) as connection:
            connection.row_factory = aiosqlite.Row
            row = await self._fetch_one(
                connection,
                "SELECT * FROM claims WHERE id = ?",
                (claim_id,),
            )
        if row is None:
            raise ClaimNotFoundError(f"Claim {claim_id} was not found.")
        return self._claim_from_row(row)

    async def _extract_chunk_claims(
        self,
        chunk: ClaimExtractionChunk,
    ) -> ClaimExtractionProviderOutput:
        request = LLMRequest(
            system_prompt=CLAIM_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=build_claim_extraction_prompt(chunk),
            temperature=0.0,
        )
        try:
            return await self.provider.generate_structured(request, ClaimExtractionProviderOutput)
        except LLMProviderError as error:
            raise ClaimProviderError(str(error)) from error

    async def _get_transcript_chunks(self, transcript_id: int) -> list[TranscriptChunk]:
        database_path = self.settings.sqlite_path
        async with aiosqlite.connect(database_path) as connection:
            connection.row_factory = aiosqlite.Row
            transcript = await self._fetch_one(
                connection,
                "SELECT id FROM transcripts WHERE id = ?",
                (transcript_id,),
            )
            if transcript is None:
                raise ClaimNotFoundError(f"Transcript {transcript_id} was not found.")
            rows = await self._fetch_all(
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
        return [
            TranscriptChunk(
                position=row["position"],
                start_seconds=row["start_seconds"],
                end_seconds=row["end_seconds"],
                text=row["text"],
                segment_start_index=row["segment_start_index"],
                segment_end_index=row["segment_end_index"],
            )
            for row in rows
        ]

    async def _store_claims(self, transcript_id: int, claims: list[Claim]) -> list[Claim]:
        database_path = self.settings.sqlite_path
        async with aiosqlite.connect(database_path) as connection:
            await connection.execute("PRAGMA foreign_keys = ON")
            cursor = await connection.execute(
                """
                INSERT INTO claim_extraction_runs (transcript_id, provider, prompt_version)
                VALUES (?, ?, ?)
                """,
                (transcript_id, self.provider.name, CLAIM_EXTRACTION_PROMPT_VERSION),
            )
            run_id = cursor.lastrowid
            if run_id is None:
                raise ClaimServiceError("Failed to store claim extraction run.")
            await connection.execute("DELETE FROM claims WHERE transcript_id = ?", (transcript_id,))
            for claim in claims:
                await connection.execute(
                    """
                    INSERT INTO claims (
                        transcript_id, extraction_run_id, chunk_position, text, category,
                        confidence, start_seconds, end_seconds, source_text
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        transcript_id,
                        run_id,
                        claim.chunk_position,
                        claim.text,
                        claim.category.value,
                        claim.confidence,
                        claim.start_seconds,
                        claim.end_seconds,
                        claim.source_text,
                    ),
                )
            await connection.commit()
        return await self.list_claims(transcript_id)

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

    def _claim_from_row(self, row: aiosqlite.Row) -> Claim:
        return Claim(
            id=row["id"],
            transcript_id=row["transcript_id"],
            chunk_position=row["chunk_position"],
            text=row["text"],
            category=row["category"],
            confidence=row["confidence"],
            start_seconds=row["start_seconds"],
            end_seconds=row["end_seconds"],
            source_text=row["source_text"],
            created_at=row["created_at"],
        )
