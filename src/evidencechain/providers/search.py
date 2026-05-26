import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

import httpx

from evidencechain.core.config import Settings
from evidencechain.models.factcheck import EvidenceProvider, SearchResult
from evidencechain.providers.base import (
    SearchProvider,
    SearchProviderConfigurationError,
    SearchProviderError,
)


class AsyncRateLimiter:
    def __init__(self, requests_per_second: float) -> None:
        self.minimum_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0.0
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def wait(self) -> None:
        if self.minimum_interval <= 0:
            return
        async with self._lock:
            now = asyncio.get_running_loop().time()
            wait_seconds = self.minimum_interval - (now - self._last_request_at)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            self._last_request_at = asyncio.get_running_loop().time()


class BraveSearchProvider:
    name = EvidenceProvider.brave.value

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if not settings.brave_search_api_key:
            raise SearchProviderConfigurationError("BRAVE_SEARCH_API_KEY is required.")
        self.settings = settings
        self.client = client
        self.rate_limiter = AsyncRateLimiter(settings.evidence_search_rate_limit_per_second)

    async def search(self, query: str, count: int) -> list[SearchResult]:
        payload = await self._with_retry(lambda: self._request(query, count))
        return self._parse_results(query, payload)

    async def _request(self, query: str, count: int) -> dict[str, Any]:
        await self.rate_limiter.wait()
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.settings.brave_search_api_key,
        }
        params: dict[str, str | int] = {
            "q": query,
            "count": min(count, 20),
            "country": "us",
            "search_lang": "en",
            "safesearch": "moderate",
        }
        timeout = httpx.Timeout(self.settings.evidence_search_timeout_seconds)
        if self.client is not None:
            response = await self.client.get(
                self.settings.brave_search_endpoint,
                headers=headers,
                params=params,
            )
        else:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(
                    self.settings.brave_search_endpoint,
                    headers=headers,
                    params=params,
                )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise SearchProviderError("Brave Search returned an invalid response.")
        return payload

    async def _with_retry(
        self,
        operation: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.evidence_search_retry_attempts + 1):
            try:
                return await operation()
            except (httpx.HTTPError, OSError, SearchProviderError) as error:
                last_error = error
                if attempt == self.settings.evidence_search_retry_attempts:
                    break
                await asyncio.sleep(self.settings.evidence_search_retry_backoff_seconds * attempt)
        raise SearchProviderError(str(last_error) if last_error else "Search request failed.")

    def _parse_results(self, query: str, payload: dict[str, Any]) -> list[SearchResult]:
        web_results = payload.get("web", {})
        raw_results = web_results.get("results", []) if isinstance(web_results, dict) else []
        results: list[SearchResult] = []
        if not isinstance(raw_results, list):
            return results
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str) or not url:
                continue
            profile = item.get("profile", {})
            publisher = ""
            if isinstance(profile, dict) and isinstance(profile.get("name"), str):
                publisher = profile["name"]
            if not publisher:
                publisher = self._publisher_from_url(url)
            result = SearchResult.model_validate(
                {
                    "title": str(item.get("title") or ""),
                    "url": url,
                    "snippet": str(item.get("description") or ""),
                    "publisher": publisher,
                    "provider": EvidenceProvider.brave,
                    "query": query,
                    "published_at": str(item["age"]) if item.get("age") else None,
                    "raw": {key: value for key, value in item.items() if isinstance(key, str)},
                }
            )
            results.append(result)
        return results

    def _publisher_from_url(self, url: str) -> str:
        hostname = urlparse(url).hostname or ""
        return hostname.removeprefix("www.")


class TavilySearchProvider:
    name = EvidenceProvider.tavily.value

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if not settings.tavily_api_key:
            raise SearchProviderConfigurationError("TAVILY_API_KEY is required.")
        self.settings = settings
        self.client = client
        self.rate_limiter = AsyncRateLimiter(settings.evidence_search_rate_limit_per_second)

    async def search(self, query: str, count: int) -> list[SearchResult]:
        payload = await self._with_retry(lambda: self._request(query, count))
        return self._parse_results(query, payload)

    async def _request(self, query: str, count: int) -> dict[str, Any]:
        await self.rate_limiter.wait()
        body = {
            "api_key": self.settings.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": min(count, 20),
            "include_answer": False,
            "include_raw_content": False,
        }
        timeout = httpx.Timeout(self.settings.evidence_search_timeout_seconds)
        if self.client is not None:
            response = await self.client.post(self.settings.tavily_search_endpoint, json=body)
        else:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.post(self.settings.tavily_search_endpoint, json=body)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise SearchProviderError("Tavily Search returned an invalid response.")
        return payload

    async def _with_retry(
        self,
        operation: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.evidence_search_retry_attempts + 1):
            try:
                return await operation()
            except (httpx.HTTPError, OSError, SearchProviderError) as error:
                last_error = error
                if attempt == self.settings.evidence_search_retry_attempts:
                    break
                await asyncio.sleep(self.settings.evidence_search_retry_backoff_seconds * attempt)
        raise SearchProviderError(str(last_error) if last_error else "Tavily request failed.")

    def _parse_results(self, query: str, payload: dict[str, Any]) -> list[SearchResult]:
        raw_results = payload.get("results", [])
        results: list[SearchResult] = []
        if not isinstance(raw_results, list):
            return results
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str) or not url:
                continue
            results.append(
                SearchResult.model_validate(
                    {
                        "title": str(item.get("title") or ""),
                        "url": url,
                        "snippet": str(item.get("content") or ""),
                        "publisher": self._publisher_from_url(url),
                        "provider": EvidenceProvider.tavily,
                        "query": query,
                        "raw": {key: value for key, value in item.items() if isinstance(key, str)},
                    }
                )
            )
        return results

    def _publisher_from_url(self, url: str) -> str:
        hostname = urlparse(url).hostname or ""
        return hostname.removeprefix("www.")


