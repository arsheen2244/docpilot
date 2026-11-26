"""Summarise results/traces*.jsonl: per-node latency, abstain reasons, tiers, cost per request.

    python scripts/trace_report.py results/traces_test.jsonl
"""
import _path  # noqa: F401
import argparse
import json
from collections import Counter, defaultdict

from docpilot.evaluation.metrics import percentile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    a = ap.parse_args()
    traces = [json.loads(l) for l in open(a.path) if l.strip()]
    per_node = defaultdict(list)
    for t in traces:
        for s in t["spans"]:
            per_node[s["name"]].append(s["dur_ms"])
    print(f"{len(traces)} traces; request latency p50={percentile([t['duration_ms'] for t in traces], 50):.2f} ms "
          f"p95={percentile([t['duration_ms'] for t in traces], 95):.2f} ms")
    print(f"{'node':10s} {'calls':>6s} {'p50 ms':>9s} {'p95 ms':>9s}")
    for n, v in sorted(per_node.items(), key=lambda x: -sum(x[1])):
        print(f"{n:10s} {len(v):6d} {percentile(v, 50):9.3f} {percentile(v, 95):9.3f}")
    print("abstain reasons:", dict(Counter(t["attrs"].get("reason") or "answered" for t in traces)))
    print("tiers:", dict(Counter(t["attrs"].get("tier") or "-" for t in traces)))
    print(f"mean cost/request (simulated prices): ${sum(t['attrs'].get('cost_usd', 0) for t in traces) / max(len(traces), 1):.8f}")


if __name__ == "__main__":
    main()
