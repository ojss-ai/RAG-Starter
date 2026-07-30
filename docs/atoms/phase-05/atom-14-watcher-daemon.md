# atom-14-watcher-daemon

- Status: COMMITTED
- Phase: phase-05-clients (`docs/plans/phase-05-clients.md`, item §05.1)
- Traces: FR-12, FR-13
- Depends on: atom-09 (upload endpoint + API keys live)
- Mode: normal
- Created: 2026-07-12

## Purpose

The standalone watcher daemon exists (`python -m ragwatcher`): watchdog file events with a
debounce window, a SQLite state cache keyed by SHA-256 so unchanged files are never
re-uploaded, multipart uploads authenticated with an ingest API key, and exponential
back-off retries that survive API outages. No FastAPI/backend imports — it's a pure client.

## Files

| Path | Action |
|---|---|
| `watcher/requirements.txt`, `watcher/requirements-dev.txt`, `watcher/pytest.ini` | create |
| `watcher/ragwatcher/__init__.py`, `config.py`, `state.py`, `uploader.py`, `core.py`, `watch.py`, `__main__.py` | create |
| `watcher/tests/__init__.py`, `test_watcher.py` | create |

## Implementation

```text file=watcher/requirements.txt
watchdog>=4.0
httpx>=0.27
```

```text file=watcher/requirements-dev.txt
pytest>=8.3
```

```ini file=watcher/pytest.ini
[pytest]
testpaths = tests
```

```python file=watcher/ragwatcher/__init__.py
```

```python file=watcher/ragwatcher/config.py
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class WatcherConfig:
    api_url: str
    api_key: str
    watch_dir: Path
    db_path: Path
    extensions: tuple[str, ...] = (".pdf", ".txt", ".md")
    debounce_s: float = 2.0
    max_retries: int = 8
    backoff_base_s: float = 1.0
    backoff_cap_s: float = 300.0

    @classmethod
    def from_env(cls) -> "WatcherConfig":
        watch_dir = Path(os.environ.get("RAGWATCH_WATCH_DIR", ".")).resolve()
        exts = tuple(e.strip().lower() for e in
                     os.environ.get("RAGWATCH_EXTS", ".pdf,.txt,.md").split(",") if e.strip())
        return cls(
            api_url=os.environ.get("RAGWATCH_API_URL", "http://localhost:8000"),
            api_key=os.environ.get("RAGWATCH_API_KEY", ""),
            watch_dir=watch_dir,
            db_path=Path(os.environ.get("RAGWATCH_DB_PATH",
                                        str(watch_dir / ".ragwatcher.db"))),
            extensions=exts,
            debounce_s=float(os.environ.get("RAGWATCH_DEBOUNCE_S", "2.0")),
            max_retries=int(os.environ.get("RAGWATCH_MAX_RETRIES", "8")),
            backoff_base_s=float(os.environ.get("RAGWATCH_BACKOFF_BASE_S", "1.0")),
        )
```

```python file=watcher/ragwatcher/state.py
import hashlib
import sqlite3
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class StateCache:
    """Local SQLite registry (FR-13): remembers what was uploaded and with which hash."""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS files ("
            " path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, mtime REAL NOT NULL,"
            " uploaded_at TEXT NOT NULL DEFAULT (datetime('now')))")
        self._conn.commit()

    def needs_upload(self, path: Path, sha256: str) -> bool:
        row = self._conn.execute("SELECT sha256 FROM files WHERE path = ?",
                                 (str(path),)).fetchone()
        return row is None or row[0] != sha256

    def mark_uploaded(self, path: Path, sha256: str, mtime: float) -> None:
        self._conn.execute(
            "INSERT INTO files (path, sha256, mtime) VALUES (?, ?, ?) "
            "ON CONFLICT(path) DO UPDATE SET sha256 = excluded.sha256, "
            " mtime = excluded.mtime, uploaded_at = datetime('now')",
            (str(path), sha256, mtime))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
```

