"""LLM gateway: tiered routing, semantic cache, retries/fallback and cost accounting.

Prices below are SIMULATED defaults (USD per 1M tokens, input/output) so cost-routing
experiments are reproducible offline. Replace PRICES with your providers' real rates and
real token usage (OpenAICompatLLM reports it) before quoting any dollar figure.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .llm import LLM, LLMResponse

PRICES = {"small": (0.15, 0.60), "large": (2.50, 10.00)}


@dataclass
class Ledger:
    requests: int = 0
    cache_hits: int = 0
    fallbacks: int = 0
    cost_usd: float = 0.0
    saved_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    by_tier: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "requests": self.requests,
            "cache_hits": self.cache_hits,
            "fallbacks": self.fallbacks,
            "cost_usd": round(self.cost_usd, 8),
            "saved_usd": round(self.saved_usd, 8),
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "by_tier": dict(self.by_tier),
        }


class SemanticCache:
    """Cache keyed by (kind, tier, context fingerprint); a hit also needs a similar question."""

    def __init__(self, embedder, threshold: float = 0.97):
        self.embedder = embedder
        self.threshold = threshold
        self.entries: dict[tuple, list[tuple[np.ndarray, LLMResponse]]] = {}

    def get(self, key: tuple, question: str) -> LLMResponse | None:
        bucket = self.entries.get(key)
        if not bucket:
            return None
        qv = self.embedder.embed([question])[0]
        for vec, resp in bucket:
            if float(vec @ qv) >= self.threshold:
                return resp
        return None

    def put(self, key: tuple, question: str, resp: LLMResponse) -> None:
        qv = self.embedder.embed([question])[0]
        self.entries.setdefault(key, []).append((qv, resp))


class Gateway:
    def __init__(
        self,
        tiers: dict[str, LLM],
        embedder=None,
        prices: dict[str, tuple[float, float]] | None = None,
        cache: bool = True,
        cache_threshold: float = 0.97,
        retries: int = 1,
    ):
        self.tiers = tiers
        self.prices = prices or PRICES
        self.cache = SemanticCache(embedder, cache_threshold) if (cache and embedder) else None
        self.retries = retries
        self.ledger = Ledger()

    def pick_tier(self, difficulty: str) -> str:
        return "small" if difficulty == "easy" and "small" in self.tiers else "large"

    def _cost(self, tier: str, pt: int, ct: int) -> float:
        pin, pout = self.prices.get(tier, (0.0, 0.0))
        return (pin * pt + pout * ct) / 1e6

    def complete(
        self, system: str, user: str, kind: str = "answer", difficulty: str = "hard",
        question: str = "", ctx_key: str = "", max_tokens: int = 300,
    ) -> tuple[LLMResponse, dict]:
        tier = self.pick_tier(difficulty)
        self.ledger.requests += 1
        key = (kind, tier, ctx_key)
        if self.cache is not None and question:
            hit = self.cache.get(key, question)
            if hit is not None:
                self.ledger.cache_hits += 1
                saved = self._cost(tier, hit.prompt_tokens, hit.completion_tokens)
                self.ledger.saved_usd += saved
                return hit, {"tier": tier, "cache_hit": True, "cost_usd": 0.0, "model": hit.model}

        order = [tier] + [t for t in self.tiers if t != tier]
        last_err: Exception | None = None
        for i, t in enumerate(order):
            for _ in range(self.retries + 1):
                try:
                    resp = self.tiers[t].complete(system, user, kind=kind, max_tokens=max_tokens)
                    if i > 0:
                        self.ledger.fallbacks += 1
                    cost = self._cost(t, resp.prompt_tokens, resp.completion_tokens)
                    L = self.ledger
                    L.cost_usd += cost
                    L.tokens_in += resp.prompt_tokens
                    L.tokens_out += resp.completion_tokens
                    L.by_tier[t] = L.by_tier.get(t, 0) + 1
                    if self.cache is not None and question and i == 0:
                        self.cache.put(key, question, resp)
                    return resp, {"tier": t, "cache_hit": False, "cost_usd": cost, "model": resp.model}
                except Exception as e:  # network / server errors: retry, then fall back a tier
                    last_err = e
                    time.sleep(0)
        raise RuntimeError(f"all LLM tiers failed: {last_err}")
