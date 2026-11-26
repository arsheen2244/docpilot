"""Wires corpus -> chunks -> retriever -> gateway -> agent from Settings."""
from __future__ import annotations

from .agent import AgentConfig, AgentResult, DocPilotAgent
from .chunking import chunk_corpus
from .config import Settings
from .corpus import load_corpus
from .embeddings import make_embedder
from .gateway import Gateway
from .llm import ExtractiveLLM, OpenAICompatLLM
from .rerank import CrossEncoderReranker, LexicalReranker
from .retrieval import Retriever
from .stores import make_store
from .tracing import Tracer


def build_retriever(settings: Settings, corpus_dir: str | None = None, chunker: str | None = None,
                    store=None, embedder=None):
    docs = load_corpus(corpus_dir or settings.corpus_dir)
    chunks = chunk_corpus(docs, chunker or settings.chunker)
    embedder = embedder or make_embedder(settings.embedder, settings.st_model)
    store = store or make_store(settings.store, settings.qdrant_url, settings.pg_dsn)
    retriever = Retriever(chunks, embedder, store, reranker=None)
    if settings.embedder == "st":
        retriever.reranker = CrossEncoderReranker()
    else:
        retriever.reranker = LexicalReranker(retriever.idf)
    return retriever, chunks


def build_tiers(settings: Settings) -> dict:
    if settings.llm_base_url and settings.small_model:
        small = OpenAICompatLLM(settings.llm_base_url, settings.small_model, settings.llm_api_key)
        large = OpenAICompatLLM(
            settings.large_base_url or settings.llm_base_url,
            settings.large_model or settings.small_model,
            settings.large_api_key or settings.llm_api_key,
        )
        return {"small": small, "large": large}
    return {"small": ExtractiveLLM("extractive-small"), "large": ExtractiveLLM("extractive-large", 3)}


class DocPilot:
    def __init__(self, settings: Settings | None = None, agent_config: AgentConfig | None = None,
                 corpus_dir: str | None = None, chunker: str | None = None, tiers: dict | None = None,
                 cache: bool | None = None):
        self.settings = settings or Settings()
        self.retriever, self.chunks = build_retriever(self.settings, corpus_dir, chunker)
        self.gateway = Gateway(tiers or build_tiers(self.settings), embedder=self.retriever.embedder,
                               cache=self.settings.cache if cache is None else cache)
        self.tracer = Tracer(self.settings.trace_path or None)
        self.agent = DocPilotAgent(self.retriever, self.gateway, self.tracer, agent_config)

    def ask(self, question: str, topic: str | None = None) -> AgentResult:
        return self.agent.run(question, topic)

    def stats(self) -> dict:
        return {"chunks": len(self.chunks), **self.gateway.ledger.as_dict()}
