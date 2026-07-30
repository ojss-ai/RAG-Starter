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
