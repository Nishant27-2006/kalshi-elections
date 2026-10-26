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
  scores 0 and isn't in the set; coverage, not ranking, is the real limit. Measured 2026-10-09: notes'
  `markets:` tickers cover 510 of 4,169 open political events, but those 510 hold 93.1% of open interest.
- **R2 (title folding) and R5 (concept expansion) are the only changes that moved recall.** R3 and R4 add
  nothing on this set because BM25 already finds the race note. They matter for tickers whose title doesn't
  name the state (e.g. `KXMIDTERMMOV-*`), and the set has few of those.
- **R5 was designed after looking at R4's misses, so its gain is in-sample.** It needs a fresh eval set
  before the number can be trusted. Its first version also caused a regression (CA wealth-tax → top-two
  note), fixed by applying state mechanics only to candidate races.
- **The as-of filter is enforced in `Retriever.search` and covered by
  `tests/test_forecast_invariants.py::test_retrieval_never_returns_future_chunks`.** The six resolved-market
  queries (PRES-2024, CONTROLH-2024, GOVPARTYNJ-25, …) are scored at their own decision dates.

## Eval run 2026-10-09 20:06 UTC — gold set v2

Knowledge: 90 files, 2715 chunks. Eval set: 56 markets, 57 market→file pairs.

| stage | recall@5 | markets scored | pairs scored | markets whose gold file is missing |
|---|---|---|---|---|
| R0 plain BM25 over chunks | 0.9286 | 56 | 57 | 0 |
| R1 + max 2 chunks per file in top-k | 0.9643 | 56 | 57 | 0 |
| R2 + note title folded into each chunk | 0.9643 | 56 | 57 | 0 |
| R3 + ticker/state query expansion | 0.9643 | 56 | 57 | 0 |
| R4 + frontmatter `markets:` ticker match | 1.0 | 56 | 57 | 0 |
| R5 + mechanics-concept expansion (designed after R4 misses: eval-tuned) | 1.0 | 56 | 57 | 0 |

Misses at the final stage:


## Eval run 2026-10-09 20:06 UTC — gold set v1

Knowledge: 90 files, 2715 chunks. Eval set: 74 markets, 78 market→file pairs.

| stage | recall@5 | markets scored | pairs scored | markets whose gold file is missing |
|---|---|---|---|---|
| R0 plain BM25 over chunks | 0.9257 | 74 | 78 | 0 |
| R1 + max 2 chunks per file in top-k | 0.9459 | 74 | 78 | 0 |
| R2 + note title folded into each chunk | 0.9595 | 74 | 78 | 0 |
| R3 + ticker/state query expansion | 0.9459 | 74 | 78 | 0 |
| R4 + frontmatter `markets:` ticker match | 0.9595 | 74 | 78 | 0 |
| R5 + mechanics-concept expansion (designed after R4 misses: eval-tuned) | 0.9797 | 74 | 78 | 0 |

Misses at the final stage:

- `KXCAWEALTHTAX-26` gold ['politics/baserate-ballot-measures.md'] → got ['politics/policy-california-wealth-tax.md', 'politics/policy-trump-executive-actions.md', 'politics/race-2026-governor-california.md']
- `KXTXPRIMARY-26` gold ['politics/cycle-2026-primaries-results.md', 'politics/baserate-primaries.md'] → got ['politics/baserate-primaries.md', 'politics/chamber-2026-senate-control.md', 'politics/race-2026-senate-tx.md']

### Fresh-set (v2) reading, 2026-10-09

- **v2** is 56 markets / 57 pairs, labelled by topic and committed (d15c613) before any retrieval ran on it. 30 of
  its markets are on topics that already had notes; 26 are on topics whose notes were written afterwards by
  research subagents.
- **Existing-topic markets only** (scored before the new notes existed): 0.933 at every stage from R1 to R5. R5's
  concept expansion added nothing on data it wasn't tuned on.
- **Full v2:** 0.929 (R0) → 0.964 (R1, per-file cap) → **1.000 (R4, frontmatter ticker match)**. R2, R3 and R5 add
  nothing. R4's gain is real, but partly by construction for the 26 new-topic markets: their notes list exactly the
  tickers the agents were given. Read it as "notes that declare their markets get found", which is the design, not
  as evidence of ranking quality.
- **v1 with the larger corpus (90 files):** 0.926 → 0.980. R3 (state expansion) now *costs* 1.4 points (0.960 →
  0.946). One new v1 "miss" is the CA wealth-tax market finding its new dedicated note instead of the ballot-measure
  base-rate note it was labelled with. That is a labelling gap, not a retrieval error.