```python file=watcher/ragwatcher/uploader.py
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
```

```python file=watcher/ragwatcher/core.py
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
```

```python file=watcher/ragwatcher/watch.py
import logging
import queue
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ragwatcher.config import WatcherConfig
from ragwatcher.core import process_file, scan_existing
from ragwatcher.state import StateCache
from ragwatcher.uploader import Uploader

log = logging.getLogger(__name__)


class _Handler(FileSystemEventHandler):
    def __init__(self, work: "queue.Queue[Path]"):
        self._work = work

    def on_created(self, event: FileSystemEvent) -> None:
        self._dispatch(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._dispatch(event)

    def _dispatch(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._work.put(Path(str(event.src_path)))


def run(config: WatcherConfig) -> None:
    """Blocking daemon loop (FR-12): startup catch-up scan, then event-driven with a
    debounce window so editors that write repeatedly trigger one upload."""
    cache = StateCache(config.db_path)
    uploader = Uploader(config)
    log.info("catch-up scan: %s", scan_existing(config, cache, uploader))

    work: "queue.Queue[Path]" = queue.Queue()
    observer = Observer()
    observer.schedule(_Handler(work), str(config.watch_dir), recursive=True)
    observer.start()
    log.info("watching %s", config.watch_dir)

    pending: dict[Path, float] = {}
    try:
        while True:
            try:
                path = work.get(timeout=0.5)
                pending[path] = time.monotonic()
            except queue.Empty:
                pass
            now = time.monotonic()
            ready = [p for p, t in pending.items() if now - t >= config.debounce_s]
            for path in ready:
                del pending[path]
                result = process_file(path, config, cache, uploader)
                if result != "ignored":
                    log.info("%s: %s", path.name, result)
    except KeyboardInterrupt:
        log.info("stopping")
    finally:
        observer.stop()
        observer.join()
        cache.close()
```

```python file=watcher/ragwatcher/__main__.py
import argparse
import logging
import sys

from ragwatcher.config import WatcherConfig
from ragwatcher.core import scan_existing
from ragwatcher.state import StateCache
from ragwatcher.uploader import Uploader
from ragwatcher.watch import run


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser("ragwatcher",
                                     description="RagStarter folder watcher daemon")
    parser.add_argument("--once", action="store_true",
                        help="single catch-up scan, then exit (no watching)")
    args = parser.parse_args()

    config = WatcherConfig.from_env()
    if not config.api_key:
        print("RAGWATCH_API_KEY is required (create one in the admin dashboard)",
              file=sys.stderr)
        return 2
    if not config.watch_dir.is_dir():
        print(f"watch dir does not exist: {config.watch_dir}", file=sys.stderr)
        return 2

    if args.once:
        cache = StateCache(config.db_path)
        counts = scan_existing(config, cache, Uploader(config))
        print(counts)
        cache.close()
        return 0
    run(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

```python file=watcher/tests/__init__.py
```

## Tests (normal mode: must exist before validate)

```python file=watcher/tests/test_watcher.py
from pathlib import Path

import httpx

from ragwatcher.config import WatcherConfig
from ragwatcher.core import process_file, scan_existing
from ragwatcher.state import StateCache, sha256_file
from ragwatcher.uploader import Uploader, backoff_delays


def _config(tmp_path: Path, **overrides) -> WatcherConfig:
    defaults = dict(api_url="http://api.test", api_key="rgs_test",
                    watch_dir=tmp_path, db_path=tmp_path / ".ragwatcher.db",
                    backoff_base_s=1.0, max_retries=3)
    defaults.update(overrides)
    return WatcherConfig(**defaults)


def _uploader(config, handler):
    return Uploader(config, client=httpx.Client(
        base_url=config.api_url, transport=httpx.MockTransport(handler)))


def test_backoff_doubles_and_caps():
    assert list(backoff_delays(1.0, 5, cap_s=6.0)) == [1.0, 2.0, 4.0, 6.0, 6.0]
    assert list(backoff_delays(1.0, 0)) == []


