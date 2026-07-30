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
