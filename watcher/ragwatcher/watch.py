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
