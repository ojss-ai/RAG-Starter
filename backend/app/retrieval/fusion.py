from collections import defaultdict
from typing import Hashable


def rrf(rankings: list[list[Hashable]], k: int = 60) -> list[tuple[Hashable, float]]:
    """Reciprocal Rank Fusion (FR-8): score(d) = Σ over rankings 1/(k + rank(d)),
    rank starting at 1. Returns (id, score) sorted descending; deterministic tie-break
    on the string form of the id."""
    scores: dict[Hashable, float] = defaultdict(float)
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda t: (-t[1], str(t[0])))