def test_state_cache_hash_semantics(tmp_path):
    cache = StateCache(tmp_path / "state.db")
    f = tmp_path / "a.txt"
    f.write_text("v1")
    sha = sha256_file(f)
    assert cache.needs_upload(f, sha)
    cache.mark_uploaded(f, sha, f.stat().st_mtime)
    assert not cache.needs_upload(f, sha)          # unchanged → skip
    assert cache.needs_upload(f, "other-hash")     # changed → upload
    cache.close()


def test_uploader_retries_on_5xx_then_succeeds(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    attempts, sleeps = [], []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(503) if len(attempts) < 3 else httpx.Response(200, json={})

    config = _config(tmp_path)
    ok = _uploader(config, handler).upload_with_retry(f, sleep=sleeps.append)
    assert ok
    assert len(attempts) == 3
    assert sleeps == [1.0, 2.0]  # exponential back-off between attempts


def test_uploader_gives_up_after_retries(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    config = _config(tmp_path, max_retries=2)
    ok = _uploader(config, lambda r: httpx.Response(503)).upload_with_retry(
        f, sleep=lambda s: None)
    assert not ok


def test_uploader_4xx_is_permanent_no_retry(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(415, text="unsupported")

    ok = _uploader(_config(tmp_path), handler).upload_with_retry(f, sleep=lambda s: None)
    assert not ok
    assert len(attempts) == 1


def test_process_file_upload_skip_reupload(tmp_path):
    config = _config(tmp_path)
    cache = StateCache(config.db_path)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "rgs_test"
        seen.append(1)
        return httpx.Response(200, json={})

    uploader = _uploader(config, handler)
    f = tmp_path / "doc.txt"
    f.write_text("version one")

    assert process_file(f, config, cache, uploader) == "uploaded"
    assert process_file(f, config, cache, uploader) == "skipped"   # FR-13
    f.write_text("version two")
    assert process_file(f, config, cache, uploader) == "uploaded"
    assert len(seen) == 2

    assert process_file(tmp_path / "skip.exe", config, cache, uploader) == "ignored"
    cache.close()


def test_scan_existing_counts_and_ignores_state_db(tmp_path):
    config = _config(tmp_path)
    cache = StateCache(config.db_path)
    (tmp_path / "a.txt").write_text("alpha")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.md").write_text("beta")
    (tmp_path / "c.exe").write_text("nope")

    uploader = _uploader(config, lambda r: httpx.Response(200, json={}))
    counts = scan_existing(config, cache, uploader)
    assert counts["uploaded"] == 2
    assert counts["skipped"] == 0
    counts2 = scan_existing(config, cache, uploader)
    assert counts2["skipped"] == 2
    cache.close()
```

Notes: everything is sync (watchdog is thread-based); `sleep` is injected so back-off tests
run instantly. The daemon loop and observer thread are deliberately thin — all logic lives
in `core.py`/`uploader.py`/`state.py`, which the tests cover without threads.

## Verification

1. `cd watcher && python -m pytest -q` → all green (own venv or backend's).
2. Manual: `RAGWATCH_WATCH_DIR=... RAGWATCH_API_KEY=rgs_... python -m ragwatcher --once` against the running API → files appear in the ledger.

## Review Log

- 2026-07-17 — review-atom: freshness ✓ (upload endpoint + X-API-Key auth live per atoms 05/09; pure client, no backend imports), completeness ✓, traceability ✓ (FR-12/13 / plan §05.1). Certified READY.

## Implementation Log

- 2026-07-17 — Implemented per atom, zero deviations. `cd watcher && pytest -q` → 7 passed.
- 2026-07-17 — VALIDATED. Manual `--once` against the live API with a real ingest key:
  2 files uploaded, ledger shows both INDEXED; second scan skips (hash cache). Back-off,
  permanent-4xx, idempotency covered by tests. No OPEN findings. review-change clean.
