"""Rerankers and the evidence-coverage measure used by the agent's grader."""
from __future__ import annotations

from typing import Callable

from .schema import Chunk
from .textutils import tokenize


def _bigrams(toks: list[str]) -> set[tuple[str, str]]:
    return set(zip(toks, toks[1:]))


def coverage(query: str, chunks: list[Chunk], idf: Callable[[str], float]) -> float:
    """IDF-weighted share of query terms present anywhere in the given chunks (0..1).

    Unknown terms get the highest idf, so a question about something absent from the
    corpus (e.g. 'MongoDB') cannot look well covered.
    """
    q = set(tokenize(query))
    if not q:
        return 0.0
    have: set[str] = set()
    for c in chunks:
        have.update(tokenize(c.index_text))
    total = sum(idf(t) for t in q)
    got = sum(idf(t) for t in q if t in have)
    return got / total if total else 0.0


class LexicalReranker:
    """Offline reranker: term coverage + phrase (bigram) match + title match."""

    name = "lexical"

    def __init__(self, idf: Callable[[str], float]):
        self.idf = idf

    def score(self, query: str, chunk: Chunk) -> float:
        qt = tokenize(query)
        if not qt:
            return 0.0
        qset = set(qt)
        ct = tokenize(chunk.index_text)
        cset = set(ct)
        total = sum(self.idf(t) for t in qset) or 1.0
        cov = sum(self.idf(t) for t in qset if t in cset) / total
        qb = _bigrams(qt)
        bi = (len(qb & _bigrams(ct)) / len(qb)) if qb else 0.0
        title = set(tokenize(chunk.title + " " + chunk.section))
        t_cov = (
            sum(self.idf(t) for t in qset if t in title) / total if title else 0.0
        )
        return min(1.0, cov + 0.25 * bi + 0.15 * t_cov)

    def rerank(self, query: str, chunks: list[Chunk]) -> list[tuple[Chunk, float]]:
        scored = [(c, self.score(query, c)) for c in chunks]
        return sorted(scored, key=lambda x: -x[1])  # stable: ties keep retrieval order


class CrossEncoderReranker:
    """Real cross-encoder. Needs sentence-transformers; not exercised in this repo's tests."""

    name = "cross-encoder"

    def __init__(self, model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model)

    def rerank(self, query: str, chunks: list[Chunk]) -> list[tuple[Chunk, float]]:
        scores = self.model.predict([(query, c.index_text) for c in chunks])
        return sorted(zip(chunks, map(float, scores)), key=lambda x: -x[1])
