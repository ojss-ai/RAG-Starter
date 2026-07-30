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
