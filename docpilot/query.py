"""Query understanding: abbreviation expansion, topic inference, decomposition, HyDE."""
from __future__ import annotations

import re

from .textutils import tokenize

ABBREV = {
    "k8s": "kubernetes",
    "pg": "postgres",
    "psql": "postgres",
    "aof": "append-only file aof",
    "rdb": "rdb snapshot",
    "lru": "least recently used lru",
    "lfu": "least frequently used lfu",
}

# Product-level keywords only (deliberately NOT derived from the eval questions).
TOPIC_KEYWORDS = {
    "k8s": {"kubernetes", "k8s", "kubectl", "kubelet", "pod", "pods"},
    "pg": {"postgres", "postgresql", "pg", "psql", "vacuum", "mvcc"},
    "redis": {"redis"},
}


def expand_query(q: str) -> str:
    words = re.findall(r"[A-Za-z0-9_-]+|[^\sA-Za-z0-9_-]", q)
    return " ".join(ABBREV.get(w.lower(), w) for w in words)


def infer_topic(q: str) -> str | None:
    """Return a topic only when exactly one topic's keywords appear (else no filter)."""
    words = {w.lower() for w in re.findall(r"[A-Za-z0-9]+", q)}
    hits = [t for t, kws in TOPIC_KEYWORDS.items() if words & kws]
    return hits[0] if len(hits) == 1 else None


_SPLIT = re.compile(r"\s*(?:;|,\s*and\s+|\s+and\s+|\s+while\s+|\s+as well as\s+)\s*", re.I)


def split_subquestions(q: str) -> list[str]:
    """Split a compound question; fall back to [q] unless every part has real content."""
    q = q.strip().rstrip("?")
    parts = [p.strip() for p in _SPLIT.split(q) if p.strip()]
    if len(parts) < 2 or any(len(tokenize(p)) < 2 for p in parts):
        return [q]
    return parts


HYDE_SYSTEM = "Write a short factual passage (2-3 sentences) that would answer the question."


def hyde_passage(gateway, question: str) -> str:
    """HyDE: retrieve with a hypothetical answer. Returns '' when the model cannot."""
    try:
        resp, _ = gateway.complete(
            HYDE_SYSTEM, question, kind="hyde", difficulty="easy", question=question, ctx_key="hyde"
        )
    except Exception:
        return ""
    return resp.text.strip()
