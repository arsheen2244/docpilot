"""Three chunking strategies so retrieval quality can be ablated, not assumed."""
from __future__ import annotations

from typing import Callable

from .schema import Chunk, Document
from .textutils import split_sentences


def chunk_heading(doc: Document, max_words: int = 160) -> list[Chunk]:
    """One chunk per section; oversized sections are split on sentence boundaries."""
    out: list[Chunk] = []
    for head, body in doc.sections:
        words = body.split()
        if len(words) <= max_words:
            pieces = [body]
        else:
            pieces, cur = [], []
            for s in split_sentences(body):
                if cur and len(" ".join(cur + [s]).split()) > max_words:
                    pieces.append(" ".join(cur))
                    cur = []
                cur.append(s)
            if cur:
                pieces.append(" ".join(cur))
        for p in pieces:
            out.append(
                Chunk(f"{doc.id}#{len(out)}", doc.id, p, doc.title, head, doc.topic)
            )
    return out


def chunk_fixed(doc: Document, size: int = 60, overlap: int = 15) -> list[Chunk]:
    """Fixed word windows that ignore structure (the naive baseline)."""
    words = doc.text.split()
    step = max(1, size - overlap)
    out: list[Chunk] = []
    for start in range(0, max(1, len(words)), step):
        piece = words[start : start + size]
        if not piece:
            break
        out.append(
            Chunk(f"{doc.id}#{len(out)}", doc.id, " ".join(piece), doc.title, "", doc.topic)
        )
        if start + size >= len(words):
            break
    return out


def chunk_sentence_window(doc: Document, window: int = 3, stride: int = 2) -> list[Chunk]:
    """Sliding sentence windows inside each section."""
    out: list[Chunk] = []
    for head, body in doc.sections:
        sents = split_sentences(body)
        for i in range(0, len(sents), stride):
            piece = " ".join(sents[i : i + window])
            out.append(Chunk(f"{doc.id}#{len(out)}", doc.id, piece, doc.title, head, doc.topic))
            if i + window >= len(sents):
                break
    return out


CHUNKERS: dict[str, Callable[[Document], list[Chunk]]] = {
    "heading": chunk_heading,
    "fixed": chunk_fixed,
    "sentence": chunk_sentence_window,
}


def chunk_corpus(docs: list[Document], strategy: str = "heading") -> list[Chunk]:
    fn = CHUNKERS[strategy]
    chunks: list[Chunk] = []
    for d in docs:
        chunks.extend(fn(d))
    return chunks
