"""Print what happened per query in a saved eval run.

Usage (from Backend):
    python eval/inspect_run.py eval/results/<file>.json            # one block per query
    python eval/inspect_run.py eval/results/<file>.json --id p01   # one query, with every lead
    python eval/inspect_run.py eval/results/<file>.json --pages    # also list every fetched URL
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metrics  # noqa: E402


def short(text: str, limit: int = 160) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--id", help="only this query id")
    parser.add_argument("--pages", action="store_true", help="list the URLs the pipeline fetched")
    args = parser.parse_args()

    data = json.loads(Path(args.path).read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    print(f"Run: {meta.get('label') or '-'}  git {meta.get('git')}  args {meta.get('args', {}).get('profiles', 'as-set')}\n")

    for q in data["queries"]:
        if args.id and q["id"] != args.id:
            continue
        p = q["pages"]
        print(f"{q['id']} [{q.get('variant', '-')}] {q['query']}")
        m = q.get("metrics", {})
        extra = ""
        if "verified_useful_leads" in m:
            extra = (f" | useful {m.get('useful_leads')}, verified useful {m.get('verified_useful_leads')}, "
                     f"order quality {m.get('ndcg') if m.get('ndcg') is not None else '-'}")
        print(f"  {q['latency_s']}s | pages fetched {p['fetched']}: ok {p['ok']}, blocked {p['blocked']}, "
              f"failed {p['failed']}, needed JS {p['needed_js']} | leads {len(q['leads'])}{extra}")
        if q.get("error"):
            print(f"  ERROR: {q['error']}")
        if q.get("summary_text"):
            print(f"  model said: {short(q['summary_text'], 240)}")
        if args.pages or args.id:
            for url in p.get("urls", []):
                print(f"    fetched: {url}")
        for lead in q["leads"]:
            g = lead.get("grounding", {})
            j = lead.get("judge") or {}
            if "request_match" in j:
                verdict = (f"match {j['request_match']}, fit {j.get('user_fit', '-') if j.get('user_fit') is not None else '-'}"
                           f"{', FABRICATED' if j.get('fabricated') else ''}{', useful' if j.get('useful') else ''}")
            else:
                verdict = f"score {j.get('score', '-')} (old judge)"
            print(f"    - {lead.get('name')} | {short(lead.get('title', ''), 50)} | {lead.get('company', '')}")
            print(f"      source: {metrics.source_type(lead.get('source_url'))} | name on page: "
                  f"{g.get('name_match')} ({g.get('page_status')}) | fetched by pipeline: "
                  f"{g.get('source_fetched_by_pipeline')} | judge: {verdict}")
            if args.id:
                print(f"      source: {lead.get('source_url')}")
                if j.get("reason"):
                    print(f"      judge reason: {short(j['reason'], 200)}")
        print()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
