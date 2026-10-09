# Retrieval eval log

Each run re-scores every stage; stages add one change at a time (before → after). Produced by `python -m forecast.retrieval_eval`.

## Eval run 2026-10-09 06:05 UTC

Knowledge: 71 files, 2195 chunks. Eval set: 74 markets, 78 market→file pairs.

| stage | recall@5 | markets scored | pairs scored | markets whose gold file is missing |
|---|---|---|---|---|
| R0 plain BM25 over chunks | 0.9527 | 74 | 78 | 0 |
| R1 + max 2 chunks per file in top-k | 0.9595 | 74 | 78 | 0 |
| R2 + note title folded into each chunk | 0.973 | 74 | 78 | 0 |
| R3 + ticker/state query expansion | 0.973 | 74 | 78 | 0 |
| R4 + frontmatter `markets:` ticker match | 0.973 | 74 | 78 | 0 |

Misses at the final stage:

- `KXMESENATEPERSON-26` gold ['politics/race-2026-senate-me.md', 'politics/mechanics-runoffs-rcv-top-two.md'] → got ['politics/chamber-2026-senate-control.md', 'politics/cycle-2026-primaries-results.md', 'politics/race-2026-senate-me.md']
- `KXAKSENATE-26NOV03` gold ['politics/race-2026-senate-ak.md', 'politics/mechanics-runoffs-rcv-top-two.md'] → got ['politics/chamber-2026-senate-control.md', 'politics/race-2026-governor-alaska.md', 'politics/race-2026-senate-ak.md', 'politics/race-2026-senate-mi.md']
- `KXGOVAK-26` gold ['politics/race-2026-governor-alaska.md', 'politics/mechanics-runoffs-rcv-top-two.md'] → got ['politics/race-2026-governor-alaska.md', 'politics/race-2026-governor-nevada.md', 'politics/race-2026-senate-ak.md']
- `KXTXPRIMARY-26` gold ['politics/cycle-2026-primaries-results.md', 'politics/baserate-primaries.md'] → got ['politics/chamber-2026-senate-control.md', 'politics/cycle-2026-primaries-results.md', 'politics/race-2026-senate-tx.md']

## Eval run 2026-10-09 06:06 UTC

Knowledge: 71 files, 2195 chunks. Eval set: 74 markets, 78 market→file pairs.

| stage | recall@5 | markets scored | pairs scored | markets whose gold file is missing |
|---|---|---|---|---|
| R0 plain BM25 over chunks | 0.9527 | 74 | 78 | 0 |
| R1 + max 2 chunks per file in top-k | 0.9595 | 74 | 78 | 0 |
| R2 + note title folded into each chunk | 0.973 | 74 | 78 | 0 |
| R3 + ticker/state query expansion | 0.973 | 74 | 78 | 0 |
| R4 + frontmatter `markets:` ticker match | 0.973 | 74 | 78 | 0 |
| R5 + mechanics-concept expansion (designed after R4 misses: eval-tuned) | 0.9932 | 74 | 78 | 0 |

Misses at the final stage:

- `KXTXPRIMARY-26` gold ['politics/cycle-2026-primaries-results.md', 'politics/baserate-primaries.md'] → got ['politics/baserate-primaries.md', 'politics/chamber-2026-senate-control.md', 'politics/race-2026-senate-tx.md']

## Eval run 2026-10-09 06:06 UTC

Knowledge: 71 files, 2195 chunks. Eval set: 74 markets, 78 market→file pairs.

| stage | recall@5 | markets scored | pairs scored | markets whose gold file is missing |
|---|---|---|---|---|
| R0 plain BM25 over chunks | 0.9527 | 74 | 78 | 0 |
| R1 + max 2 chunks per file in top-k | 0.9595 | 74 | 78 | 0 |
| R2 + note title folded into each chunk | 0.973 | 74 | 78 | 0 |
| R3 + ticker/state query expansion | 0.973 | 74 | 78 | 0 |
| R4 + frontmatter `markets:` ticker match | 0.973 | 74 | 78 | 0 |
| R5 + mechanics-concept expansion (designed after R4 misses: eval-tuned) | 0.9932 | 74 | 78 | 0 |

Misses at the final stage:

- `KXTXPRIMARY-26` gold ['politics/cycle-2026-primaries-results.md', 'politics/baserate-primaries.md'] → got ['politics/baserate-primaries.md', 'politics/chamber-2026-senate-control.md', 'politics/race-2026-senate-tx.md']

### How to read these numbers

- **Recall@5 = 0.95 with plain BM25 says the eval is easy.** Most notes were written for exactly these
  markets, so a race note's title shares words with the market title. A market whose topic has no note
  scores 0 and isn't in the set; coverage, not ranking, is the real limit. 1,700+ open political
  events have no note at all.
- **R2 (title folding) and R5 (concept expansion) are the only changes that moved recall.** R3 and R4 add
  nothing on this set because BM25 already finds the race note. They matter for tickers whose title doesn't
  name the state (e.g. `KXMIDTERMMOV-*`), and the set has few of those.
- **R5 was designed after looking at R4's misses, so its gain is in-sample.** It needs a fresh eval set
  before the number can be trusted. Its first version also caused a regression (CA wealth-tax → top-two
  note), fixed by applying state mechanics only to candidate races.
- **The as-of filter is enforced in `Retriever.search` and covered by
  `tests/test_forecast_invariants.py::test_retrieval_never_returns_future_chunks`.** The six resolved-market
  queries (PRES-2024, CONTROLH-2024, GOVPARTYNJ-25, …) are scored at their own decision dates.
