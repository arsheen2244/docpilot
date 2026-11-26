from docpilot.bm25 import BM25
from docpilot.retrieval import rrf
from docpilot.schema import Chunk
from docpilot.textutils import split_sentences, stem, tokenize
from docpilot.query import expand_query, infer_topic, split_subquestions
from docpilot.evaluation.data import load_questions
from docpilot.evaluation.runner import retrieval_per_question


def test_stem_is_consistent_across_inflections():
    assert stem("services") == stem("service")
    assert stem("probes") == stem("probe")
    assert stem("policies") == stem("policy")
    assert stem("indexes") == stem("index")
    assert stem("updated") == stem("update")
    assert stem("process") == "process"


def test_tokenize_splits_camel_case_and_drops_stopwords():
    toks = tokenize("What does maxSurge control in the NodePort?")
    assert "max" in toks and "surg" in toks and "port" in toks
    assert "what" not in toks and "the" not in toks


def test_split_sentences():
    assert split_sentences("A is B. C is D? Yes!") == ["A is B.", "C is D?", "Yes!"]


def test_rrf_rewards_agreement():
    fused = dict(rrf([["a", "b", "c"], ["b", "a", "d"]]))
    assert fused["a"] > fused["c"] and fused["b"] > fused["d"]


def test_bm25_ranks_matching_chunk_first_and_respects_filter():
    chunks = [Chunk("1", "d1", "redis eviction policy lru", topic="redis"),
              Chunk("2", "d2", "postgres vacuum dead tuples", topic="pg")]
    bm = BM25(chunks)
    assert bm.search("vacuum tuples", 2)[0][0] == "2"
    assert bm.search("vacuum tuples", 2, allowed={"1"}) == []


def test_query_helpers():
    assert "kubernetes" in expand_query("how does k8s work")
    assert infer_topic("how does redis evict keys") == "redis"
    assert infer_topic("redis versus postgres") is None  # ambiguous -> no filter
    assert len(split_subquestions("How do I roll back a Deployment and check rollout progress?")) == 2
    assert len(split_subquestions("difference between a liveness and a readiness probe")) == 1


def test_hybrid_rerank_is_strong_on_lexical_questions(dp):
    qs = [q for q in load_questions(split="all") if q.get("tier") == "lexical"]
    rows = retrieval_per_question(dp.retriever, qs, "hybrid_rerank")
    assert sum(r["hit@5"] for r in rows) / len(rows) >= 0.95


def test_metadata_filter_is_applied(dp):
    hits = dp.retriever.search("what is the default", mode="hybrid", k=5, flt={"topic": "redis"})
    assert hits and all(h.chunk.topic == "redis" for h in hits)
