from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(f"DOCPILOT_{name}", default)


@dataclass
class Settings:
    corpus_dir: str = field(default_factory=lambda: _env("CORPUS", str(ROOT / "data" / "corpus")))
    chunker: str = field(default_factory=lambda: _env("CHUNKER", "heading"))
    embedder: str = field(default_factory=lambda: _env("EMBEDDER", "hash"))  # hash | st
    st_model: str = field(default_factory=lambda: _env("ST_MODEL", "BAAI/bge-small-en-v1.5"))
    store: str = field(default_factory=lambda: _env("STORE", "memory"))  # memory|qdrant|pgvector
    qdrant_url: str = field(default_factory=lambda: _env("QDRANT_URL", "http://localhost:6333"))
    pg_dsn: str = field(default_factory=lambda: _env("PG_DSN", ""))
    llm_base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL", ""))
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY", ""))
    small_model: str = field(default_factory=lambda: _env("SMALL_MODEL", ""))
    large_model: str = field(default_factory=lambda: _env("LARGE_MODEL", ""))
    large_base_url: str = field(default_factory=lambda: _env("LARGE_BASE_URL", ""))
    large_api_key: str = field(default_factory=lambda: _env("LARGE_API_KEY", ""))
    api_keys: list[str] = field(
        default_factory=lambda: [k for k in _env("API_KEYS").split(",") if k.strip()]
    )
    rate_per_min: int = field(default_factory=lambda: int(_env("RATE_PER_MIN", "30")))
    cache: bool = field(default_factory=lambda: _env("CACHE", "1") != "0")  # semantic LLM cache
    trace_path: str = field(default_factory=lambda: _env("TRACE_PATH", "results/traces.jsonl"))
