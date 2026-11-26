"""LLM clients. Everything speaks one tiny interface so tiers can be swapped freely."""
from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from .textutils import approx_tokens, split_sentences, tokenize


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    latency_s: float = 0.0


class LLM(Protocol):
    name: str

    def complete(
        self, system: str, user: str, kind: str = "answer", max_tokens: int = 300
    ) -> LLMResponse: ...


class OpenAICompatLLM:
    """Any OpenAI-compatible /chat/completions endpoint: OpenAI, vLLM, llama.cpp server, Ollama."""

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.name = model
        self.api_key = api_key
        self.timeout = timeout

    def complete(self, system, user, kind="answer", max_tokens=300) -> LLMResponse:
        body = json.dumps(
            {
                "model": self.name,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "max_tokens": max_tokens,
            }
        ).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body, headers=headers
        )
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.load(r)
        text = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            prompt_tokens=usage.get("prompt_tokens", approx_tokens(system + user)),
            completion_tokens=usage.get("completion_tokens", approx_tokens(text)),
            model=self.name,
            latency_s=time.perf_counter() - t0,
        )


_BLOCK = re.compile(r"^\[(\d+)\] (.*?)(?=^\[\d+\] |\n</context>)", re.S | re.M)


class ExtractiveLLM:
    """Offline stand-in 'model': picks the best-matching context sentences and cites them.

    It cannot reason, paraphrase or be prompt-injected. It exists so the pipeline,
    guards, gateway and evals run end-to-end with no network or GPU. Quality numbers
    produced with it describe the *retrieval and guard layers*, not a real LLM.
    """

    def __init__(self, name: str = "extractive-small", max_sentences: int = 2):
        self.name = name
        self.max_sentences = max_sentences

    def complete(self, system, user, kind="answer", max_tokens=300) -> LLMResponse:
        t0 = time.perf_counter()
        if kind != "answer":  # HyDE etc.: this model cannot imagine passages
            return LLMResponse("", approx_tokens(system + user), 0, self.name, 0.0)
        qline = user.rsplit("Question:", 1)[-1].strip()
        q = set(tokenize(qline))
        scored = []
        for m in _BLOCK.finditer(user):
            n, body = int(m.group(1)), m.group(2).strip()
            for s in split_sentences(body):
                st = set(tokenize(s))
                if not st or not q:
                    continue
                overlap = len(q & st)
                if overlap:
                    scored.append((overlap / len(q) + 0.01 * overlap / len(st), n, s))
        if not scored:
            text = "INSUFFICIENT"
        else:
            scored.sort(key=lambda x: -x[0])
            best = scored[0][0]
            picked = [x for x in scored if x[0] >= 0.6 * best][: self.max_sentences]
            picked.sort(key=lambda x: x[1])
            text = " ".join(f"{s.rstrip('.!? ')} [{n}]." for _, n, s in picked)
        return LLMResponse(
            text, approx_tokens(system + user), approx_tokens(text), self.name,
            time.perf_counter() - t0,
        )