class BingSearchProvider:
    name = EvidenceProvider.bing.value

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if not settings.bing_search_api_key:
            raise SearchProviderConfigurationError("BING_SEARCH_API_KEY is required.")
        self.settings = settings
        self.client = client
        self.rate_limiter = AsyncRateLimiter(settings.evidence_search_rate_limit_per_second)

    async def search(self, query: str, count: int) -> list[SearchResult]:
        payload = await self._with_retry(lambda: self._request(query, count))
        return self._parse_results(query, payload)

    async def _request(self, query: str, count: int) -> dict[str, Any]:
        await self.rate_limiter.wait()
        headers = {"Ocp-Apim-Subscription-Key": self.settings.bing_search_api_key}
        params: dict[str, str | int] = {
            "q": query,
            "count": min(count, 50),
            "safeSearch": "Moderate",
        }
        timeout = httpx.Timeout(self.settings.evidence_search_timeout_seconds)
        if self.client is not None:
            response = await self.client.get(
                self.settings.bing_search_endpoint,
                headers=headers,
                params=params,
            )
        else:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(
                    self.settings.bing_search_endpoint,
                    headers=headers,
                    params=params,
                )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise SearchProviderError("Bing Search returned an invalid response.")
        return payload

    async def _with_retry(
        self,
        operation: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.evidence_search_retry_attempts + 1):
            try:
                return await operation()
            except (httpx.HTTPError, OSError, SearchProviderError) as error:
                last_error = error
                if attempt == self.settings.evidence_search_retry_attempts:
                    break
                await asyncio.sleep(self.settings.evidence_search_retry_backoff_seconds * attempt)
        raise SearchProviderError(str(last_error) if last_error else "Bing request failed.")

    def _parse_results(self, query: str, payload: dict[str, Any]) -> list[SearchResult]:
        web_pages = payload.get("webPages", {})
        raw_results = web_pages.get("value", []) if isinstance(web_pages, dict) else []
        results: list[SearchResult] = []
        if not isinstance(raw_results, list):
            return results
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str) or not url:
                continue
            results.append(
                SearchResult.model_validate(
                    {
                        "title": str(item.get("name") or ""),
                        "url": url,
                        "snippet": str(item.get("snippet") or ""),
                        "publisher": self._publisher_from_url(url),
                        "provider": EvidenceProvider.bing,
                        "query": query,
                        "published_at": str(item["dateLastCrawled"])
                        if item.get("dateLastCrawled")
                        else None,
                        "raw": {key: value for key, value in item.items() if isinstance(key, str)},
                    }
                )
            )
        return results

    def _publisher_from_url(self, url: str) -> str:
        hostname = urlparse(url).hostname or ""
        return hostname.removeprefix("www.")


class FailoverSearchProvider:
    def __init__(self, providers: list[SearchProvider]) -> None:
        if not providers:
            raise ValueError("At least one search provider is required for failover.")
        self.providers = providers
        self.name = providers[0].name

    async def search(self, query: str, count: int) -> list[SearchResult]:
        errors: list[str] = []
        for provider in self.providers:
            try:
                results = await provider.search(query, count)
            except SearchProviderError as error:
                errors.append(f"{provider.name}: {error}")
                continue
            if results:
                return results
            errors.append(f"{provider.name}: no results")
        raise SearchProviderError("All search providers failed. " + " | ".join(errors))


class UnconfiguredSearchProvider:
    def __init__(self, provider: EvidenceProvider, settings: Settings) -> None:
        self.provider = provider
        self.settings = settings
        self.name = provider.value

    async def search(self, query: str, count: int) -> list[SearchResult]:
        raise SearchProviderConfigurationError(
            f"{self.provider.value} search is wired but not implemented in this stage."
        )
