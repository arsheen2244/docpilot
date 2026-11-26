"""Retrieval metrics at document level, bootstrap CIs, paired comparison, Cohen's kappa."""
from __future__ import annotations

import math

import numpy as np


def dedupe_docs(doc_ids: list[str]) -> list[str]:
    seen, out = set(), []
    for d in doc_ids:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def hit_at_k(ranked_docs: list[str], gold: set[str], k: int) -> float:
    return float(any(d in gold for d in ranked_docs[:k]))


def recall_at_k(ranked_docs: list[str], gold: set[str], k: int) -> float:
    return len(gold & set(ranked_docs[:k])) / len(gold) if gold else 0.0


def mrr(ranked_docs: list[str], gold: set[str]) -> float:
    for i, d in enumerate(ranked_docs, start=1):
        if d in gold:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked_docs: list[str], gold: set[str], k: int) -> float:
    dcg = sum(1.0 / math.log2(i + 2) for i, d in enumerate(ranked_docs[:k]) if d in gold)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(gold), k)))
    return dcg / ideal if ideal else 0.0


def question_metrics(chunk_doc_ids: list[str], gold: set[str], k: int = 5) -> dict[str, float]:
    ranked = dedupe_docs(chunk_doc_ids)
    return {
        "hit@1": hit_at_k(ranked, gold, 1),
        f"hit@{k}": hit_at_k(ranked, gold, k),
        "mrr": mrr(ranked, gold),
        f"ndcg@{k}": ndcg_at_k(ranked, gold, k),
        f"recall@{k}": recall_at_k(ranked, gold, k),
    }


def bootstrap_ci(values, n_boot: int = 2000, alpha: float = 0.05, seed: int = 0):
    v = np.asarray(values, dtype=float)
    if len(v) == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), size=(n_boot, len(v)))].mean(axis=1)
    return float(v.mean()), float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def paired_bootstrap_diff(a, b, n_boot: int = 5000, seed: int = 0):
    """Mean(a-b) with a 95% CI and the share of resamples where a <= b (one-sided p-ish)."""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    rng = np.random.default_rng(seed)
    means = d[rng.integers(0, len(d), size=(n_boot, len(d)))].mean(axis=1)
    return float(d.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975)), float((means <= 0).mean())


def cohens_kappa(a: list, b: list) -> float:
    assert len(a) == len(b) and a, "need two equal-length non-empty label lists"
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def percentile(values, q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), q)) if len(values) else float("nan")
