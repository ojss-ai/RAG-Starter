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
