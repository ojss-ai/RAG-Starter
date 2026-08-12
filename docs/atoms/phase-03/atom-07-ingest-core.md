# atom-07-ingest-core

- Status: COMMITTED
- Phase: phase-03-ingestion (`docs/plans/phase-03-ingestion.md`, item §03.1)
- Traces: FR-1, FR-2, NFR-8
- Depends on: atom-06
- Mode: normal
- Created: 2026-07-12

## Purpose

The ingestion primitives exist: text extraction (txt/md/pdf), a token-based chunker with a
configurable overlapping window, and the embedding-provider interface with a deterministic
offline fake and an OpenAI-compatible batch implementation.

## Files

| Path | Action |
|---|---|
| `backend/app/ingest/__init__.py`, `extract.py`, `chunker.py`, `embeddings.py` | create |
| `backend/tests/test_ingest_core.py` | create |

## Implementation

```python file=backend/app/ingest/__init__.py
```

```python file=backend/app/ingest/extract.py
import io
from pathlib import PurePosixPath


class ExtractionError(Exception):
    pass


TEXT_EXTS = {".txt", ".md"}


def extract_text(filename: str, data: bytes) -> str:
    """Best-effort plain text from a supported document. Raises ExtractionError on
    unsupported types or unreadable content."""
    ext = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    if ext in TEXT_EXTS:
        return data.decode("utf-8", errors="replace")
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:  # pypdf raises a zoo of types on corrupt files
            raise ExtractionError(f"unreadable pdf: {exc}") from exc
    raise ExtractionError(f"unsupported extension: {ext}")
```

```python file=backend/app/ingest/chunker.py
def chunk_text(text: str, size_tokens: int, overlap_pct: int) -> list[str]:
    """Whitespace-token sliding window (FR-1). `size_tokens` per chunk, stepping
    `size - size*overlap_pct/100` tokens, so consecutive chunks share ~overlap_pct%.
    The token measure is deliberately model-agnostic (see SRS Open Q 2)."""
    if size_tokens <= 0:
        raise ValueError("size_tokens must be positive")
    overlap = max(0, min(overlap_pct, 90))
    tokens = text.split()
    if not tokens:
        return []
    step = max(1, size_tokens - (size_tokens * overlap) // 100)
    chunks = []
    for start in range(0, len(tokens), step):
        window = tokens[start:start + size_tokens]
        chunks.append(" ".join(window))
        if start + size_tokens >= len(tokens):
            break
    return chunks
```

```python file=backend/app/ingest/embeddings.py
import hashlib
import math
from typing import Protocol

import httpx

from app.config import Settings


class EmbeddingProvider(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class EmbeddingError(Exception):
    pass


class FakeEmbeddingProvider:
    """Deterministic, offline: hash n-grams into a fixed-dim unit vector. Similar texts
    share n-grams and therefore direction — good enough for relevance-shaped tests."""

    def __init__(self, dim: int = 32):
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        words = text.lower().split()
        for w in words:
            h = int.from_bytes(hashlib.sha256(w.encode()).digest()[:4], "big")
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class OpenAIEmbeddingProvider:
    """OpenAI-compatible /embeddings endpoint, batched (FR-2)."""

    def __init__(self, api_base: str, api_key: str, model: str, dim: int, batch: int = 64,
                 client: httpx.AsyncClient | None = None):
        self.dim = dim
        self._model = model
        self._batch = batch
        self._client = client or httpx.AsyncClient(
            base_url=api_base, headers={"Authorization": f"Bearer {api_key}"}, timeout=60)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch):
            batch = texts[i:i + self._batch]
            try:
                r = await self._client.post("/embeddings",
                                            json={"model": self._model, "input": batch})
                r.raise_for_status()
            except httpx.HTTPError as exc:
                raise EmbeddingError(str(exc)) from exc
            data = r.json()["data"]
            out.extend(item["embedding"] for item in sorted(data, key=lambda d: d["index"]))
        return out


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embed_provider == "fake":
        return FakeEmbeddingProvider(dim=settings.embed_dim)
    if settings.embed_provider == "openai":
        return OpenAIEmbeddingProvider(settings.embed_api_base, settings.embed_api_key,
                                       settings.embed_model, settings.embed_dim,
                                       settings.embed_batch)
    raise ValueError(f"unknown embed provider: {settings.embed_provider}")
```

