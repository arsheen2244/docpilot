import pytest

from docpilot.agent import AgentConfig
from docpilot.embeddings import HashingEmbedder
from docpilot.gateway import Gateway
from docpilot.llm import ExtractiveLLM, LLMResponse
from docpilot.service import DocPilot


class Stub:
    def __init__(self, name, text="x [1].", fail=False):
        self.name, self.text, self.fail, self.calls = name, text, fail, 0

    def complete(self, system, user, kind="answer", max_tokens=300):
        self.calls += 1
        if self.fail:
            raise ConnectionError("down")
        return LLMResponse(self.text, 1000, 100, self.name)


def make(small, large, **kw):
    emb = HashingEmbedder().fit(["alpha beta gamma", "delta"])
    return Gateway({"small": small, "large": large}, embedder=emb, **kw)


def test_routes_by_difficulty_and_accounts_cost():
    s, l = Stub("s"), Stub("l")
    g = make(s, l)
    _, m1 = g.complete("sys", "u", difficulty="easy", question="alpha")
    _, m2 = g.complete("sys", "u", difficulty="hard", question="beta")
    assert (m1["tier"], m2["tier"]) == ("small", "large")
    assert m2["cost_usd"] > m1["cost_usd"] > 0
    assert g.ledger.requests == 2 and abs(g.ledger.cost_usd - (m1["cost_usd"] + m2["cost_usd"])) < 1e-12


def test_semantic_cache_hit_saves_a_call():
    s, l = Stub("s"), Stub("l")
    g = make(s, l)
    g.complete("sys", "u", difficulty="easy", question="alpha beta", ctx_key="k")
    _, meta = g.complete("sys", "u", difficulty="easy", question="alpha beta", ctx_key="k")
    assert meta["cache_hit"] and s.calls == 1 and g.ledger.cache_hits == 1 and g.ledger.saved_usd > 0


def test_cache_is_keyed_on_context():
    s, l = Stub("s"), Stub("l")
    g = make(s, l)
    g.complete("sys", "u", difficulty="easy", question="alpha beta", ctx_key="k1")
    _, meta = g.complete("sys", "u", difficulty="easy", question="alpha beta", ctx_key="k2")
    assert not meta["cache_hit"] and s.calls == 2


def test_falls_back_to_other_tier_when_primary_down():
    g = make(Stub("s", fail=True), Stub("l"), retries=1)
    resp, meta = g.complete("sys", "u", difficulty="easy", question="q")
    assert meta["tier"] == "large" and g.ledger.fallbacks == 1


def test_raises_when_all_tiers_fail():
    g = make(Stub("s", fail=True), Stub("l", fail=True), retries=0)
    with pytest.raises(RuntimeError):
        g.complete("sys", "u", difficulty="hard", question="q")


def test_cascade_escalates_to_large_when_small_answer_is_unsupported(settings):
    bad = Stub("s", text="Totally unrelated claim about bananas [1].")
    tiers = {"small": bad, "large": ExtractiveLLM("large", 3)}
    dp = DocPilot(settings, AgentConfig(), tiers=tiers, cache=False)
    r = dp.ask("What does a Kubernetes liveness probe do when it fails repeatedly?")
    assert r.escalated and r.tier == "large" and not r.abstained
    off = DocPilot(settings, AgentConfig(cascade=False), tiers=tiers, cache=False)
    assert off.ask("What does a Kubernetes liveness probe do when it fails repeatedly?").abstained


def test_routing_sends_easy_questions_to_small_tier(dp):
    r = dp.ask("What is the default isolation level in PostgreSQL?")
    assert r.tier == "small" and r.cost_usd > 0
