"""In-memory rate limiter — simple, single-process. Phase 2 replaces with RateLimitHook."""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._store: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str):
        now = time.time()
        window_start = now - self.window_seconds
        self._store[key] = [t for t in self._store[key] if t > window_start]
        if len(self._store[key]) >= self.max_requests:
            raise HTTPException(status_code=429, detail="Too many requests, try again later")
        self._store[key].append(now)


login_limiter = RateLimiter(max_requests=5, window_seconds=60)
register_limiter = RateLimiter(max_requests=3, window_seconds=60)


async def login_rate_limit(request: Request):
    login_limiter.check(f"login:{request.client.host}")


async def register_rate_limit(request: Request):
    register_limiter.check(f"register:{request.client.host}")
