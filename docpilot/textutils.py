"""Tokenisation, light stemming and sentence splitting shared by every component."""
from __future__ import annotations

import re

STOPWORDS = frozenset(
    """
    a an the of to in on for and or is are was were be been being what which who whom whose
    how why when where does do did can could should would will shall may might must it its
    this that these those with as by at from into than then so if not no vs versus about
    between over under use used using i you we they their there has have had me my our your
    mean means meant happen happens difference differences work works get gets make makes
    """.split()
)

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_TOKEN = re.compile(r"[a-z0-9]+")
_SENT = re.compile(r"(?<=[.!?])\s+|\n+")


def stem(w: str) -> str:
    """A deliberately small suffix stripper; consistent matters more than linguistic."""
    if len(w) <= 3:
        return w
    if w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith(("xes", "ches", "shes", "sses")):
        w = w[:-2]
    elif w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    for suf in ("ing", "ed"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            break
    if w.endswith("e") and len(w) > 4:
        w = w[:-1]
    return w


def tokenize(text: str, keep_stop: bool = False) -> list[str]:
    text = _CAMEL.sub(" ", text)
    out: list[str] = []
    for m in _TOKEN.finditer(text.lower()):
        w = m.group(0)
        if not keep_stop and w in STOPWORDS:
            continue
        out.append(stem(w))
    return out


def split_sentences(text: str) -> list[str]:
    return [p.strip() for p in _SENT.split(text) if p and p.strip()]


def approx_tokens(text: str) -> int:
    """Cheap token estimate used for budgets and simulated cost accounting."""
    return int(len(text.split()) * 1.3) + 1
