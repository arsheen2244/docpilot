"""Deterministic guards that run in code, not in the prompt.

1. is_injection: drop retrieved chunks that look like instructions aimed at the model.
2. verify_answer: keep only answer sentences that carry a valid citation AND are lexically
   supported by the cited passage. Anything else is removed; an empty result means abstain.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .schema import Chunk
from .textutils import split_sentences, tokenize

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
    r"disregard (all |any |the )?(previous|prior|above|earlier)",
    r"forget (everything|all|your) (above|previous|instructions)",
    r"you are now\b",
    r"(reveal|print|show|repeat) (your |the )?(system|hidden) (prompt|instructions)",
    r"\bnew instructions?:",
    r"\b(act|respond|reply) as (if )?(you|an?) ",
    r"do not (cite|mention) (the )?(source|context|passages?)",
]
_INJ = re.compile("|".join(INJECTION_PATTERNS), re.I)
_CITE = re.compile(r"\[(\d+)\]")


def is_injection(text: str) -> bool:
    return bool(_INJ.search(text))


@dataclass
class Verified:
    text: str
    kept: list[str] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)
    cited: list[int] = field(default_factory=list)  # 1-based passage numbers actually used


def verify_answer(answer: str, passages: list[Chunk], min_support: float = 0.6) -> Verified:
    ptoks = [set(tokenize(p.index_text)) for p in passages]
    kept: list[str] = []
    dropped: list[dict] = []
    cited: list[int] = []
    for sent in split_sentences(answer):
        nums = [int(n) for n in _CITE.findall(sent)]
        body = _CITE.sub("", sent)
        toks = set(tokenize(body))
        if not toks:
            continue
        valid = [n for n in nums if 1 <= n <= len(passages)]
        if not valid:
            dropped.append({"sentence": sent, "reason": "no_valid_citation"})
            continue
        support = max(len(toks & ptoks[n - 1]) / len(toks) for n in valid)
        if support < min_support:
            dropped.append({"sentence": sent, "reason": "unsupported", "support": round(support, 2)})
            continue
        kept.append(sent)
        cited.extend(n for n in valid if n not in cited)
    return Verified(text=" ".join(kept), kept=kept, dropped=dropped, cited=cited)
