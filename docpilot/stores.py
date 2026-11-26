"""Vector stores behind one interface.

InMemoryStore is exercised by the test-suite. QdrantStore and PgVectorStore are real
implementations but need running services and optional packages; they were NOT executed
in the environment this repo was generated in (see README "Verification status").
"""
from __future__ import annotations

import uuid
from typing import Protocol

import numpy as np

from .schema import Chunk


class VectorStore(Protocol):
    def add(self, chunks: list[Chunk], vectors: np.ndarray) -> None: ...

    def search(
        self, vector: np.ndarray, k: int, flt: dict | None = None
    ) -> list[tuple[str, float]]: ...


class InMemoryStore:
    def __init__(self) -> None:
        self.ids: list[str] = []
        self.meta: list[Chunk] = []
        self.matrix = np.zeros((0, 0), dtype=np.float32)

    def add(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        self.ids = [c.id for c in chunks]
        self.meta = list(chunks)
        self.matrix = np.asarray(vectors, dtype=np.float32)

    def search(self, vector, k, flt=None):
        if not len(self.ids):
            return []
        sims = self.matrix @ np.asarray(vector, dtype=np.float32)
        order = np.argsort(-sims)
        out = []
        for i in order:
            c = self.meta[i]
            if flt and any(getattr(c, key, None) != val for key, val in flt.items()):
                continue
            out.append((self.ids[i], float(sims[i])))
            if len(out) >= k:
                break
        return out


class QdrantStore:
    """Qdrant backend. url=':memory:' runs an embedded instance for local use."""

    def __init__(self, url: str = "http://localhost:6333", collection: str = "docpilot"):
        from qdrant_client import QdrantClient, models

        self.models = models
        self.client = QdrantClient(location=url) if url == ":memory:" else QdrantClient(url=url)
        self.collection = collection

    def add(self, chunks, vectors):
        m = self.models
        try:
            self.client.delete_collection(self.collection)
        except Exception:
            pass
        self.client.create_collection(
            self.collection,
            vectors_config=m.VectorParams(size=int(vectors.shape[1]), distance=m.Distance.COSINE),
        )
        points = [
            m.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, c.id)),
                vector=vectors[i].tolist(),
                payload={"chunk_id": c.id, "doc_id": c.doc_id, "topic": c.topic},
            )
            for i, c in enumerate(chunks)
        ]
        self.client.upsert(self.collection, points=points)

    def search(self, vector, k, flt=None):
        m = self.models
        qf = None
        if flt:
            qf = m.Filter(
                must=[
                    m.FieldCondition(key=key, match=m.MatchValue(value=val))
                    for key, val in flt.items()
                ]
            )
        res = self.client.query_points(
            self.collection, query=vector.tolist(), limit=k, query_filter=qf
        ).points
        return [(p.payload["chunk_id"], float(p.score)) for p in res]


class PgVectorStore:
    """PostgreSQL + pgvector backend (psycopg 3)."""

    def __init__(self, dsn: str, table: str = "docpilot_chunks"):
        import psycopg

        self.conn = psycopg.connect(dsn, autocommit=True)
        self.table = table

    @staticmethod
    def _lit(v) -> str:
        return "[" + ",".join(f"{x:.6f}" for x in v) + "]"

    def add(self, chunks, vectors):
        dim = int(vectors.shape[1])
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(f"DROP TABLE IF EXISTS {self.table}")
            cur.execute(
                f"CREATE TABLE {self.table} (id text PRIMARY KEY, doc_id text, topic text, "
                f"embedding vector({dim}))"
            )
            for c, v in zip(chunks, vectors):
                cur.execute(
                    f"INSERT INTO {self.table} (id, doc_id, topic, embedding) "
                    f"VALUES (%s, %s, %s, %s::vector)",
                    (c.id, c.doc_id, c.topic, self._lit(v)),
                )

    def search(self, vector, k, flt=None):
        where, params = "", [self._lit(vector)]
        if flt:
            allowed = {"topic", "doc_id"}
            conds = []
            for key, val in flt.items():
                if key not in allowed:
                    raise ValueError(f"unsupported filter key {key}")
                conds.append(f"{key} = %s")
                params.append(val)
            where = "WHERE " + " AND ".join(conds)
        params += [self._lit(vector), k]
        sql = (
            f"SELECT id, 1 - (embedding <=> %s::vector) AS score FROM {self.table} {where} "
            f"ORDER BY embedding <=> %s::vector LIMIT %s"
        )
        # parameter order: score vector, filter values, order vector, limit
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return [(r[0], float(r[1])) for r in cur.fetchall()]


def make_store(kind: str, url: str = "", dsn: str = "") -> VectorStore:
    if kind == "qdrant":
        return QdrantStore(url or "http://localhost:6333")
    if kind == "pgvector":
        return PgVectorStore(dsn)
    return InMemoryStore()
