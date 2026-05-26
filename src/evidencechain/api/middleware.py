import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from evidencechain.core.config import Settings


class AccessControlMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self.settings.api_access_token or not request.url.path.startswith("/api/"):
            return await call_next(request)
        provided = request.headers.get("x-api-key") or _bearer_token(
            request.headers.get("authorization", "")
        )
        if provided != self.settings.api_access_token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "API access token is required."},
            )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        limit = self.settings.api_rate_limit_per_minute
        if limit <= 0 or not request.url.path.startswith("/api/"):
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self.requests[client]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= limit:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded."},
            )
        window.append(now)
        return await call_next(request)


def _bearer_token(header: str) -> str:
    prefix = "Bearer "
    if header.startswith(prefix):
        return header.removeprefix(prefix).strip()
    return ""
