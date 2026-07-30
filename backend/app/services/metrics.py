from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


@dataclass
class HttpMetrics:
    """In-process request/error counters (FR-20). Single-process like the rate limiter;
    swap for Prometheus in multi-worker deployments."""

    requests: int = 0
    errors: int = 0
    by_status: dict[int, int] = field(default_factory=dict)

    def observe(self, status_code: int) -> None:
        self.requests += 1
        self.by_status[status_code] = self.by_status.get(status_code, 0) + 1
        if status_code >= 500:
            self.errors += 1

    @property
    def error_rate(self) -> float:
        return round(self.errors / self.requests, 4) if self.requests else 0.0


class HttpMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            request.app.state.http_metrics.observe(500)
            raise
        request.app.state.http_metrics.observe(response.status_code)
        return response