## Tests (normal mode: must exist before validate)

```python file=backend/tests/test_ingest_core.py
import httpx
import pytest

from app.ingest.chunker import chunk_text
from app.ingest.embeddings import (EmbeddingError, FakeEmbeddingProvider,
                                   OpenAIEmbeddingProvider)
from app.ingest.extract import ExtractionError, extract_text


def test_chunker_sizes_and_overlap():
    words = " ".join(f"w{i}" for i in range(1000))
    chunks = chunk_text(words, size_tokens=100, overlap_pct=10)
    assert all(len(c.split()) <= 100 for c in chunks)
    # step 90 → second chunk starts at w90: 10-token overlap
    assert chunks[1].split()[0] == "w90"
    # every token is covered
    assert set(words.split()) == {t for c in chunks for t in c.split()}


def test_chunker_edges():
    assert chunk_text("", 512, 10) == []
    assert chunk_text("one two", 512, 10) == ["one two"]
    with pytest.raises(ValueError):
        chunk_text("x", 0, 10)


def test_extract_txt_md_and_unsupported():
    assert extract_text("a.txt", "hello".encode()) == "hello"
    assert extract_text("b.MD", "# hi".encode()) == "# hi"
    with pytest.raises(ExtractionError):
        extract_text("c.exe", b"MZ")


def test_extract_pdf_blank_page():
    from pypdf import PdfWriter
    import io
    buf = io.BytesIO()
    w = PdfWriter()
    w.add_blank_page(width=100, height=100)
    w.write(buf)
    assert extract_text("d.pdf", buf.getvalue()) == ""
    with pytest.raises(ExtractionError):
        extract_text("e.pdf", b"not a pdf at all")


async def test_fake_embedder_deterministic_and_unit_norm():
    p = FakeEmbeddingProvider(dim=16)
    a1, a2 = await p.embed(["alpha beta"]), await p.embed(["alpha beta"])
    assert a1 == a2
    assert len(a1[0]) == 16
    assert abs(sum(v * v for v in a1[0]) - 1.0) < 1e-9
    # related texts closer than unrelated
    [v_ab], [v_ax], [v_zz] = (await p.embed(["alpha beta"]),
                              await p.embed(["alpha gamma"]),
                              await p.embed(["zeta omega"]))
    cos = lambda x, y: sum(a * b for a, b in zip(x, y))
    assert cos(v_ab, v_ax) > cos(v_ab, v_zz)


async def test_openai_embedder_batches_and_errors():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(request.content)
        calls.append(len(body["input"]))
        data = [{"index": i, "embedding": [float(i), 1.0]}
                for i in range(len(body["input"]))]
        return httpx.Response(200, json={"data": data})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                               base_url="https://fake/v1")
    p = OpenAIEmbeddingProvider("https://fake/v1", "k", "m", dim=2, batch=2, client=client)
    out = await p.embed(["a", "b", "c"])
    assert calls == [2, 1]
    assert len(out) == 3

    def down(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    bad = OpenAIEmbeddingProvider("https://fake/v1", "k", "m", dim=2,
                                  client=httpx.AsyncClient(
                                      transport=httpx.MockTransport(down),
                                      base_url="https://fake/v1"))
    with pytest.raises(EmbeddingError):
        await bad.embed(["x"])
```

Notes: chunker guarantees full coverage (`break` only after the window reached the tail).
FakeEmbeddingProvider dim defaults to 32 in tests via settings override — tests here pass
dim explicitly.

## Verification

1. `cd backend && python -m pytest -q` → all green.

## Review Log

- 2026-07-17 — review-atom: freshness ✓ (all embed_*/chunk_* settings exist in config.py; no drift since authoring), completeness ✓ (full code blocks, exact paths, tests listed), traceability ✓ (FR-1, FR-2, NFR-8 / plan §03.1). Certified READY.

## Implementation Log

- 2026-07-17 — Implemented per atom, zero deviations. `pytest -q` → 32 passed.
- 2026-07-17 — VALIDATED. All atom files present with specified behavior; verification
  step (full suite) green. No OPEN findings. review-change clean.
