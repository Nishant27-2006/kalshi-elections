"""recall@5 on the market -> knowledge-file eval set, one change at a time.

    python -m forecast.retrieval_eval          # run all stages, append to docs/retrieval.md

recall@5 = for each market, the share of its gold files that appear among the
files of the top-5 retrieved chunks (as_of filter applied), averaged over
markets. Gold labels come from what the market is ABOUT, assigned by hand in
forecast/eval/retrieval_gold.json, not from the files' `markets:` frontmatter.
Markets whose gold file does not exist yet are reported separately, not
silently dropped.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from forecast.retrieval import KNOWLEDGE, Retriever, _date, load_chunks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = os.path.join(ROOT, "forecast", "eval", "retrieval_gold.json")
DOC = os.path.join(ROOT, "docs", "retrieval.md")

STAGES = [
    ("R0 plain BM25 over chunks", dict(title_boost=False, expand=False, ticker_match=False, per_file_cap=None)),
    ("R1 + max 2 chunks per file in top-k", dict(title_boost=False, expand=False, ticker_match=False, per_file_cap=2)),
    ("R2 + note title folded into each chunk", dict(title_boost=True, expand=False, ticker_match=False, per_file_cap=2)),
    ("R3 + ticker/state query expansion", dict(title_boost=True, expand=True, ticker_match=False, per_file_cap=2)),
    ("R4 + frontmatter `markets:` ticker match", dict(title_boost=True, expand=True, ticker_match=True, per_file_cap=2)),
    ("R5 + mechanics-concept expansion (designed after R4 misses: eval-tuned)",
     dict(title_boost=True, expand=True, ticker_match=True, per_file_cap=2, concepts=True)),
]


def evaluate(opts: dict, gold: list[dict], chunks, k: int = 5) -> dict:
    r = Retriever(chunks, **opts)
    existing = {c.file for c in chunks}
    scores, misses, missing_gold = [], [], 0
    for g in gold:
        golds = [x for x in g["gold"] if x in existing]
        if not golds:
            missing_gold += 1
            continue
        hits = r.search(g["title"], g.get("rules", ""), g["ticker"], as_of=_date(g["as_of"]), k=k)
        files = {c.file for _, c in hits}
        rec = sum(1 for x in golds if x in files) / len(golds)
        scores.append(rec)
        if rec < 1:
            misses.append({"ticker": g["ticker"], "gold": golds, "got": sorted(files)})
    return {"recall@5": round(sum(scores) / len(scores), 4) if scores else None, "n_markets": len(scores),
            "n_pairs": sum(len([x for x in g["gold"] if x in existing]) for g in gold),
            "markets_without_gold_file": missing_gold, "misses": misses}


def main():
    gold = json.load(open(GOLD, encoding="utf-8"))
    chunks = load_chunks(KNOWLEDGE)
    n_files = len({c.file for c in chunks})
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"\n## Eval run {stamp}", "",
             f"Knowledge: {n_files} files, {len(chunks)} chunks. Eval set: {len(gold)} markets, "
             f"{sum(len(g['gold']) for g in gold)} market→file pairs.", "",
             "| stage | recall@5 | markets scored | pairs scored | markets whose gold file is missing |", "|---|---|---|---|---|"]
    last = None
    for name, opts in STAGES:
        res = evaluate(opts, gold, chunks)
        lines.append(f"| {name} | {res['recall@5']} | {res['n_markets']} | {res['n_pairs']} | {res['markets_without_gold_file']} |")
        print(f"{name:<45} recall@5 {res['recall@5']}  (n={res['n_markets']})")
        last = res
    lines += ["", "Misses at the final stage:", ""]
    for m in last["misses"]:
        lines.append(f"- `{m['ticker']}` gold {m['gold']} → got {m['got']}")
    new = not os.path.exists(DOC)
    with open(DOC, "a", encoding="utf-8") as fh:
        if new:
            fh.write("# Retrieval eval log\n\nEach run re-scores every stage; stages add one change at a time "
                     "(before → after). Produced by `python -m forecast.retrieval_eval`.\n")
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
