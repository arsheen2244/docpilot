from __future__ import annotations

import argparse
import json

from .service import DocPilot


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="docpilot")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask", help="ask one question")
    a.add_argument("question")
    a.add_argument("--topic")
    a.add_argument("--json", action="store_true")
    sub.add_parser("stats", help="index statistics")
    args = p.parse_args(argv)

    dp = DocPilot()
    if args.cmd == "stats":
        print(json.dumps(dp.stats(), indent=2))
        return
    r = dp.ask(args.question, args.topic)
    if args.json:
        print(json.dumps(r.to_dict(), indent=2))
        return
    print(r.answer)
    for c in r.citations:
        print(f"  [{c['n']}] {c['doc_id']} > {c['section']}")
    print(f"\n(plan={r.plan} tier={r.tier} coverage={r.coverage} steps={r.steps} {r.latency_ms:.1f} ms)")


if __name__ == "__main__":
    main()
