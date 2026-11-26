import json

from docpilot.evaluation.metrics import (bootstrap_ci, cohens_kappa, mrr, ndcg_at_k,
                                         paired_bootstrap_diff, question_metrics)
from docpilot.evaluation.judge import agreement
from docpilot.security import ApiKeyAuth, RateLimiter
from docpilot.tracing import Tracer


def test_api_key_auth():
    a = ApiKeyAuth(["k1", "k2"])
    assert a.check("k2") and not a.check("nope") and not a.check(None)
    assert ApiKeyAuth([]).check(None)  # auth disabled when no keys configured


def test_rate_limiter_token_bucket_with_fake_clock():
    now = [0.0]
    rl = RateLimiter(per_minute=60, burst=2, clock=lambda: now[0])
    assert rl.allow("a") and rl.allow("a") and not rl.allow("a")
    assert rl.allow("b")  # separate bucket
    now[0] += 1.0  # 1 token refills at 1/sec
    assert rl.allow("a") and not rl.allow("a")


def test_tracer_writes_spans(tmp_path):
    p = tmp_path / "t.jsonl"
    with Tracer(p).trace("ask", q="x") as tr:
        with tr.span("retrieve") as sp:
            sp.set(n=3)
    rec = json.loads(p.read_text())
    assert rec["spans"][0]["name"] == "retrieve" and rec["spans"][0]["attrs"]["n"] == 3
    assert rec["duration_ms"] >= rec["spans"][0]["dur_ms"] >= 0


def test_ranking_metrics_known_values():
    assert mrr(["x", "g", "y"], {"g"}) == 0.5
    assert abs(ndcg_at_k(["x", "g"], {"g"}, 5) - 1 / 1.5849625007) < 1e-6
    m = question_metrics(["a", "a", "b", "g"], {"g", "z"}, 5)  # chunk ids dedupe to docs
    assert m["hit@5"] == 1.0 and m["recall@5"] == 0.5 and m["hit@1"] == 0.0


def test_bootstrap_and_paired_diff_are_sane():
    mean, lo, hi = bootstrap_ci([1, 1, 0, 1, 0, 1, 1, 1])
    assert lo <= mean <= hi
    d, lo, hi, p = paired_bootstrap_diff([1] * 20, [0] * 20)
    assert d == 1.0 and p == 0.0


def test_kappa():
    assert cohens_kappa(list("AABB"), list("AABB")) == 1.0
    assert abs(cohens_kappa(list("AABB"), list("ABAB"))) < 1e-9
    r = agreement(["SUPPORTED", "UNSUPPORTED", "SUPPORTED"], ["SUPPORTED", "UNSUPPORTED", "UNSUPPORTED"])
    assert r["n"] == 3 and abs(r["raw_agreement"] - 2 / 3) < 1e-9
