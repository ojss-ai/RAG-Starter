import logging
import time
from collections.abc import Callable
from pathlib import Path

from ragwatcher.config import WatcherConfig
from ragwatcher.state import StateCache, sha256_file
from ragwatcher.uploader import Uploader

log = logging.getLogger(__name__)


def process_file(path: Path, config: WatcherConfig, cache: StateCache,
                 uploader: Uploader, sleep: Callable[[float], None] = time.sleep) -> str:
    """Returns 'uploaded' | 'skipped' | 'failed' | 'ignored'."""
    if path.suffix.lower() not in config.extensions or not path.is_file():
        return "ignored"
    sha = sha256_file(path)
    if not cache.needs_upload(path, sha):  # FR-13 idempotency
        return "skipped"
    if uploader.upload_with_retry(path, sleep=sleep):
        cache.mark_uploaded(path, sha, path.stat().st_mtime)
        return "uploaded"
    return "failed"


def scan_existing(config: WatcherConfig, cache: StateCache, uploader: Uploader,
                  sleep: Callable[[float], None] = time.sleep) -> dict[str, int]:
    """One pass over the watch dir (startup catch-up / --once mode)."""
    counts = {"uploaded": 0, "skipped": 0, "failed": 0, "ignored": 0}
    for path in sorted(config.watch_dir.rglob("*")):
        if path.name == config.db_path.name:
            continue
        result = process_file(path, config, cache, uploader, sleep=sleep)
        counts[result] += 1
    return counts
