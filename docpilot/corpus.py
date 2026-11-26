"""Load markdown documents: data/corpus/<topic>/<name>.md -> Document."""
from __future__ import annotations

from pathlib import Path

from .schema import Document


def parse_markdown(doc_id: str, topic: str, raw: str) -> Document:
    title = doc_id
    sections: list[tuple[str, str]] = []
    cur_head, cur_lines = "", []
    for line in raw.splitlines():
        if line.startswith("# ") and title == doc_id:
            title = line[2:].strip()
        elif line.startswith("## "):
            if cur_lines:
                sections.append((cur_head, " ".join(cur_lines).strip()))
            cur_head, cur_lines = line[3:].strip(), []
        elif line.strip():
            cur_lines.append(line.strip())
    if cur_lines:
        sections.append((cur_head, " ".join(cur_lines).strip()))
    text = " ".join(body for _, body in sections)
    return Document(id=doc_id, title=title, topic=topic, text=text, sections=sections)


def load_corpus(root: str | Path) -> list[Document]:
    root = Path(root)
    docs: list[Document] = []
    for path in sorted(root.rglob("*.md")):
        topic = path.parent.name if path.parent != root else "general"
        doc_id = f"{topic}/{path.stem}"
        docs.append(parse_markdown(doc_id, topic, path.read_text(encoding="utf-8")))
    if not docs:
        raise FileNotFoundError(f"no .md documents under {root}")
    return docs
