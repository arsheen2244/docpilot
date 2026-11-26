"""Retrieval ablation and end-to-end agent evaluation."""
from __future__ import annotations

from ..agent import AgentConfig
from ..query import expand_query, infer_topic
from ..service import DocPilot, build_retriever
from ..config import Settings
from .metrics import bootstrap_ci, percentile, question_metrics

K = 5


def retrieval_per_question(retriever, questions, mode, rewrite=False, k=K, pool=20):
    """Per-question metric dicts for one retrieval configuration (answerable questions only)."""
    rows = []
    for q in questions:
        if not q["answerable"]:
            continue
        text, flt = q["question"], None
        if rewrite:
            text = expand_query(text)
            topic = infer_topic(q["question"])
            flt = {"topic": topic} if topic else None
        hits = retriever.search(text, mode=mode, k=k, flt=flt, pool=pool)
        rows.append(question_metrics([h.chunk.doc_id for h in hits], set(q["gold"]), k))
    return rows


def summarize(rows: list[dict]) -> dict:
    out = {}
    for key in rows[0]:
        mean, lo, hi = bootstrap_ci([r[key] for r in rows])
        out[key] = {"mean": mean, "lo": lo, "hi": hi}
    out["n"] = len(rows)
    return out


def ablation(settings: Settings, questions, chunkers=("fixed", "sentence", "heading")) -> dict:
    results: dict[str, dict] = {}
    per_q: dict[str, list[dict]] = {}
    for chunker in chunkers:
        retriever, chunks = build_retriever(settings, chunker=chunker)
        configs = [("dense", False), ("lexical", False), ("hybrid", False),
                   ("hybrid_rerank", False), ("hybrid_rerank", True)]
        for mode, rewrite in configs:
            if chunker != "heading" and (mode in ("dense", "lexical") or rewrite):
                continue  # full grid only for the default chunker; chunkers compared on hybrid
            name = f"{chunker}|{mode}{'+rewrite' if rewrite else ''}"
            rows = retrieval_per_question(retriever, questions, mode, rewrite)
            per_q[name] = rows
            results[name] = {"chunks": len(chunks), **summarize(rows)}
    return {"summary": results, "per_question": per_q}


def agent_eval(settings: Settings, questions, agent_config: AgentConfig | None = None,
               chunker: str | None = None, cache: bool = True, tiers: dict | None = None) -> dict:
    dp = DocPilot(settings, agent_config, chunker=chunker, cache=cache, tiers=tiers)
    ans_rows, un_rows, lat = [], [], []
    for q in questions:
        r = dp.ask(q["question"])
        lat.append(r.latency_ms)
        if q["answerable"]:
            cited = {c["doc_id"] for c in r.citations}
            gold = set(q["gold"])
            ans_rows.append({
                "answered": not r.abstained,
                "cites_gold": bool(cited & gold),
                "all_cites_gold": bool(cited) and cited <= gold,
                "steps": r.steps, "cost": r.cost_usd, "tier": r.tier,
            })
        else:
            un_rows.append({"abstained": r.abstained, "steps": r.steps, "cost": r.cost_usd})
    answered = [r for r in ans_rows if r["answered"]]
    n_ans, n_un = max(len(ans_rows), 1), max(len(un_rows), 1)
    return {
        "n_answerable": len(ans_rows), "n_unanswerable": len(un_rows),
        "answer_rate": sum(r["answered"] for r in ans_rows) / n_ans,
        "false_abstain_rate": 1 - sum(r["answered"] for r in ans_rows) / n_ans,
        "cites_gold_given_answered": (sum(r["cites_gold"] for r in answered) / len(answered)) if answered else 0.0,
        "all_cites_gold_given_answered": (sum(r["all_cites_gold"] for r in answered) / len(answered)) if answered else 0.0,
        "correct_abstention_rate": sum(r["abstained"] for r in un_rows) / n_un,
        "avg_steps": sum(r["steps"] for r in ans_rows + un_rows) / max(len(ans_rows) + len(un_rows), 1),
        "latency_ms_p50": percentile(lat, 50), "latency_ms_p95": percentile(lat, 95),
        "gateway": dp.gateway.ledger.as_dict(),
        "small_tier_share": (sum(r["tier"] == "small" for r in answered) / len(answered)) if answered else 0.0,
    }
