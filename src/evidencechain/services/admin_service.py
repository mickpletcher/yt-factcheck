from typing import Any

import aiosqlite

from evidencechain.core.config import Settings, get_settings


class AdminService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def provider_metrics(self) -> dict[str, Any]:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            connection.row_factory = aiosqlite.Row
            usage_rows = await self._fetch_all(
                connection,
                """
                SELECT provider_type, provider, COUNT(*) AS calls,
                       SUM(total_tokens) AS total_tokens,
                       SUM(cost_usd) AS cost_usd,
                       SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failures
                FROM provider_usage_events
                GROUP BY provider_type, provider
                ORDER BY provider_type, provider
                """,
                (),
            )
            cache_row = await self._fetch_one(
                connection,
                """
                SELECT
                    SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) AS hits,
                    COUNT(*) AS total
                FROM provider_usage_events
                WHERE provider_type = 'search'
                """,
                (),
            )
            failed_search_rows = await self._fetch_all(
                connection,
                """
                SELECT provider, search_query, error_message, created_at
                FROM provider_usage_events
                WHERE provider_type = 'search' AND success = 0
                ORDER BY created_at DESC
                LIMIT 25
                """,
                (),
            )
        hits = int(cache_row["hits"] or 0) if cache_row else 0
        total = int(cache_row["total"] or 0) if cache_row else 0
        return {
            "providers": [
                {
                    "type": row["provider_type"],
                    "provider": row["provider"],
                    "calls": row["calls"],
                    "total_tokens": row["total_tokens"] or 0,
                    "cost_usd": round(float(row["cost_usd"] or 0), 6),
                    "failures": row["failures"] or 0,
                }
                for row in usage_rows
            ],
            "cache": {
                "hits": hits,
                "total": total,
                "hit_rate": round(hits / total, 4) if total else 0.0,
            },
            "failed_search_queries": [
                {
                    "provider": row["provider"],
                    "query": row["search_query"],
                    "error": row["error_message"],
                    "created_at": row["created_at"],
                }
                for row in failed_search_rows
            ],
        }

    async def record_search_event(
        self,
        provider: str,
        query: str,
        cache_hit: bool,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            await connection.execute(
                """
                INSERT INTO provider_usage_events (
                    provider_type, provider, cache_hit, search_query, success, error_message
                )
                VALUES ('search', ?, ?, ?, ?, ?)
                """,
                (provider, int(cache_hit), query, int(success), error_message),
            )
            await connection.commit()

    async def record_llm_event(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_usd: float,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        async with aiosqlite.connect(self.settings.sqlite_path) as connection:
            await connection.execute(
                """
                INSERT INTO provider_usage_events (
                    provider_type, provider, model, prompt_tokens, completion_tokens,
                    total_tokens, cost_usd, success, error_message
                )
                VALUES ('llm', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    cost_usd,
                    int(success),
                    error_message,
                ),
            )
            await connection.commit()

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
