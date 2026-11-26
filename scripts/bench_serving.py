"""Benchmark an OpenAI-compatible streaming endpoint (vLLM, llama.cpp server, Ollama, ...).

Measures time-to-first-token (TTFT), end-to-end latency, and decode tokens/sec under a
given concurrency. Use it to compare FP16 vs AWQ vs GGUF servers (see docs/serving.md):
point --base-url at each server in turn and keep everything else identical.

    python scripts/bench_serving.py --base-url http://localhost:8000/v1 --model Qwen/Qwen2.5-1.5B-Instruct \
        --concurrency 8 --requests 64 --max-tokens 128
"""
import _path  # noqa: F401
import argparse
import http.client
import json
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from docpilot.evaluation.metrics import percentile

PROMPT = ("Explain, in a few sentences, how a database index speeds up queries "
          "and what the trade-offs are. ")


def one_request(base_url: str, model: str, prompt: str, max_tokens: int, api_key: str = "") -> dict:
    u = urllib.parse.urlparse(base_url)
    conn_cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(u.hostname, u.port or (443 if u.scheme == "https" else 80), timeout=120)
    body = json.dumps({"model": model, "stream": True, "max_tokens": max_tokens, "temperature": 0,
                       "messages": [{"role": "user", "content": prompt}]})
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    t0 = time.perf_counter()
    conn.request("POST", u.path.rstrip("/") + "/chat/completions", body, headers)
    resp = conn.getresponse()
    if resp.status != 200:
        raise RuntimeError(f"HTTP {resp.status}: {resp.read()[:200]!r}")
    ttft, n_tokens = None, 0
    for raw in resp:
        line = raw.decode().strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
        except (KeyError, IndexError, json.JSONDecodeError):
            continue
        if delta:
            if ttft is None:
                ttft = time.perf_counter() - t0
            n_tokens += 1  # one SSE content event ~ one token for vLLM/llama.cpp
    total = time.perf_counter() - t0
    conn.close()
    decode_time = max(total - (ttft or 0), 1e-9)
    return {"ttft": ttft if ttft is not None else total, "total": total, "tokens": n_tokens,
            "decode_tps": (n_tokens - 1) / decode_time if n_tokens > 1 else 0.0}


def run(base_url, model, concurrency, requests, max_tokens, api_key="", prompt=PROMPT) -> dict:
    results, errors = [], []
    lock = threading.Lock()

    def work(_):
        try:
            r = one_request(base_url, model, prompt, max_tokens, api_key)
            with lock:
                results.append(r)
        except Exception as e:
            with lock:
                errors.append(repr(e))

    t0 = time.perf_counter()
    with ThreadPoolExecutor(concurrency) as ex:
        list(ex.map(work, range(requests)))
    wall = time.perf_counter() - t0
    tt = [r["ttft"] for r in results]
    return {
        "concurrency": concurrency, "requests_ok": len(results), "errors": len(errors),
        "ttft_ms_p50": percentile(tt, 50) * 1000, "ttft_ms_p95": percentile(tt, 95) * 1000,
        "latency_s_p50": percentile([r["total"] for r in results], 50),
        "decode_tps_per_request_p50": percentile([r["decode_tps"] for r in results], 50),
        "aggregate_tokens_per_s": sum(r["tokens"] for r in results) / wall if wall else 0.0,
        "wall_s": wall,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default="")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--requests", type=int, default=32)
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--label", default="run")
    a = ap.parse_args()
    out = run(a.base_url, a.model, a.concurrency, a.requests, a.max_tokens, a.api_key)
    out["label"] = a.label
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
