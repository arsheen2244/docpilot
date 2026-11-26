"""Embedders.

HashingEmbedder is an offline, deterministic, IDF-weighted bag-of-ngrams stand-in so the
whole system runs and is testable without downloading a model. It is essentially lexical:
for real semantic retrieval switch to SentenceTransformerEmbedder (DOCPILOT_EMBEDDER=st).
"""
from __future__ import annotations

import math
import zlib
from collections import Counter

import numpy as np

from .textutils import tokenize


class HashingEmbedder:
    name = "hashing"

    def __init__(self, dim: int = 1024):
        self.dim = dim
        self.idf: dict[str, float] = {}
        self.max_idf = 1.0

    def fit(self, texts: list[str]) -> "HashingEmbedder":
        df: Counter[str] = Counter()
        for t in texts:
            df.update(set(tokenize(t)))
        n = len(texts)
        self.idf = {tok: math.log((n + 1) / (c + 1)) + 1.0 for tok, c in df.items()}
        self.max_idf = math.log(n + 1) + 1.0
        return self

    def _add(self, v: np.ndarray, feat: str, w: float) -> None:
        h = zlib.crc32(feat.encode())
        v[h % self.dim] += (1.0 if (h >> 16) & 1 else -1.0) * w

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            toks = tokenize(text)
            for t in toks:
                self._add(out[i], t, self.idf.get(t, self.max_idf))
            for a, b in zip(toks, toks[1:]):
                w = 0.5 * max(self.idf.get(a, self.max_idf), self.idf.get(b, self.max_idf))
                self._add(out[i], a + "_" + b, w)
            norm = np.linalg.norm(out[i])
            if norm > 0:
                out[i] /= norm
        return out


class SentenceTransformerEmbedder:
    """Real dense embeddings. Requires `pip install sentence-transformers` (not run in CI here)."""

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5"):
        from sentence_transformers import SentenceTransformer  # lazy import

        self.name = model
        self.model = SentenceTransformer(model)
        self.dim = self.model.get_sentence_embedding_dimension()

    def fit(self, texts: list[str]) -> "SentenceTransformerEmbedder":
        return self

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False),
            dtype=np.float32,
        )


def make_embedder(kind: str, st_model: str = "BAAI/bge-small-en-v1.5"):
    if kind == "st":
        return SentenceTransformerEmbedder(st_model)
    return HashingEmbedder()
