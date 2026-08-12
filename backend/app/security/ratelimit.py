import time
from dataclasses import dataclass, field

from fastapi import HTTPException, Request
from fastapi.responses import Response


@dataclass
class _Bucket:
    tokens: float
    updated: float


@dataclass
class RateLimiter:
    """In-memory token bucket per (route_class, caller). Single-process only — the keyed
    interface is Redis-swappable without touching endpoints (plan §5 limitation)."""

    buckets: dict[str, _Bucket] = field(default_factory=dict)

    def check(self, key: str, rpm: int, now: float | None = None) -> tuple[bool, float]:
        """Returns (allowed, retry_after_seconds)."""
        now = time.monotonic() if now is None else now
        rate = rpm / 60.0
        b = self.buckets.get(key)
        if b is None:
            b = _Bucket(tokens=float(rpm), updated=now)
            self.buckets[key] = b
        b.tokens = min(float(rpm), b.tokens + (now - b.updated) * rate)
        b.updated = now
        if b.tokens >= 1.0:
            b.tokens -= 1.0
            return True, 0.0
        return False, (1.0 - b.tokens) / rate


def _caller_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    api_key = request.headers.get("x-api-key", "")
    if api_key:
        return f"key:{api_key[:16]}"
    if auth:
        return f"jwt:{auth[-24:]}"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


def rate_limit(route_class: str):
    """Dependency factory: `Depends(rate_limit("chat"))` / `Depends(rate_limit("upload"))`."""

    async def dependency(request: Request, response: Response) -> None:
        settings = request.app.state.settings
        rpm = {"chat": settings.rate_chat_rpm, "upload": settings.rate_upload_rpm}[route_class]
        limiter: RateLimiter = request.app.state.rate_limiter
        allowed, retry_after = limiter.check(f"{route_class}:{_caller_key(request)}", rpm)
        if not allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded",
                                headers={"Retry-After": str(max(1, round(retry_after)))})

    return dependency
