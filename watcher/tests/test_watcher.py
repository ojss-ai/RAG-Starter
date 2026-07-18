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
