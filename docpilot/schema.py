from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Chunk:
    id: str
    doc_id: str
    text: str
    title: str = ""
    section: str = ""
    topic: str = ""

    @property
    def index_text(self) -> str:
        """Text used for indexing: title and section give each chunk context."""
        parts = [p for p in (self.title, self.section, self.text) if p]
        return ". ".join(parts)


@dataclass
class Hit:
    chunk: Chunk
    score: float
    source: str = ""


@dataclass
class Document:
    id: str
    title: str
    topic: str
    text: str
    sections: list[tuple[str, str]] = field(default_factory=list)  # (heading, body)
