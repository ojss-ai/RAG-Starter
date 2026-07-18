import logging
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx

from ragwatcher.config import WatcherConfig

log = logging.getLogger(__name__)


def backoff_delays(base_s: float, retries: int, cap_s: float = 300.0) -> Iterator[float]:
    """1, 2, 4, 8, … seconds, capped (FR-13 retry policy)."""
    for attempt in range(retries):
        yield min(cap_s, base_s * (2 ** attempt))


class Uploader:
    def __init__(self, config: WatcherConfig, client: httpx.Client | None = None):
        self._config = config
        self._client = client or httpx.Client(base_url=config.api_url, timeout=120)

    def upload_once(self, path: Path) -> httpx.Response:
        with path.open("rb") as fh:
            return self._client.post(
                "/api/v1/admin/upload",
                headers={"X-API-Key": self._config.api_key},
                files={"file": (path.name, fh)})

    def upload_with_retry(self, path: Path,
                          sleep: Callable[[float], None]) -> bool:
        """True on success. Network errors / 5xx / 429 back off and retry; any other 4xx is
        permanent (a rejected file will not get better by retrying)."""
        delays = backoff_delays(self._config.backoff_base_s, self._config.max_retries,
                                self._config.backoff_cap_s)
        while True:
            try:
                response = self.upload_once(path)
                if response.status_code < 300:
                    return True
                if response.status_code not in (429,) and response.status_code < 500:
                    log.warning("permanent rejection for %s: %s %s",
                                path.name, response.status_code, response.text[:200])
                    return False
            except httpx.HTTPError as exc:
                log.info("network error uploading %s: %s", path.name, exc)
            delay = next(delays, None)
            if delay is None:
                log.error("gave up on %s after %s retries",
                          path.name, self._config.max_retries)
                return False
            sleep(delay)
