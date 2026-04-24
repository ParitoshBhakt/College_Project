import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.utils.exceptions import SentiFaceError


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.window_seconds = 60
        self.buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        recent = [t for t in self.buckets[ip] if now - t < self.window_seconds]
        if len(recent) >= settings.rate_limit_per_minute:
            raise SentiFaceError("RATE_LIMIT_EXCEEDED", "Too many requests. Try again in a minute.", 429)
        recent.append(now)
        self.buckets[ip] = recent
        return await call_next(request)