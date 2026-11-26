from __future__ import annotations

import json
from pathlib import Path

from ..config import ROOT

DEFAULT_QUESTIONS = ROOT / "data" / "eval" / "questions.jsonl"


def load_questions(path: str | Path | None = None, split: str = "all") -> list[dict]:
    rows = [json.loads(l) for l in Path(path or DEFAULT_QUESTIONS).read_text().splitlines() if l.strip()]
    return rows if split == "all" else [r for r in rows if r["split"] == split]
