"""Build DPO preference pairs that teach citation fidelity.

chosen   = an answer that passes the code-level guard (cited and lexically supported)
rejected = the same answer with one claim swapped for a sentence from an UNRELATED chunk
           but keeping the original citation marker (a plausible-looking mis-attribution)

With the offline ExtractiveLLM the 'chosen' answers are extractive snippets, which is poor
training data for a real model. For a real run generate `chosen` with a strong LLM through
the gateway (set DOCPILOT_LLM_BASE_URL etc.) and keep only guard-verified answers.

    python scripts/make_dpo_pairs.py --split dev --out data/dpo_pairs.jsonl
"""
import _path  # noqa: F401
import argparse
import json
import random
from pathlib import Path

from docpilot.config import Settings
from docpilot.evaluation.data import load_questions
from docpilot.prompts import SYSTEM_ANSWER, build_user
from docpilot.service import DocPilot
from docpilot.textutils import split_sentences


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--out", default="data/dpo_pairs.jsonl")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    s = Settings()
    s.trace_path = ""
    dp = DocPilot(s)
    pairs = []
    for q in load_questions(split=a.split):
        if not q["answerable"]:
            continue
        r = dp.ask(q["question"])
        if r.abstained or not r.citations:
            continue
        ctx = [dp.retriever.by_id[c["chunk_id"]] for c in r.citations]
        used_docs = {c.doc_id for c in ctx}
        distractors = [c for c in dp.chunks if c.doc_id not in used_docs and c.topic != ctx[0].topic]
        if not distractors:
            continue
        sents = split_sentences(r.answer)
        i = rng.randrange(len(sents))
        wrong = rng.choice(distractors)
        wrong_sent = split_sentences(wrong.text)[0].rstrip(".!? ")
        marker = sents[i][sents[i].rfind("["):] if "[" in sents[i] else "[1]."
        bad = list(sents)
        bad[i] = f"{wrong_sent} {marker}"
        prompt = build_user(q["question"], [c.text for c in ctx])
        pairs.append({"system": SYSTEM_ANSWER, "prompt": prompt, "chosen": r.answer,
                      "rejected": " ".join(bad), "question_id": q["id"]})
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(json.dumps(p) for p in pairs) + "\n")
    print(f"wrote {len(pairs)} pairs to {a.out}")


if __name__ == "__main__":
    main()
