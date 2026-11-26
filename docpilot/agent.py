"""The agent: an explicit state machine (route -> rewrite -> retrieve -> grade -> generate ->
guard), with bounded retries, a step cap, a token budget, small->large model cascade, and
abstention. Each node is a plain method so it ports directly to LangGraph if you want it.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .guards import is_injection, verify_answer
from .prompts import ABSTAIN_TEXT, SYSTEM_ANSWER, build_user
from .query import expand_query, hyde_passage, infer_topic, split_subquestions
from .rerank import coverage
from .schema import Chunk, Hit
from .tracing import Tracer


@dataclass
class AgentConfig:
    mode: str = "hybrid_rerank"
    k: int = 4
    pool: int = 20
    max_attempts: int = 2
    max_steps: int = 14
    token_budget: int = 6000
    coverage_threshold: float = 0.6
    easy_coverage: float = 0.85
    support_threshold: float = 0.6
    topic_filter: bool = True
    cascade: bool = True
    quarantine: bool = True
    use_hyde: bool = True


@dataclass
class AgentResult:
    question: str
    answer: str
    abstained: bool
    reason: str
    citations: list[dict]
    plan: str
    attempts: int
    steps: int
    coverage: float
    tier: str
    escalated: bool
    cost_usd: float
    tokens: int
    cache_hit: bool
    quarantined: list[str]
    dropped: list[dict]
    trace_id: str
    latency_ms: float

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class _State:
    question: str
    topic: str | None = None
    plan: str = "single"
    subs: list[str] = field(default_factory=list)
    flt: dict | None = None
    queries: list[str] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)
    best_hits: list[Hit] = field(default_factory=list)
    best_cov: float = 0.0
    coverage: float = 0.0
    attempt: int = 0
    steps: int = 0
    raw: str = ""
    answer: str = ""
    abstained: bool = False
    reason: str = ""
    cited: list[int] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)
    quarantined: list[str] = field(default_factory=list)
    tier: str = ""
    escalated: bool = False
    cost: float = 0.0
    tokens: int = 0
    cache_hit: bool = False
    ctx: list[Chunk] = field(default_factory=list)
    trace: object = None


class DocPilotAgent:
    def __init__(self, retriever, gateway, tracer: Tracer | None = None,
                 config: AgentConfig | None = None):
        self.retriever = retriever
        self.gateway = gateway
        self.tracer = tracer or Tracer()
        self.cfg = config or AgentConfig()

    # ---- driver -------------------------------------------------------------------
    def run(self, question: str, topic: str | None = None) -> AgentResult:
        st = _State(question=question, topic=topic)
        with self.tracer.trace("ask", question=question) as tr:
            st.trace = tr
            node = "route"
            while node != "done":
                st.steps += 1
                if st.steps > self.cfg.max_steps and node != "abstain":
                    st.reason = "step_budget_exceeded"
                    node = "abstain"
                with tr.span(node) as sp:
                    node = getattr(self, f"_n_{node}")(st, sp)
            tr.attrs.update(
                abstained=st.abstained, reason=st.reason, steps=st.steps, tier=st.tier,
                cost_usd=st.cost,
            )
            result = self._result(st, tr)
        result.latency_ms = round(tr.duration_ms or result.latency_ms, 3)
        return result

    def _result(self, st: _State, tr) -> AgentResult:
        cites = []
        for n in st.cited:
            c = st.ctx[n - 1]
            cites.append({"n": n, "chunk_id": c.id, "doc_id": c.doc_id, "title": c.title,
                          "section": c.section})
        import time as _t  # duration is finalised by the tracer after this block
        return AgentResult(
            question=st.question, answer=st.answer, abstained=st.abstained, reason=st.reason,
            citations=cites, plan=st.plan, attempts=st.attempt + 1, steps=st.steps,
            coverage=round(st.coverage, 3), tier=st.tier, escalated=st.escalated,
            cost_usd=st.cost, tokens=st.tokens, cache_hit=st.cache_hit,
            quarantined=st.quarantined, dropped=st.dropped, trace_id=tr.id,
            latency_ms=(_t.perf_counter() - tr._t0) * 1000,
        )

    # ---- nodes: each returns the name of the next node ------------------------------
    def _n_route(self, st: _State, sp) -> str:
        st.subs = split_subquestions(st.question)
        st.plan = "multi" if len(st.subs) > 1 else "single"
        if st.topic is None and self.cfg.topic_filter:
            st.topic = infer_topic(st.question)
        st.flt = {"topic": st.topic} if st.topic else None
        sp.set(plan=st.plan, topic=st.topic)
        return "rewrite"

    def _n_rewrite(self, st: _State, sp) -> str:
        queries = [expand_query(st.question)]
        if st.plan == "multi":
            queries += [expand_query(s) for s in st.subs]
        if st.attempt > 0:  # broaden: drop the topic filter, add a HyDE passage
            st.flt = None
            if self.cfg.use_hyde:
                passage = hyde_passage(self.gateway, st.question)
                if passage:
                    queries.append(passage)
        st.queries = queries
        sp.set(n_queries=len(queries), attempt=st.attempt, broadened=st.attempt > 0)
        return "retrieve"

    def _n_retrieve(self, st: _State, sp) -> str:
        cfg = self.cfg
        hits = self.retriever.search_multi(st.queries, cfg.mode, cfg.k + 2, st.flt, cfg.pool)
        kept: list[Hit] = []
        for h in hits:
            if cfg.quarantine and is_injection(h.chunk.text):
                st.quarantined.append(h.chunk.id)
            else:
                kept.append(h)
        st.hits = kept[: cfg.k]
        sp.set(n_hits=len(st.hits), quarantined=len(st.quarantined),
               top=[h.chunk.id for h in st.hits])
        return "grade"

    def _n_grade(self, st: _State, sp) -> str:
        ctx = [h.chunk for h in st.hits]
        cov = coverage(expand_query(st.question), ctx, self.retriever.idf)
        st.coverage = cov
        if cov > st.best_cov:
            st.best_cov, st.best_hits = cov, list(st.hits)
        sp.set(coverage=round(cov, 3), threshold=self.cfg.coverage_threshold)
        if cov >= self.cfg.coverage_threshold:
            return "generate"
        if st.attempt + 1 < self.cfg.max_attempts:
            st.attempt += 1
            return "rewrite"
        st.reason = "insufficient_evidence"
        return "abstain"

    def _n_generate(self, st: _State, sp) -> str:
        cfg = self.cfg
        hits = st.best_hits if st.best_hits and st.best_cov >= st.coverage else st.hits
        st.ctx = [h.chunk for h in hits[: cfg.k]]
        if st.tokens > cfg.token_budget:
            st.reason = "token_budget_exceeded"
            return "abstain"
        user = build_user(st.question, [c.text for c in st.ctx])
        easy = st.plan == "single" and st.coverage >= cfg.easy_coverage and not st.escalated
        ctx_key = hashlib.sha1("|".join(c.id for c in st.ctx).encode()).hexdigest()[:12]
        resp, meta = self.gateway.complete(
            SYSTEM_ANSWER, user, kind="answer", difficulty="easy" if easy else "hard",
            question=st.question, ctx_key=ctx_key,
        )
        st.raw, st.tier, st.cache_hit = resp.text, meta["tier"], meta["cache_hit"]
        st.cost += meta["cost_usd"]
        st.tokens += resp.prompt_tokens + resp.completion_tokens
        sp.set(tier=st.tier, cache_hit=st.cache_hit, cost_usd=meta["cost_usd"],
               tokens=resp.prompt_tokens + resp.completion_tokens)
        return "guard"

    def _n_guard(self, st: _State, sp) -> str:
        if "INSUFFICIENT" in st.raw.upper() and len(st.raw) < 40:
            ok = False
            st.reason = "model_declined"
            v = None
        else:
            v = verify_answer(st.raw, st.ctx, self.cfg.support_threshold)
            ok = bool(v.kept)
            st.dropped.extend(v.dropped)
            if not ok:
                st.reason = "unsupported_answer"
        sp.set(ok=ok, dropped=len(v.dropped) if v else 0)
        if ok:
            st.answer, st.cited, st.reason = v.text, v.cited, ""
            return "done"
        if self.cfg.cascade and st.tier == "small" and not st.escalated:
            st.escalated = True  # retry once on the large tier
            return "generate"
        return "abstain"

    def _n_abstain(self, st: _State, sp) -> str:
        st.abstained = True
        st.answer = ABSTAIN_TEXT
        st.cited = []
        if not st.reason:
            st.reason = "abstained"
        sp.set(reason=st.reason)
        return "done"
