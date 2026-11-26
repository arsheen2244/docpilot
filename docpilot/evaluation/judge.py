"""LLM-as-judge for answer faithfulness, plus agreement with human labels.

Workflow: label ~50 (question, answer, passages) triples yourself as SUPPORTED/UNSUPPORTED,
run the judge on the same triples, and report Cohen's kappa. Only trust judge scores on
the rest of the data if kappa is high enough for your purposes.
"""
from __future__ import annotations

from .metrics import cohens_kappa

JUDGE_SYSTEM = (
    "You are a strict fact-checker. Given numbered passages and an answer, reply with exactly "
    "one word: SUPPORTED if every claim in the answer is stated in the passages, otherwise "
    "UNSUPPORTED."
)


def judge_prompt(passages: list[str], answer: str) -> str:
    blocks = "\n".join(f"[{i}] {p}" for i, p in enumerate(passages, start=1))
    return f"<passages>\n{blocks}\n</passages>\nAnswer: {answer}"


class LLMJudge:
    def __init__(self, llm):
        self.llm = llm

    def label(self, passages: list[str], answer: str) -> str:
        text = self.llm.complete(JUDGE_SYSTEM, judge_prompt(passages, answer), kind="judge", max_tokens=5).text
        return "UNSUPPORTED" if "UNSUPPORTED" in text.upper() else "SUPPORTED"


def agreement(human: list[str], judge: list[str]) -> dict:
    n = len(human)
    return {
        "n": n,
        "raw_agreement": sum(h == j for h, j in zip(human, judge)) / n,
        "kappa": cohens_kappa(human, judge),
    }
