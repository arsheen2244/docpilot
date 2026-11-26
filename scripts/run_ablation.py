"""Retrieval ablation: chunkers x retrievers, with bootstrap 95% CIs.

    python scripts/run_ablation.py --split test --tier all
Writes results/ablation_<split>.json and .md; logs each config via ExperimentLogger.
"""
import _path  # noqa: F401
import argparse
import json
from pathlib import Path

from docpilot.config import Settings
from docpilot.evaluation.data import load_questions
from docpilot.evaluation.expt import ExperimentLogger
from docpilot.evaluation.metrics import paired_bootstrap_diff
from docpilot.evaluation.runner import ablation


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=["dev", "test", "all"])
    ap.add_argument("--tier", default="all", choices=["all", "lexical", "paraphrase"])
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    qs = load_questions(split=a.split)
    if a.tier != "all":
        qs = [q for q in qs if q.get("tier") == a.tier]
    s = Settings()
    s.trace_path = ""
    res = ablation(s, qs)

    lines = [f"### Retrieval ablation — split={a.split}, tier={a.tier}, n={next(iter(res['summary'].values()))['n']} answerable questions",
             "", "| config | hit@1 | hit@5 | MRR | nDCG@5 | recall@5 |", "|---|---|---|---|---|---|"]
    for name, v in res["summary"].items():
        cell = lambda m: f"{v[m]['mean']:.2f} [{v[m]['lo']:.2f}, {v[m]['hi']:.2f}]"
        lines.append(f"| {name} | {cell('hit@1')} | {cell('hit@5')} | {cell('mrr')} | {cell('ndcg@5')} | {cell('recall@5')} |")
    pq = res["per_question"]
    if "heading|hybrid_rerank" in pq and "heading|dense" in pq:
        d, lo, hi, p = paired_bootstrap_diff(
            [r["mrr"] for r in pq["heading|hybrid_rerank"]], [r["mrr"] for r in pq["heading|dense"]])
        lines += ["", f"Paired bootstrap, MRR (hybrid_rerank − dense): {d:+.3f}, 95% CI [{lo:+.3f}, {hi:+.3f}], P(diff≤0)={p:.3f}"]
    lines += ["", "Brackets are 95% bootstrap CIs. With small n the intervals are wide: read them before the means."]

    out = Path(a.out)
    out.mkdir(exist_ok=True)
    tag = f"{a.split}_{a.tier}"
    (out / f"ablation_{tag}.json").write_text(json.dumps(res["summary"], indent=2))
    (out / f"ablation_{tag}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    for name, v in res["summary"].items():
        lg = ExperimentLogger(f"ablation:{name}:{tag}", {"config": name, "split": a.split, "tier": a.tier})
        lg.log({k: v[k]["mean"] for k in v if isinstance(v[k], dict)})
        lg.finish()


if __name__ == "__main__":
    main()
