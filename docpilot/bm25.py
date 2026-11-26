"""Small, dependency-free BM25 with an inverted index."""
from __future__ import annotations

import math
from collections import Counter, defaultdict

from .schema import Chunk
from .textutils import tokenize


class BM25:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.ids = [c.id for c in chunks]
        self.n = len(chunks)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.lengths: list[int] = []
        for i, c in enumerate(chunks):
            toks = tokenize(c.index_text)
            self.lengths.append(len(toks))
            for t, tf in Counter(toks).items():
                self.postings[t].append((i, tf))
        self.avg_len = (sum(self.lengths) / self.n) if self.n else 1.0

    def idf(self, token: str) -> float:
        df = len(self.postings.get(token, ()))
        return math.log(1.0 + (self.n - df + 0.5) / (df + 0.5))

    def search(
        self, query: str, k: int = 10, allowed: set[str] | None = None
    ) -> list[tuple[str, float]]:
        scores: dict[int, float] = defaultdict(float)
        for t in set(tokenize(query)):
            idf = self.idf(t)
            for i, tf in self.postings.get(t, ()):
                denom = tf + self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg_len)
                scores[i] += idf * tf * (self.k1 + 1) / denom
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        out = []
        for i, s in ranked:
            if allowed is not None and self.ids[i] not in allowed:
                continue
            out.append((self.ids[i], s))
            if len(out) >= k:
                break
        return out
