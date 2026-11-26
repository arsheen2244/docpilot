"""End-to-end agent evaluation: answer rate, citation accuracy, abstention, cost, latency.

    python scripts/run_agent_eval.py --split test
    python scripts/run_agent_eval.py --split test --no-cascade --no-cache   # ablate features
"""
import _path  # noqa: F401
import argparse
import json
from pathlib import Path

from docpilot.agent import AgentConfig
from docpilot.config import Settings
from docpilot.evaluation.data import load_questions
from docpilot.evaluation.expt import ExperimentLogger
from docpilot.evaluation.runner import agent_eval


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=["dev", "test", "all"])
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument("--no-cascade", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--no-topic-filter", action="store_true")
    ap.add_argument("--no-quarantine", action="store_true")
    ap.add_argument("--chunker", default=None)
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    cfg = AgentConfig(coverage_threshold=a.threshold, cascade=not a.no_cascade,
                      topic_filter=not a.no_topic_filter, quarantine=not a.no_quarantine)
    s = Settings()
    s.trace_path = f"{a.out}/traces_{a.split}.jsonl"
    Path(s.trace_path).unlink(missing_ok=True)
    qs = load_questions(split=a.split)
    res = agent_eval(s, qs, cfg, chunker=a.chunker, cache=not a.no_cache)
    flags = "_".join(f for f, on in [("nocascade", a.no_cascade), ("nocache", a.no_cache),
                                     ("notopic", a.no_topic_filter)] if on) or "default"
    Path(a.out).mkdir(exist_ok=True)
    Path(a.out, f"agent_{a.split}_{flags}.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    lg = ExperimentLogger(f"agent:{a.split}:{flags}", {"threshold": a.threshold, "flags": flags})
    lg.log({k: v for k, v in res.items() if isinstance(v, (int, float))})
    lg.finish()


if __name__ == "__main__":
    main()
