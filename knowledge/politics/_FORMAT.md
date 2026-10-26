---
aliases:
  - "Politics Knowledge – File Format"
tags:
  - meta
as_of: 2026-10-09
---

# Politics Knowledge – File Format

Same shape as the vault notes (`obsidian-personal-space/vault`): YAML frontmatter with `aliases` and
`tags`, a `# Title` matching the first alias, a `Back to [[...]]` line, wikilinks between notes, and a
`## Timeline` section in `[YYYY-MM-DD] Kind: text URL` form, newest first. Two additions make the notes
usable in a backtest without leakage.

## 1. Every claim is dated and sourced

Each claim is one bullet ending in a provenance tag:

```
- Ossoff led Collins 51–41 among 3,447 RV (YouGov, Sep 15–18). (as_of: 2026-09-23; source: https://...)
```

`as_of` is the date the fact became **publicly knowable**: the publication date of the source, or the
date of the event for results (certification date for official counts). It is NOT the date the note
was written. A backtest at decision time T may only see claims with `as_of < T`.

Rules:
- One fact per bullet, so a single tag covers it. No undated prose claims under `## Claims` or `## Base rates`.
- Write each claim as the source stated it on that date. Do not fold in later knowledge
  ("X, who went on to lose..."); that leaks the outcome into an earlier as_of. A later development is a
  separate bullet with its own later date.
- If a number cannot be verified from a fetched source, do not write it. No placeholders.
- Prose outside `## Claims` / `## Base rates` / `## Timeline` (title, summary line) is treated by the
  retriever as dated at the note's `created` date, so keep it free of facts.

## 2. Frontmatter

```yaml
---
aliases:
  - "Race: 2026 Georgia Senate"
tags:
  - politics
  - race            # race | base-rate | chamber | nomination | policy | international | mechanics
  - senate
  - georgia
created: 2026-10-09        # when the note was written (summary prose is dated here)
as_of: 2026-09-23          # newest claim date in the note
markets:                   # Kalshi series / event tickers this note informs (verified on the API)
  - SENATEGA-26
  - KXGASENATE-26
---
```

## 3. Base rates are machine-readable

Under `## Base rates`, numeric priors use a fixed shape so code can read them:

```
- base_rate: senate_incumbent_reelect_rate = 0.84; n = 230; window = 1982-2022; (as_of: 2022-12-06; source: https://...)
```

`name = value` is required; `n` and `window` when the source gives them.

## 4. Sections, in order

`# Title` → `Back to [[Politics Knowledge Index]]` → one-line scope → `## Claims` → optional
`## Base rates` → optional `## Resolution notes` (how the Kalshi rules settle it, each line tagged) →
`## Related` (wikilinks) → `## Timeline`.
