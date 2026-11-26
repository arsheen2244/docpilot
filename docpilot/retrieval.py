"""Dense + BM25 retrieval, Reciprocal Rank Fusion, reranking, multi-query merging."""
from __future__ import annotations

from .bm25 import BM25
from .schema import Chunk, Hit

MODES = ("dense", "lexical", "hybrid", "hybrid_rerank")


def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion over ranked id lists."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])


class Retriever:
    def __init__(self, chunks: list[Chunk], embedder, store, reranker=None):
        self.by_id = {c.id: c for c in chunks}
        self.embedder = embedder
        self.store = store
        self.reranker = reranker
        self.bm25 = BM25(chunks)
        texts = [c.index_text for c in chunks]
        if hasattr(embedder, "fit"):
            embedder.fit(texts)
        store.add(chunks, embedder.embed(texts))

    def idf(self, token: str) -> float:
        return self.bm25.idf(token)

    # -- single query -------------------------------------------------------------
    def _allowed(self, flt: dict | None) -> set[str] | None:
        if not flt:
            return None
        return {
            cid
            for cid, c in self.by_id.items()
            if all(getattr(c, k, None) == v for k, v in flt.items())
        }

    def search(
        self, query: str, mode: str = "hybrid_rerank", k: int = 5, flt: dict | None = None,
        pool: int = 20,
    ) -> list[Hit]:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        dense = [cid for cid, _ in self.store.search(self.embedder.embed([query])[0], pool, flt)]
        lexical = [cid for cid, _ in self.bm25.search(query, pool, self._allowed(flt))]
        if mode == "dense":
            return [Hit(self.by_id[c], 1.0 / (r + 1), mode) for r, c in enumerate(dense[:k])]
        if mode == "lexical":
            return [Hit(self.by_id[c], 1.0 / (r + 1), mode) for r, c in enumerate(lexical[:k])]
        fused = rrf([dense, lexical])
        if mode == "hybrid" or self.reranker is None:
            return [Hit(self.by_id[c], s, "hybrid") for c, s in fused[:k]]
        candidates = [self.by_id[c] for c, _ in fused[:pool]]
        reranked = self.reranker.rerank(query, candidates)
        return [Hit(c, s, mode) for c, s in reranked[:k]]

    # -- several queries (sub-questions, expansions, HyDE) ------------------------
    def search_multi(
        self, queries: list[str], mode: str = "hybrid_rerank", k: int = 5,
        flt: dict | None = None, pool: int = 20,
    ) -> list[Hit]:
        """Round-robin merge of per-query rankings so each sub-question keeps a seat."""
        if len(queries) == 1:
            return self.search(queries[0], mode, k, flt, pool)
        lists = [self.search(q, mode, k, flt, pool) for q in queries]
        merged: list[Hit] = []
        seen: set[str] = set()
        for rank in range(k):
            for lst in lists:
                if rank < len(lst) and lst[rank].chunk.id not in seen:
                    seen.add(lst[rank].chunk.id)
                    merged.append(lst[rank])
        return merged[:k]
