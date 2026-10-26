# Kalshi Predictor — Continuous Loop Log

Format: `[YYYY-MM-DD HH:MM] FINDING: <one line> | FILE: <path> | VERIFY: <command> | STATUS: <pending/confirmed>`

## 2026-08-18 — Cycle 1: portfolio persistence & exit logic

[2026-08-18 00:05] FINDING: PortfolioState.save() defined but called 0 times in tree; state/portfolio.json absent -> load() returns blank every cycle, so duplicate-position / max_open_positions / daily-loss / capital caps never bind | FILE: agent/risk.py:51 | VERIFY: `grep -rn "\.save()" --include=*.py .` -> no hits | STATUS: confirmed
[2026-08-18 00:05] FINDING: no exit path anywhere; execute_node only opens. grep sell/stop/take-profit hits only backtest exit_price_1h/4h columns | FILE: agent/nodes.py:295 | VERIFY: `grep -rn "stop_loss\|take_profit\|sell" --include=*.py agent/` | STATUS: confirmed
[2026-08-18 00:05] FINDING: execute_node gates on RISK.execution_enabled only, not RISK.is_live(); with EXECUTION_ENABLED=true + env=demo it would POST orders. Invariant A requires both | FILE: agent/nodes.py:301 | VERIFY: `sed -n '295,310p' agent/nodes.py` | STATUS: confirmed
[2026-08-18 00:45] FINDING: ledger built; save() now called on every mutation (open_position/close_position, atomic tmp+replace) | FILE: agent/portfolio.py:144,163 | VERIFY: `grep -rn "\.save(" --include=*.py agent/ \| grep -v "def save"` -> 2 hits | STATUS: confirmed
[2026-08-18 00:45] FINDING: all 4 caps now bind against a synthetic Portfolio projected via risk_state() (duplicate / max_open=5 / daily_loss=-25 / capital=100) | FILE: tests/test_risk_caps.py | VERIFY: `python -m pytest tests/test_risk_caps.py -q` -> 8 passed | STATUS: confirmed
[2026-08-18 00:45] FINDING: exit logic added: take_profit (2x entry, capped 97c), stop_loss (0.5x entry), time exit (6h before close). Stop checked BEFORE target so a gap through both books the stop | FILE: agent/exits.py | VERIFY: `python -m pytest tests/test_exits.py -q` -> 19 passed | STATUS: confirmed
[2026-08-18 00:45] FINDING: sub-3c entries cannot carry a percentage stop (50% of 1.3c = 0.65c, not a quotable tick) -> default_levels returns stop=None + hold_to_resolution=True. Directly covers the Fishback 1.3c position | FILE: agent/exits.py:38 | VERIFY: `python -c "from agent.exits import default_levels; print(default_levels(1.3))"` -> (2.6, None, True) | STATUS: confirmed
[2026-08-18 00:45] FINDING: execution gate hardened from RISK.execution_enabled to RISK.is_live(); dry-run now records a paper fill so caps bind in dry run, and emits would_send | FILE: agent/nodes.py:324 | VERIFY: `python -m pytest tests/test_execution_gate.py -q` -> 10 passed | STATUS: confirmed
[2026-08-18 00:45] FINDING: side translation extracted to pure translate_side(side, price, action); yes/no/none + open/close all asserted, no network | FILE: agent/nodes.py:262 | VERIFY: `python -m pytest tests/test_orders.py -q` -> 16 passed | STATUS: confirmed

## 2026-08-18 — Cycle 2: knowledge base + RAG compression

[2026-08-18 01:20] FINDING: cached open_election_events.json (2026-08-06, 883 events, 274 series) contains NO KXFLPRIMARY / KXFLRGOV series -> market_lookup can never match the FL races from cache; --refresh-markets required | FILE: open_election_events.json | VERIFY: `python -c "import json;e=json.load(open('open_election_events.json'));print([v for v in e if 'FLPRIMARY' in v.get('series_ticker','')])"` -> [] | STATUS: confirmed
[2026-08-18 01:20] FINDING: Kalshi ships settlement_sources on 883/883 cached events -> certification-vs-media-call is DERIVABLE, not guesswork. 66.5% official certification (587, concentrated in KXMIDTERMVOTETURN/KXMIDTERMMOV), 10.3% media desk (91 events / 90 series: NYT 82, Politico 64, Reuters 63, WSJ 63, WaPo 61, CNN 60, Fox 59, AP 58), 23.1% other | FILE: agent/knowledge_graph.py | VERIFY: see Update Log in the settlement-sources vault note | STATUS: confirmed
[2026-08-18 01:20] FINDING: Call-Lag Arbitrage pattern only applies to the media-called 10.3%; on certification-sourced contracts there is no desk call to front-run | FILE: vault/Market Mechanics - Kalshi Settlement Sources.md | VERIFY: n/a (documented) | STATUS: confirmed
[2026-08-18 01:20] FINDING: resolution_source slot is now LIVE (was deliberately omitted). 3 new vault notes carry ## Resolution Rules; slot populates on every FL headline | FILE: agent/knowledge_graph.py:220 | VERIFY: `python -m pytest tests/test_expert_context.py -q` -> 17 passed | STATUS: confirmed
[2026-08-18 01:20] FINDING: expert_context had TWO silent bugs — (a) fixed 260-char per-slot allowance let the first 2 slots eat the 800 budget so related_markets/historical_analog never rendered; (b) budget was charged to bare facts, so a nominal 800 cap emitted 898 chars into the prompt. Fixed: fair-share budgeting with roll-forward + render overhead charged | FILE: agent/knowledge_graph.py:255 | VERIFY: `python -m pytest tests/test_expert_context.py -q` | STATUS: confirmed
[2026-08-18 01:20] FINDING: compression now 5,776 raw -> 793 rendered chars with ALL 4 slots (was 5,722 -> ~670 with 3 slots and resolution_source absent). 7.3x, under the 800 prompt cap | FILE: agent/knowledge_graph.py | VERIFY: python snippet printing len(ctx) vs len(block) | STATUS: confirmed
[2026-08-18 01:20] FINDING: vault grew 131 -> 134 notes; new race notes rank #1 seed for their headlines. Askar/Taylor/Martin previously matched ZERO vault entities (entities=0 in the instrumented T2 run) | FILE: obsidian vault | VERIFY: `python -c "...VaultGraph().stats()"` -> notes 134 | STATUS: confirmed

## 2026-08-18 — Cycle 3: scanner filter (live data corrections)

[2026-08-18 02:10] FINDING: Kalshi read endpoints work UNAUTHENTICATED (HTTP 200 on /markets); POST/DELETE hard-fail without creds. So scans run with no .env, and execution stays impossible by construction | FILE: kalshi_client.py:122 | VERIFY: `python -c "import requests;print(requests.get('https://external-api.kalshi.com/trade-api/v2/markets',params={'limit':2}).status_code)"` -> 200 | STATUS: confirmed
[2026-08-18 02:10] FINDING: scanner now has --election-day / --close-after / --close-before / --series-match / --ticker-match / --thin-book / --rank-by / --out. Filtered FL scan: 12 series, 48 markets, 57.9s, exit 0 — vs ~45 min for 575 series (~45x faster) | FILE: find_momentum.py, momentum_filter.py | VERIFY: `python find_momentum.py --series-match KXFL --hours 24 --min-volume 0 --out state/scan_fl_v2.json` -> exit 0 | STATUS: confirmed
[2026-08-18 02:10] FINDING: **close_time is NOT a usable election-day key.** No FL market closes 2026-08-18. Distribution: 2026-11-03 (20), 2027-08-18 (5), 2027-11-03 (23). KXFLRGOVEXACT-26AUG18-* embeds AUG18 in the ticker but closes 2027-08-18; KXGOVFLNOMR-* nomination markets close 2026-11-03 (the general). --election-day 2026-08-18 would return ZERO markets. Added --ticker-match for this | FILE: momentum_filter.py:ticker_matches | VERIFY: close-time distribution from state/scan_fl_20260818.json | STATUS: confirmed
[2026-08-18 02:10] FINDING: ask-sum must group by EVENT, not series. KXFLPRIMARY spans 9 district races; summing its 21 legs gave 922c (read as a huge longshot premium, actually 9 coherent fields added up). Per-event sums are 100-107c = normal vig | FILE: momentum_filter.py:ask_sums_by_event | VERIFY: `python find_momentum.py --series-match KXFLRGOVEXACT` -> KXFLRGOVEXACT-26AUG18 ask_sum=105.00c legs=3 | STATUS: confirmed
[2026-08-18 02:10] FINDING: event_ticker must take the FIRST TWO segments (SERIES-PERIOD), not everything-before-last-hyphen: exact-finish outcomes are themselves hyphenated (DON-COL-REN), which split one event into three | FILE: momentum_filter.py:event_ticker | VERIFY: `python -m pytest tests/test_momentum_filter.py -q` -> 30 passed | STATUS: confirmed
[2026-08-18 02:10] FINDING: an ask_sum BELOW 100 means legs are missing from the scan (volume/candle filters dropped them), NOT an arbitrage. Only >100 is interpretable from a partial field | FILE: momentum_filter.py:INCOMPLETE_FIELD_NOTE | VERIFY: KXFLPRIMARY-22R26 shows 61.00c with legs=2 | STATUS: confirmed

### Live market data (prod, unauthenticated, 2026-08-18) — CONTRADICTS several loop-prompt premises
[2026-08-18 02:10] FINDING: FL governor GOP nomination books are DEEP, not thin. Donalds KXGOVFLNOMR-26-BD bid/ask 98.30/98.50c, 24h vol 2,077,262, OI 5,854,886. Fishback -JFIS 1.20/1.30c, 24h vol 6,519,776, OI 22,909,477. Collins -JCOL 0.20/0.30c, 24h vol 1,242,537, OI 5,842,738. Operator entry prices (~1.3c / ~0.3c) match the live asks exactly | FILE: n/a (live API) | VERIFY: `python -c "...c.get_market('KXGOVFLNOMR-26-JFIS')"` | STATUS: confirmed
[2026-08-18 02:10] FINDING: KXGOVFLNOMR-26 field ask_sum = 100.70c across 9 legs — fully coherent, essentially zero longshot premium. A 22.9M-OI book pricing Fishback at 1.3c is not an illiquid mispricing; it is a deep market's considered view. The DDHQ 37/18/17 and Public Sentinel 31/28/31 polls point the other way, but the loop prompt's own rule applies: do not trade against your own evidence without new information | FILE: n/a | VERIFY: scanner ask-sum output | STATUS: confirmed
[2026-08-18 02:10] FINDING: exact-finish market prices Fishback THIRD. KXFLRGOVEXACT-26AUG18: DON-COL-FIS 68c, DON-FIS-COL 23c, DON-COL-REN 14c (ask_sum 105c). The market's modal ordering is Donalds > Collins > Fishback | FILE: n/a | VERIFY: `python find_momentum.py --series-match KXFLRGOVEXACT` | STATUS: confirmed
[2026-08-18 02:10] FINDING: Taylor/Martin crossover is REAL but is FL-21 DEMOCRATIC, not FL-22R as the loop prompt states. KXFLPRIMARY-21D26-BTAY 0.35->0.61 (+26c, vol 2,286); -JMAR 0.64->0.44 (-20c, vol 2,378). Volumes ~2.3k, not the 7,266/10,458 in the prompt | FILE: state/scan_fl_v2.json | VERIFY: scanner output rows | STATUS: confirmed
[2026-08-18 02:10] FINDING: Askar thin-book repricing CONFIRMED live: KXFLPRIMARY-22R26-CASK 0.14->0.29 (+15c) on 7,373 contracts over 24h. Under conviction ranking scaled to FL-22R depth (280k) it scores 0.0040 and is flagged THIN | FILE: state/scan_fl_v2.json | VERIFY: scanner output row 1 | STATUS: confirmed

## 2026-08-18 — Cycle 4: backtest with real portfolio state

[2026-08-18 02:50] FINDING: hardcoded backtest UNIVERSE has gone stale — 5 of 12 tickers return 0-2 candles, so the default run yields n=4, a sample too small to read. Added --universe-from to consume a find_momentum --out file | FILE: backtest.py | VERIFY: `python backtest.py --days 7 --move 5` -> "4 simulated entries" | STATUS: confirmed
[2026-08-18 02:50] FINDING: backtest evaluated every entry against a blank PortfolioState() — the same dead-caps condition as the live loop. Added --stateful: replays candidates chronologically against ONE Portfolio, positions occupy a slot and consume capital for --hold-hours, ledger kept in a scratch temp file so replay never touches state/positions.json | FILE: backtest.py:simulate_stateful | VERIFY: `ls state/positions.json` -> absent after stateful run | STATUS: confirmed
[2026-08-18 02:50] FINDING: **caps block 72% of entries.** Stateless 50 entries -> stateful 14 (36 blocked). Rejection census: 124 daily-loss-cap hits (dominant), 10 duplicate-position blocks across 3 tickers, plus pre-existing edge/price gates. The daily-loss cap is the binding constraint, not the position count | FILE: backtest.py | VERIFY: `python backtest.py --days 7 --move 5 --universe-from state/scan_fl_v2.json --stateful` | STATUS: confirmed
[2026-08-18 02:50] FINDING: 4h win rate by trigger bucket, 50-entry stateless run on live FL data — 5-10c: 30.8% (n=13, median -$0.70); 10-20c: 10.0% (n=20, median -$0.83); >=20c: 10.0% (n=10, median -$1.85). Reproduces the documented shape (prompt recorded 6.1% / median -$1.75 for >=10c); combined >=10c here is 10.0% (3/30) | FILE: n/a | VERIFY: bucket table in backtest output | STATUS: confirmed
[2026-08-18 02:50] FINDING: with caps binding, 4h win rate goes 16.3% -> 0.0% and total goes -$48.22 -> -$25.40. The caps halve the loss by blocking 72% of entries; they are doing risk control, not alpha selection (most rejections fire once the book is already underwater). >=20c stays the worst bucket: 0% win, median -$4.52 | FILE: n/a | VERIFY: stateful backtest output | STATUS: confirmed
[2026-08-18 02:50] FINDING: the momentum rule is unprofitable at every horizon on this universe (1h -$31.14, 4h -$25.40, end -$23.73 stateful). n=14 is small; do not over-read the level, but the sign and the bucket ordering are consistent across both runs | FILE: n/a | VERIFY: both backtest runs | STATUS: confirmed

## 2026-08-18 — Cycle 5: API audit, time-series vault, non-political markets

### A. API key inventory
[2026-08-18 15:20] FINDING: no hardcoded secrets anywhere. All creds via env; .gitignore covers .env/.env.*/*.pem/*.key/credentials*.json; `git ls-files` tracks only .env.example; no .pem exists in tree. Wrote config/api_keys_required.md (gitignored) | FILE: config/api_keys_required.md | VERIFY: `git check-ignore -v config/api_keys_required.md` | STATUS: confirmed
[2026-08-18 15:20] FINDING: exactly 3 external services — Kalshi (RSA-PSS signing; reads need NO creds, POST/DELETE raise RuntimeError without them), Google News RSS (no key), Anthropic (ANTHROPIC_API_KEY). Vault is local files. risk.py/exits.py/portfolio.py have 0 network refs | FILE: config/api_keys_required.md | VERIFY: `grep -rn "requests\.\|urllib" --include=*.py .` | STATUS: confirmed
[2026-08-18 15:20] FINDING: BLOCKED — ANTHROPIC_API_KEY unset (T2/T5 untestable end-to-end); BLOCKED — KALSHI_API_KEY_ID/PRIVATE_KEY_PATH unset (balance/positions/orders unreachable, live execution untestable). Neither blocks scans, backtests or KG work | FILE: n/a | VERIFY: env check in inventory | STATUS: confirmed

### B. Political KB as a time series
[2026-08-18 15:20] FINDING: 0 of 134 notes had any timestamped observation; `updated:` is day-granularity only. Judge could not distinguish a poll from this morning from one predating the early-vote close | FILE: obsidian vault | VERIFY: `grep -rlE "^## (Timeline\|News Events)" vault \| wc -l` -> 0 | STATUS: confirmed
[2026-08-18 15:20] FINDING: built agent/timeline.py (parse/staleness/forced-update) + agent/vault_writer.py (atomic section-only edits). New `latest_event` context slot injects "FRESH/STALE (Nh old) - newest: <ts> <kind>: <text>" as the FIRST line of every judge prompt | FILE: agent/timeline.py, agent/vault_writer.py | VERIFY: `python -m pytest tests/test_timeline.py -q` -> 40 passed | STATUS: confirmed
[2026-08-18 15:20] FINDING: staleness has 4 triggers — no timestamps at all (stale by construction), observation predating a passed resolution, age > 72h, and a FUTURE timestamp. The future guard was added after I stamped notes an hour ahead of real UTC and got "FRESH (-1h old)"; reporting that as fresh would launder a data error into confidence | FILE: agent/timeline.py:156 | VERIFY: test_a_future_timestamp_is_stale_not_fresh | STATUS: confirmed
[2026-08-18 15:20] FINDING: runner now ingests every headline's pub_date into matching notes. Live run: 184 fetched / 158 new / 144 timeline events written, exit 0. Items with no parseable pub_date are DROPPED, never stamped "now" | FILE: agent/runner.py:cycle | VERIFY: `python -m agent.runner --once` -> vault_events_added=144 | STATUS: confirmed
[2026-08-18 15:20] FINDING: first ingest wrote news into abstract pattern notes (28 events into "Trump Endorsement Primary Premium"). A headline about a candidate is not an observation about a method. Scoped ingestion by tag (TIMELINE_TAGS vs EXCLUDED_TAGS) and stripped timelines from 9 method notes; 33 observational notes retain them | FILE: agent/vault_writer.py:accepts_timeline | VERIFY: `grep -rlE "^## Timeline" vault \| wc -l` -> 33 | STATUS: confirmed

### C. Non-political market KGs
[2026-08-18 15:20] FINDING: 2 non-political notes built with the SAME CONTEXT_SLOTS — KXHIGHNY (NYC daily high temp, 6 legs, mutually_exclusive=True, ask-sum 109c, settles on The Weather Company NOT NWS) and KXCPIYOY (CPI YoY, 26 legs, mutually_exclusive=FALSE, settles on BLS, close 2026-09-11T12:29Z). Both fill 5/5 slots at ~791 chars | FILE: vault | VERIFY: `python -m pytest tests/test_cross_domain.py -q` -> 11 passed | STATUS: confirmed
[2026-08-18 15:20] FINDING: **politics leak #1 (retrieval)** — "NYC heat wave" top-matched "Pattern: Midterm Moderate WAVE Against Populist Incumbent" on the shared token "wave", so a weather contract's prompt carried midterm-backlash analysis. Fixed with subject-over-method ranking (METHOD_PENALTY=0.6): a pattern note is a lens, not a subject | FILE: agent/knowledge_graph.py:_subject_weight | VERIFY: test_a_weather_headline_pulls_no_political_race_note | STATUS: confirmed
[2026-08-18 15:20] FINDING: **politics leak #2 (ask-sum)** — the ask-sum heuristic assumed mutually-exclusive candidate fields. KXCPIYOY is a CUMULATIVE THRESHOLD LADDER (mutually_exclusive=False): 26 legs sum to 939c, which is not an 839c longshot premium but roughly the expected count of legs settling YES. Added is_threshold_ladder(); ladders now report premium=n/a | FILE: momentum_filter.py:is_threshold_ladder | VERIFY: live scan shows "KXCPIYOY-26AUG ask_sum=209.00c premium=n/a (cumulative ladder)" | STATUS: confirmed
[2026-08-18 15:20] FINDING: **politics leak #3 (discovery)** — discover_candidate_series swept ONLY the Elections category, so --series-match KXHIGHNY returned 0 series. Added --category over 7 Kalshi categories; an explicit series filter now also skips the political watchlist seed | FILE: find_momentum.py:CATEGORIES | VERIFY: `python find_momentum.py --category "Climate and Weather" --series-match KXHIGHNY` -> 12 markets, exit 0 | STATUS: confirmed
[2026-08-18 15:20] FINDING: no crypto note exists, and a Dogecoin headline correctly injects NOTHING rather than falling back to the nearest political note | FILE: tests/test_cross_domain.py | VERIFY: test_an_unmodelled_domain_injects_nothing_rather_than_guessing | STATUS: confirmed

### E. Scanner — silent truncation bug (affects ALL prior scans)
[2026-08-18 15:20] FINDING: **scan_series took ONE limit=50 page per series and ignored the cursor.** KXCPIYOY's first page held 50 legs across 3 months with ZERO 24h volume and missed the liquid T3.4 leg entirely, so the series scored 0 and looked inactive. Added _all_open_markets() with cursor-following and a 12-page cap that ANNOUNCES truncation | FILE: find_momentum.py:_all_open_markets | VERIFY: `python -m pytest tests/test_scan_pagination.py -q` -> 7 passed | STATUS: confirmed
[2026-08-18 15:20] FINDING: the same bug hit the POLITICAL scans. FL coverage 48 -> 122 markets: **75 markets (61%) were silently dropped**, so every earlier scan in this log was an arbitrary ~40% sample. Cost 57.9s -> 198.6s, still far under the ~45 min baseline. Re-ranked output written to state/scan_fl_v3.json, exit 0 | FILE: state/scan_fl_v3.json | VERIFY: compare v2 vs v3 ticker sets | STATUS: confirmed
[2026-08-18 15:20] FINDING: non-political scan live — KXHIGHNY-26AUG18-T85 0.54->0.87 (+33c) on 16,765 contracts as the day resolved toward "below 85°"; per-event ask-sums KXHIGHNY 105c / KXHIGHCHI 108c, both correctly typed as exclusive fields | FILE: state/scan_nonpolitical.json | VERIFY: scanner output | STATUS: confirmed

### D. Regression check (prior cycle's work still intact)
[2026-08-18 15:20] FINDING: save() still wired (2 call sites), 4 caps still bind (8 passed), exits + execution gate still pass (29 passed), side translation yes/no/none + open/close still correct, dry-run confirmed. Full suite 176 passed | FILE: tests/ | VERIFY: `python -m pytest tests/ -q` -> 176 passed | STATUS: confirmed

## 2026-08-18 — Cycle 6: MLB vertical KG (first sports industry)

### Vertical selection
[2026-08-18 17:03] FINDING: 0 hub notes existed -> rotation picked MLB (163 series). Novel: first season-accumulation clock (162 games). Chosen over NBA (309 series) because mid-August is MLB in-season while NBA futures are empty (KXNBAFINALS/KXNBACHAMP = 0 open markets) | FILE: n/a | VERIFY: `grep -rl "^  - vertical$" vault \| wc -l` -> 0 | STATUS: confirmed

### Clustering (§5 MANDATORY coverage reporting)
[2026-08-18 17:03] FINDING: MLB ticker grammar clustered to 99% (162/163) across 24 families after TWO passes. Pass 1 with the command's starting hint: 69% (50 unclassified). The residue exposed a whole missing family — 15 per-player game props (KXMLBHR/KS/RBI/TB/WALK/OUTS/PITCH/SS/HA/WA) — plus pennant (MLBAL/MLBNL), personnel (COACHOUT/NEXTMANAGER), and league-business (CBA/EXPAND) families. Only the bare series KXMLB resisted | FILE: n/a | VERIFY: clustering script output | STATUS: confirmed
[2026-08-18 17:03] FINDING: 112 of 163 MLB series have any open market; 51 dormant. Liquidity is extremely concentrated — KXMLB 41.1M OI, KXMLBGAME 1.92M 24h vol (highest), KXMLBTOTAL 1.33M, KXMLBRFI 1.07M | FILE: n/a | VERIFY: per-series OI ranking script | STATUS: confirmed

### THIRD settlement family (predicted in the command's §12, now confirmed)
[2026-08-18 17:03] FINDING: MLB introduces "the Governing League" (mlb.com) as a settlement source alongside media. Per archetype: KXMLB-26 = AP + Fox Sports + ESPN + Governing League (4 sources); KXMLBGAME = ESPN + Fox + Governing League; KXMLBTOTAL = MLB only; KXMLBWINS-BOS = **ESPN ONLY**. A season-long wins total settling on one media outlet's standings page rather than the league's official record is the anomaly worth noting | FILE: vault/Vertical - MLB Pro Baseball.md | VERIFY: get_event(...)['settlement_sources'] per series | STATUS: confirmed
[2026-08-18 17:03] FINDING: Call-Lag Arbitrage does NOT transfer to MLB. Multi-source contracts including the league's own scoreboard have no desk-vs-canvass gap to exploit — the result is definitive within minutes. This is structural, not a liquidity accident | FILE: vault notes | VERIFY: n/a (documented) | STATUS: confirmed

### Bugs found and fixed (both real, both would have corrupted readings)
[2026-08-18 17:03] FINDING: **event_ticker broke on hyphenated SERIES tickers.** first-two-segments mapped KXMLBWINS-BOS-26-T95 -> "KXMLBWINS-BOS", merging EVERY season's Boston wins event into one bogus field. Fixed: prefer the exchange's own event_ticker field; fallback now keys off the PERIOD segment (first token starting with 2 digits) | FILE: momentum_filter.py:event_ticker | VERIFY: `python -m pytest tests/test_momentum_filter.py -q` -> 40 passed | STATUS: confirmed
[2026-08-18 17:03] FINDING: **is_threshold_ladder required a T-prefixed strike.** MLB game totals number legs bare (-9, -12), so every KXMLBTOTAL event was classified as an exclusive field — reporting its 578c cumulative ask-sum as a 478c longshot premium that does not exist. Fixed to accept both spellings | FILE: momentum_filter.py:is_threshold_ladder | VERIFY: live scan shows 15 events typed threshold_ladder with premium=n/a | STATUS: confirmed
[2026-08-18 17:03] FINDING: detector now agrees with the exchange's mutually_exclusive flag on all 4 archetypes, and at scale across 54 live events (39 exclusive_field, 15 threshold_ladder) | FILE: state/scan_mlb.json | VERIFY: scanner ask-sum section | STATUS: confirmed

### Cross-domain collision (place names)
[2026-08-18 17:03] FINDING: MLB club cities collide with the vault's 50 state notes. "Washington at Texas tonight" retrieved State: Washington – Predictive Markets, putting political context in a baseball prompt | FILE: agent/knowledge_graph.py | VERIFY: seed_search on the headline | STATUS: confirmed
[2026-08-18 17:03] FINDING: added DOMAIN_MARKERS disambiguation — vocabulary unique to one domain (inning/bullpen/pitcher vs primary/ballot/certification) boosts matching-domain notes 1.6x and demotes mismatched-domain notes to 0.35x. Every new vertical registers its markers | FILE: agent/knowledge_graph.py:_domain_weight | VERIFY: `python -m pytest tests/test_cross_domain.py -q` -> 34 passed | STATUS: confirmed
[2026-08-18 17:03] FINDING: 20 of 141 notes had NO domain tag, so they escaped the mismatch penalty entirely and election pattern notes hijacked sports headlines. Tagged 18 election notes `politics`; left 2 deliberately neutral (Kalshi settlement mechanics = cross-domain, State Note Template = meta) | FILE: vault frontmatter | VERIFY: domain-tag audit script | STATUS: confirmed
[2026-08-18 17:03] FINDING: the tag `politics` itself was missing from DOMAIN_TAG_FAMILY, so newly-tagged notes still scored 1.0. Family names must map to themselves | FILE: agent/knowledge_graph.py:DOMAIN_TAG_FAMILY | VERIFY: `_note_domain('Trading Pattern: Late Urban Surge...')` -> politics | STATUS: confirmed
[2026-08-18 17:03] FINDING: aliasing all 30 API-derived club names onto the hub HIJACKED the alias index — bare "washington"/"texas"/"colorado" resolved to the MLB hub and broke a political headline. Reverted to the 22 club names that do not collide with a state note; dropped 8 (Arizona, Colorado, Kansas City, New York M, New York Y, Minnesota, Texas, Washington) | FILE: vault/Vertical - MLB Pro Baseball.md | VERIFY: test_state_colliding_club_names_are_not_claimed_as_mlb_aliases | STATUS: confirmed

### Scan
[2026-08-18 17:03] FINDING: full 163-series MLB scan exceeded a 590s inline timeout (exit 124) — pagination over a large sports vertical is genuinely slow. Targeted 3-series archetype scan: 227 records, 150.2s, 0 errors, exit 0. Top mover KXMLBTOTAL-26AUG182005WSHTEX-9 -0.070 on 538,073 contracts. 192 of 227 markets flagged THIN at a 20k reference depth | FILE: state/scan_mlb.json | VERIFY: `python find_momentum.py --category Sports --series-match KXMLBGAME --series-match KXMLBTOTAL --series-match KXMLBWINS-BOS ...` -> exit 0 | STATUS: confirmed

## 2026-08-18 — Cycle 7: European club soccer vertical

### Rotation
[2026-08-18 18:00] FINDING: rotation target #1 (FIFA/WORLDCUP) is DEAD — 13 FIFA series with 1 open market (88 contracts, 32,895 OI), 4 WORLDCUP series with zero. The 2026 tournament finished in July. §3's "re-verify, the board moves" rule caught it; advanced to #2 | FILE: n/a | VERIFY: per-series open-market probe | STATUS: confirmed
[2026-08-18 18:00] FINDING: chose European club soccer (297 series / 10 competitions, 93 live). Novelty: first THREE-outcome market in the graph — MLB's 2-leg no-draw arithmetic cannot transfer — plus in-play halves. UCL is the liquidity centre (KXUCLGAME 421,506 24h vol) | FILE: n/a | VERIFY: liquidity ranking script | STATUS: confirmed

### Clustering
[2026-08-18 18:00] FINDING: soccer grammar is KX<COMP><SUFFIX> and clustered to 98% (292/297) on the FIRST pass across 30 families — much cleaner than MLB's two passes, because every competition reuses one suffix vocabulary. Residue: 4 named UCL round-of-16 tie tickets + one LALIGA2H mis-split by my competition list | FILE: n/a | VERIFY: clustering script | STATUS: confirmed
[2026-08-18 18:00] FINDING: period-scoped (1H/2H) is the LARGEST family at 52 of 297 series — bigger than game moneyline (20), spread (18) or total (18). The most common soccer contract shape has no MLB analogue at all | FILE: vault/Vertical - European Club Soccer.md | VERIFY: family histogram | STATUS: confirmed

### Structural findings
[2026-08-18 18:00] FINDING: the draw is real and priced. KXUCLGAME-26AUG19CELASK = 3 legs (CEL 0.59/0.60, TIE 0.22/0.23, ASK 0.17/0.18), ME=True, ask-sum 101c. Buying NO on a favourite here buys the underdog PLUS the draw — the two-leg inference P(away)=1-P(home) is false | FILE: vault/Market - Soccer Three-Way Match Result.md | VERIFY: get_event on the fixture | STATUS: confirmed
[2026-08-18 18:00] FINDING: a first-half draw prices ~45c vs ~22c full-time — roughly double, because half the minutes means half the goals. Anyone carrying full-time intuition into the 1H market systematically underprices the draw. KXUCL1H-26AUG18LEVAEK ask-sum was exactly 100.0c, the only zero-vig field recorded in this vault | FILE: vault/Market - Soccer First-Half Period Market.md | VERIFY: scanner ask-sum section | STATUS: confirmed
[2026-08-18 18:00] FINDING: **soccer settles MEDIA-ONLY.** Every archetype sampled = ESPN + Fox Sports, with NO governing body. So the "league as settlement authority" family found in MLB is NOT universal to sports — UEFA/Premier League/FIFA appear nowhere as settlement sources. Two media sources with no tiebreak authority is an unverified risk on contested scorelines | FILE: vault/Vertical - European Club Soccer.md | VERIFY: settlement_sources per archetype | STATUS: confirmed

### Bug found and fixed — third structure category
[2026-08-18 18:00] FINDING: **KXUCLBTTS is ONE leg with mutually_exclusive=False** — the same flag a cumulative ladder carries, but it is a standalone binary. is_threshold_ladder returned True, so the structure was reported as a cumulative ladder, implying "leg differences are the density" for a market with no leg differences. Added is_standalone_binary(); taxonomy is now exclusive_field / threshold_ladder / standalone_binary | FILE: momentum_filter.py:is_standalone_binary | VERIFY: `python -m pytest tests/test_momentum_filter.py -q` -> 45 passed | STATUS: confirmed
[2026-08-18 18:00] FINDING: the scanner's ask-sum report filtered `legs > 1`, so standalone binaries were silently omitted from the structure section entirely — an invariant-J-style silent drop. Now shown with premium=n/a (standalone binary) | FILE: find_momentum.py:321 | VERIFY: `python find_momentum.py --series-match KXUCLBTTS` -> 7 binaries listed | STATUS: confirmed

### Isolation (two sports verticals share one domain family)
[2026-08-18 18:00] FINDING: MLB and soccer both map to the `sports` domain family, so DOMAIN_MARKERS alone cannot separate them — separation comes from token IDF on competition/team vocabulary. Verified clean both ways: no MLB term in any soccer block, no soccer term in any MLB block, no political term in either, and politics retrieval unchanged | FILE: tests/test_cross_domain.py | VERIFY: `python -m pytest tests/test_cross_domain.py -q` -> 55 passed | STATUS: confirmed

### Scan
[2026-08-18 18:00] FINDING: soccer archetype scan — 61 records, 4 series, 0 errors, exit 0. All three structures typed at scale: 7 KXUCLGAME events exclusive_field (3 legs, premium +0..+2c), 3 KXUCL1H exclusive_field, 3 KXUCL1HTOTAL threshold_ladder, 7 KXUCLBTTS standalone_binary. Top mover KXUCLBTTS-26AUG18LEVAEK +0.010 on 159,485 contracts | FILE: state/scan_soccer.json | VERIFY: scanner output, exit 0 | STATUS: confirmed

## 2026-08-18 — Cycle 8: crypto digital assets vertical

### Rotation
[2026-08-18 18:33] FINDING: rotation target BTC verified live before commit — 272 crypto series, 78 with open markets; BTC alone 3,186,895 24h vol and 17,712,840 OI across 706 open markets | FILE: n/a | VERIFY: per-asset liquidity probe | STATUS: confirmed

### Clustering
[2026-08-18 18:33] FINDING: crypto grammar is KX<ASSET><HORIZON/SHAPE> where the SUFFIX ENCODES A TIME HORIZON, not a contract type — 15M/H/D/W/MON/M/Q/Y/YEAR. Clustered to 97% (265/272) first pass across 18 families. Residue: 7 price-level milestone series (KXBTC100, KXBTC2025100, KXBTC2026200, KXBTC2026250, KXSOL150, KXSOL26500, KXSOLD26) | FILE: n/a | VERIFY: clustering script | STATUS: confirmed
[2026-08-18 18:33] FINDING: window extremes are the largest family after plain spot — 48 MAX + 32 MIN = 80 of 272 series | FILE: vault/Vertical - Crypto Digital Assets.md | VERIFY: family histogram | STATUS: confirmed

### FOURTH settlement family
[2026-08-18 18:33] FINDING: crypto settles on **CF Benchmarks** — a specialist INDEX PROVIDER, distinct from official certification (politics), media desk (politics/soccer) and governing body (MLB). Crypto has no official price: BTC trades on many venues and any price is a constructed index (BRTI). KXBTCMAXMON rules reference a "trimmed mean". The contract is on THAT INDEX, not on "the price of Bitcoin" | FILE: vault/Vertical - Crypto Digital Assets.md | VERIFY: settlement_sources per archetype | STATUS: confirmed
[2026-08-18 18:33] FINDING: discovered the per-market `rules_primary` field carrying Kalshi's verbatim settlement sentence. Authoritative; should be read rather than inferred from titles. Added to the command as a standing rule | FILE: command §9 | VERIFY: get_market(...)['market']['rules_primary'] | STATUS: confirmed

### PATH DEPENDENCE — a risk the structure taxonomy does not capture
[2026-08-18 18:33] FINDING: KXBTCMAXMON rules_primary reads "If the price of BTC ... is EVER above $67500.00, then the market resolves to Yes" — a ONE-TOUCH BARRIER, not a terminal-value question. It is a ratchet (once touched, permanently YES) and is worth strictly MORE than the same-strike terminal contract | FILE: vault/Market - Crypto Window Maximum.md | VERIFY: rules_primary on KXBTCMAXMON-BTC-26AUG31-6750000 | STATUS: confirmed
[2026-08-18 18:33] FINDING: structure classification (exclusive/ladder/binary) is ORTHOGONAL to path dependence. KXBTCMAXMON and KXBTCD are both threshold_ladder yet have OPPOSITE theta signs — touching accretes probability with elapsed time, closing decays toward spot. Added "path-dep" as a timing frame in the command §6 | FILE: command §6 | VERIFY: n/a (documented) | STATUS: confirmed
[2026-08-18 18:33] FINDING: the barrier window runs "after issuance", not from the start of the calendar month — in the rules text, easy to miss | FILE: vault/Market - Crypto Window Maximum.md | VERIFY: rules_primary | STATUS: confirmed

### Detector edge case
[2026-08-18 18:33] FINDING: Kalshi ships mutually_exclusive=TRUE on some single-leg events (KXBTC2026200) and FALSE on others (KXBTC15M). Leg count must take precedence over the flag — is_standalone_binary is checked first, which was already the case, and is now covered by a test asserting both flag values classify identically | FILE: tests/test_momentum_filter.py | VERIFY: `python -m pytest tests/test_momentum_filter.py -q` -> 50 passed | STATUS: confirmed
[2026-08-18 18:33] FINDING: detector agrees with the exchange on all 4 crypto archetypes, including the 3-segment event ticker KXBTCMAXMON-BTC-26AUG31 (asset token between series and period) which the period-segment rule handles correctly | FILE: momentum_filter.py:event_ticker | VERIFY: detector agreement script -> ALL AGREE True | STATUS: confirmed

### Scanner blind spot
[2026-08-18 18:33] FINDING: **a contract shorter than the candle interval is INVISIBLE to the momentum scanner.** KXBTC15M turns 1,096,851 contracts in 24h and produces ZERO hourly candles, so it scored nothing. Absence from a scan is not absence of liquidity — added to KNOWN TRAPS | FILE: command §9 | VERIFY: get_market_candlesticks on KXBTC15M -> 0 candles | STATUS: confirmed
[2026-08-18 18:33] FINDING: the agent CANNOT trade the 15-minute archetype. At POLL_INTERVAL_SECONDS=300 a 15-minute contract gets ~3 observations across its entire lifetime, and agent/exits.py only evaluates on the poll. Recorded as a stated limitation in the note rather than papered over | FILE: vault/Market - Crypto 15-Minute Price Binary.md | VERIFY: n/a (documented) | STATUS: confirmed

### Observations
[2026-08-18 18:33] FINDING: KXBTC2026200-27JAN01 ("BTC above $200k by 2027") prices 2/3c against 2,631,257 OI on only 10,519 24h volume — large positions opened earlier and held. Two readings fit (stale lottery tickets vs parked size) and the vault has no evidence to separate them; recorded as observation, not signal | FILE: vault/Market - Crypto Long-Dated Price Milestone.md | VERIFY: get_market | STATUS: confirmed
[2026-08-18 18:33] FINDING: KXBTCD ladders carry 188 legs at $100 spacing — the finest strike grid in the vault (vs MLB ~11, CPI 26, soccer 3). Most legs are inert: every sampled leg in the top $700 quoted 0/1c on zero volume and zero OI | FILE: vault/Market - Crypto Daily Price Ladder.md | VERIFY: event leg dump | STATUS: confirmed

### Scan
[2026-08-18 18:33] FINDING: crypto archetype scan — 53 records, 4 series, 234.4s, 0 errors, exit 0. Structures typed: 2 KXBTCD events threshold_ladder (22/23 legs), KXBTCMAXMON threshold_ladder, KXBTC2026200 standalone_binary. Live intraday convergence visible: KXBTCD-26AUG1817-T64249.99 moved 0.57->0.93 on 151,705 contracts as BTC rallied through $64,250 | FILE: state/scan_crypto.json | VERIFY: scanner output, exit 0 | STATUS: confirmed

## 2026-08-18 — Cycle 9: corporate events vertical

[2026-08-18 19:04] FINDING: chose corporate events (82 series in Financials, 39 live). Novel: FIRST vertical with no scheduled resolution instant — a company IPOs when it decides, a board acts when it acts | FILE: n/a | VERIFY: liquidity probe | STATUS: confirmed
[2026-08-18 19:04] FINDING: **FIFTH settlement family** — regulator + THE SUBJECT COMPANY + a news panel. KXIPOANTHROPIC settles on 8 sources including Anthropic itself; KXCOMPANYACTIONMERGER on 21 including SEC EDGAR + Tesla + SpaceX; KXAAPLCEOCHANGE on Apple ALONE. The subject of the contract is an authority on its own outcome — no analogue in politics/sports/crypto | FILE: vault/Vertical - Corporate Events.md | VERIFY: settlement_sources per archetype | STATUS: confirmed
[2026-08-18 19:04] FINDING: panel WIDTH tracks how contested the observation could be — 1 source for a CEO change (unambiguous once announced), 21 for a two-company merger (no single authoritative feed) | FILE: vault notes | VERIFY: n/a (documented) | STATUS: confirmed
[2026-08-18 19:04] FINDING: acquisition/merger markets resolve on the ANNOUNCEMENT of a definitive binding agreement, NOT on the deal closing. Regulatory/closing risk is therefore not priced — the opposite of merger-arb intuition | FILE: vault/Market - Corporate Acquisition Announcement.md | VERIFY: rules_primary | STATUS: confirmed

### Two detector bugs, both found and fixed
[2026-08-18 19:04] FINDING: **event_ticker split date-laddered markets into one event per leg.** KXIPOANTHROPIC-DATE-26SEP01 was grouped as its own event because the trailing date looked like a period, turning an 8-leg ladder into 8 standalone binaries. Fixed: a date-looking segment is the PERIOD when something follows it, the OUTCOME when it is last. Verified against 17 tickers across all 7 domains | FILE: momentum_filter.py:event_ticker | VERIFY: `python -m pytest tests/test_momentum_filter.py -q` | STATUS: confirmed
[2026-08-18 19:04] FINDING: **is_threshold_ladder only accepted monotone-DECREASING strikes.** Corporate markets ladder by DATE and rise with it (later deadline = more likely), so every IPO/merger timing ladder was classified as an exclusive field and its cumulative 531c ask-sum reported as a 431c longshot premium. Fixed to accept either monotone direction; also added date-suffix strike ordering (26SEP01 -> 260901) so the shape heuristic works without the exchange flag | FILE: momentum_filter.py:_strike_value, is_threshold_ladder | VERIFY: live scan groups KXIPOANTHROPIC-DATE as 6 legs / threshold_ladder | STATUS: confirmed

### Observations
[2026-08-18 19:04] FINDING: soft monotonicity inversion on the Anthropic ladder — 27JAN01 asks 0.90 while 27FEB01 asks 0.89; on a CDF a later date should never be cheaper. Bids (0.89 vs 0.87) mean the spread swallows it, so NOT a clean arb, but monotonicity is the cheapest arb check available on date ladders | FILE: vault/Market - Corporate IPO Date Ladder.md | VERIFY: ladder quotes | STATUS: confirmed
[2026-08-18 19:04] FINDING: KXAAPLCEOCHANGE sub_title says "Before 2026" while rules_primary says "before Jan 1, 2027" and close_time is 2027-01-02. rules_primary + close agree, so the sub-title is the outlier. Recorded unresolved rather than guessed | FILE: vault/Market - Corporate CEO Departure.md | VERIFY: get_event vs get_market | STATUS: confirmed
[2026-08-18 19:04] FINDING: CEO-departure markets live at price extremes (Apple at 0.98/0.99), so agent/risk.py's max_price_cents=95 gate rejects them by construction except during a brief genuinely-uncertain window | FILE: vault/Market - Corporate CEO Departure.md | VERIFY: agent/risk.py price band | STATUS: confirmed
[2026-08-18 19:04] FINDING: clustering trap — substring "IPO" also matches KXNIKKEIPOS, KXKOSPIPOS, KXHSIPOS, KXPEPSIPOS, KXALANIPOS, which are index-POS markets. Excluded by hand and documented | FILE: vault/Vertical - Corporate Events.md | VERIFY: series list | STATUS: confirmed
[2026-08-18 19:04] FINDING: replaced two brittle hub-equality tests with growth-tolerant ones (known hubs must survive; every hub must link >=2 archetypes). The old equality assert turned every successful new vertical into a test failure | FILE: tests/test_cross_domain.py | VERIFY: 278 passed | STATUS: confirmed
[2026-08-18 19:04] FINDING: corporate scan — 20 records, 5 series, 0 errors, exit 0. Structures: 2 standalone_binary, 2 threshold_ladder (grouped correctly), 1 exclusive_field. A 2-leg sample cannot be shape-classified (needs >=3 for monotonicity), so KXIPOOPENAI defaulted to exclusive_field with a sub-100 partial-sample ask-sum | FILE: state/scan_corporate.json | VERIFY: scanner output | STATUS: confirmed

### Shared-code fix (orchestrator, while subagents build AI/Space/Weather)
[2026-08-18 19:20] FINDING: **a 2-leg sample with no exchange flag was silently classified exclusive_field and given a premium.** Monotonicity needs >=3 points, so 2 legs are genuinely undecidable — yet KXIPOOPENAI reported premium=-17.00c, a confident-looking number computed from a field never seen whole. Added a fourth structure value `indeterminate` (premium=None) plus a scanner label "2 legs, structure undecidable". The exchange flag still resolves it when present | FILE: momentum_filter.py:_shape_is_undecidable | VERIFY: `python -m pytest tests/ -q` -> 281 passed | STATUS: confirmed
[2026-08-18 19:20] FINDING: two existing tests had encoded the old behaviour (2-leg samples without the flag asserted as exclusive_field). Updated them to carry `mutually_exclusive`, which is what real scanner records contain | FILE: tests/test_momentum_filter.py | VERIFY: 281 passed | STATUS: confirmed
[2026-08-18 19:24] FINDING: scanner counted API errors without ever showing them — "2 errors / 0 markets scored" is indistinguishable from a dead series. The 2 errors turned out to be TRANSIENT rate-limiting under load (a direct call seconds later returned 10 open markets). Now prints series/ticker/reason per error | FILE: find_momentum.py | VERIFY: re-run shows "0 errors" and 3 markets scored | STATUS: confirmed
[2026-08-18 19:24] FINDING: indeterminate label confirmed in live output — KXIPOOPENAI now reads "premium=n/a (2 legs, structure undecidable)" where it previously printed a misleading "-17.00c" | FILE: state/ scan output | VERIFY: `python find_momentum.py --category Financials --series-match KXIPOOPENAI ...` | STATUS: confirmed

## 2026-08-18 — Cycle 10: three verticals in parallel (AI, Space, Weather)

### Fan-out
[2026-08-18 19:30] FINDING: dispatched 3 general-purpose subagents (AI/GPT, Space/Launch, Weather retrofit) with a strict file allowlist — vault notes only, no .py/test/log/command edits, report code bugs rather than fix them. All 3 respected it; suite stayed green throughout | FILE: n/a | VERIFY: `python -m pytest tests/ -q` before and after -> 281 / 329 passed | STATUS: confirmed
[2026-08-18 19:30] FINDING: 3 clusters delivered — AI (186 series/75 live, 99.5% coverage), Space (62/23, 100%), Weather (353/100, retrofit around the existing KXHIGHNY note). 13 new notes, all 5/5 slots, all <=800 chars, zero broken wikilinks across all 7 hubs | FILE: vault | VERIFY: hub link-integrity check -> 0 broken | STATUS: confirmed

### FOUR code bugs reported by subagents, all independently verified before fixing
[2026-08-18 19:30] FINDING: **conditional exclusive field.** KXMODELHIGH-27-1550 is a COMPLETE 8-leg ME=True field (it has an explicit 'Other' leg) asking 37c, because "no model reaches 1550 before 2027" is not purchasable. INCOMPLETE_FIELD_NOTE asserted sub-100 meant "legs missing from the scan" — wrong here. Replaced with SUB_100_FIELD_NOTE giving BOTH readings and attached as a per-event note | FILE: momentum_filter.py | VERIFY: independently confirmed 8 legs incl -OTHE, ask_sum 37c | STATUS: confirmed
[2026-08-18 19:30] FINDING: **the exchange flag is not always right.** KXMOONMAN-31 is a 5-country partition (USA 58.4 / PRC 42.9 / I 5.3 / R 1.9 / E 1.4) asking 109.9c = 100 + ~10c vig, yet Kalshi flags mutually_exclusive=False. Trusting the flag labelled it a ladder and SUPPRESSED a real vig reading | FILE: momentum_filter.py:_flag_only_ladder | VERIFY: independently confirmed via get_event + _all_open_markets | STATUS: confirmed
[2026-08-18 19:30] FINDING: **independent basket — a third structure the taxonomy lacked.** KXRAIN-26AUG19 is 20 DIFFERENT CITIES sharing one event, ME=False, asking 276c. Neither a partition nor a cumulative ladder; the ask-sum has no meaning at all. The flag shortcut ("not exclusive" => "cumulative") mislabelled it a ladder while the SHAPE heuristic got it right | FILE: momentum_filter.py:BASKET_NOTE | VERIFY: real 20-leg event now classifies independent_basket | STATUS: confirmed
[2026-08-18 19:30] FINDING: taxonomy is now 6 values — exclusive_field, threshold_ladder, standalone_binary, indeterminate, independent_basket, disputed. ME=False means "not a partition", which is WEAKER than "cumulative"; three real structures carry that flag and ask-sum separates them | FILE: momentum_filter.py | VERIFY: `python -m pytest tests/test_momentum_filter.py -q` | STATUS: confirmed
[2026-08-18 19:30] FINDING: **honest limit recorded rather than papered over** — prices alone CANNOT separate a mislabelled partition from a basket that happens to sum near 100. The "disputed" label now says AMBIGUOUS and presents the premium as conditional ("a vig reading ONLY under the first reading"), instead of asserting it. Found because my own 10-city test sample summed to 107c and classified as disputed | FILE: momentum_filter.py:DISPUTED_FIELD_NOTE | VERIFY: test_a_basket_and_a_mislabelled_partition_are_separated_by_ask_sum | STATUS: confirmed

### Retrieval collision (found during verification, not reported by the agent)
[2026-08-18 19:30] FINDING: "magnitude 8 earthquake in California" routed to the POLITICAL State: California note. The weather vertical covers geophysics, whose place names collide with the 50 state notes — same class as the MLB city collision. Added earthquake/magnitude/epicenter/seismic/eruption/volcano/tsunami/tornado/precipitation to the weather DOMAIN_MARKERS; verified political place-name headlines still route to state notes | FILE: agent/knowledge_graph.py:DOMAIN_MARKERS | VERIFY: both directions tested | STATUS: confirmed

### Subagent structural findings (recorded, not independently re-derived)
[2026-08-18 19:30] FINDING: AI settlement rules are MUTABLE DOCUMENTS rewritten mid-contract — KXCLAUDE-NXTMYTH hand-patches rules_primary to exclude a specific already-released model; KXGPT-ASTRA carries a ~250-word rules_secondary defining a qualifying release incl. "consensus of credible reporting". Elsewhere the criterion is fixed and only the outcome is uncertain; here the outcome can be public and undisputed while settlement is still open | FILE: vault/Vertical - AI and Machine Learning.md | VERIFY: agent report (not re-derived) | STATUS: pending
[2026-08-18 19:30] FINDING: weather settlement is SPLIT BY HORIZON inside one family — daily KXRAIN NYC settles on The Weather Company, monthly KXRAINNYCM NYC on the NWS Climatological Report for Central Park. Same city, same variable, two agencies, and different structures (the monthly one is a real cumulative ladder) | FILE: vault/Vertical - Weather and Climate.md | VERIFY: agent report (not re-derived) | STATUS: pending
[2026-08-18 19:30] FINDING: space slip risk shows as finalized-'no' rungs still attached to LIVE events (KXNEWGLENN-262 carries -JUL and -AUG finalized beside 5 active rungs). KXSPACEXSTARSHIP-13 overshot SEVEN consecutive date rungs before resolving yes on the eighth | FILE: vault/Vertical - Space and Launch.md | VERIFY: agent report (not re-derived) | STATUS: pending
[2026-08-18 19:30] FINDING: subagents hit HTTP 429 rate limiting under concurrent sweeps — one reported 146 of 351 series throttled, recovered by serial retry with backoff. KalshiClient has no retry/backoff. Not fixed; a real gap for batch scanning | FILE: kalshi_client.py | VERIFY: agent reports x2 | STATUS: pending

## 2026-08-18 — Cycle 11: §2C Historical Analog backfill (orchestrator, serial)

[2026-08-18 19:45] FINDING: dispatched 3 subagents (NBA 309, NFL 287, Economics retrofit 697) — all low-novelty COVERAGE targets whose shapes are already modelled, which is the safe case for parallelism per §2B | FILE: n/a | VERIFY: baseline 329 passed before dispatch | STATUS: confirmed
[2026-08-18 19:45] FINDING: **KalshiClient had no retry/backoff** — two subagents reported 429s (13 of 62 series, then 146 of 351 = 41.6%). Without a retry the caller cannot distinguish throttling from a dead series. Added exponential backoff over 4 attempts on 429/5xx only (a 400/404 is a real answer), honouring Retry-After, re-raising the last error so a failed read is never silent | FILE: kalshi_client.py:get | VERIFY: live GET still returns settled markets; retry config 4 attempts / 0.75s base | STATUS: confirmed
[2026-08-18 19:45] FINDING: **`GET /markets?status=settled` works and returns `result` per leg** — the missing ingredient for the §2C backfill. status=finalized/determined 400; status=closed returns 0. So settled history IS pullable, and every "None recorded" slot was a gap in tooling, not in the data | FILE: agent/history.py | VERIFY: `c.get_markets(series_ticker='KXMLBGAME', status='settled')` -> finalized markets with result=yes/no | STATUS: confirmed
[2026-08-18 19:45] FINDING: built agent/history.py — fetch_settled (cursor-following, announces truncation per invariant J), group_settled, winner_frequency (decided events only; ladders excluded because a cumulative ladder resolves many legs yes at once), yes_rate, ladder_hit_rate. Every rate carries its sample and refuses to publish below a minimum n | FILE: agent/history.py | VERIFY: `python -m pytest tests/test_history.py -q` -> 15 passed | STATUS: confirmed

### First two verified base rates — the vault's weakest slot starts closing
[2026-08-18 19:45] FINDING: **soccer draw base rate = 19/76 = 25.0%**, measured from settled KXUCLGAME contracts. All 76 settled events are 3-leg; the tie leg carries two labels ("Reg Time: Tie" 52, "Tie" 24) which is a labelling variation, not a structural one. This is the exact number the note previously called "the single most important number for pricing this archetype" and listed as missing | FILE: vault/Market - Soccer Three-Way Match Result.md | VERIFY: command embedded in the note | STATUS: confirmed
[2026-08-18 19:45] FINDING: the soccer sample is UCL QUALIFYING rounds (11 matchdays, late Jul–early Aug 2026, clubs like Levski Sofia / Sabah Masazir / Kauno), NOT the group stage. Qualifiers pair mismatched sides more often and lopsided fixtures draw less, so 25.0% is written into the note as a floor-ish estimate explicitly NOT transferable to the group stage or domestic leagues | FILE: same | VERIFY: event-ticker date span | STATUS: confirmed
[2026-08-18 19:45] FINDING: **MLB home-field advantage = 442/856 = 51.6%**, measured from 864 settled KXMLBGAME events (856 two-leg and decided; 8 skipped as voided/postponed, matching the 99.4% any-winning-leg rate). A 1.6-point edge — far smaller than the 60/40 pricing on individual fixtures, which is team quality and starting pitcher, not venue. Written in as a league-wide baseline that is explicitly NOT a per-matchup prior | FILE: vault/Market - MLB Single-Game Moneyline.md | VERIFY: command embedded in the note | STATUS: confirmed
[2026-08-18 19:45] FINDING: both backfilled slots verified to reach the judge prompt — 5/5 slots, 790-791 chars, "Historical analog: ... measured from settled contracts" visible in the rendered block | FILE: n/a | VERIFY: format_expert_context on both headlines | STATUS: confirmed
[2026-08-18 19:45] FINDING: backfill progress 2 of 28 notes; 26 still read "None recorded". Ladder archetypes need a different statistic than winner-frequency (KXBTCD returned 13 events / 0 decided, correctly — every rung resolves) | FILE: vault | VERIFY: `grep -rl 'measured from settled contracts' vault \| wc -l` -> 2 | STATUS: confirmed

### NBA vertical + a scanner bug that invalidated every live classification
[2026-08-18 19:55] FINDING: **the /markets payload does NOT carry `mutually_exclusive` — it is EVENT-level only.** find_momentum stored `m.get("mutually_exclusive")` from the market dict, which is always absent, so the scanner recorded None on every record and the classifier fell back to shape alone. Confirmed live: KXRAIN-26AUG19 (20 independent cities) classified `exclusive_field` with a +176c "premium" that is meaningless. The independent_basket and disputed structures added earlier had NEVER fired in a real scan | FILE: find_momentum.py:attach_event_flags | VERIFY: live scan now prints "independent basket" for both KXRAIN events, exit 0 | STATUS: confirmed
[2026-08-18 19:55] FINDING: fixed by fetching the flag per EVENT (cached; a 39-record KXRAIN sweep touches 2 events) before classification. A lookup failure leaves the record None rather than guessing, so the shape path still applies | FILE: find_momentum.py | VERIFY: `python -m pytest tests/test_scan_pagination.py -q` | STATUS: confirmed
[2026-08-18 19:55] FINDING: `ask_sum_cents` read only `r["yes_ask"]`, which the raw /markets payload does not have (it ships `yes_ask_dollars` as a string). ask_sums_by_event returned {} SILENTLY on raw records — a caller saw "no events" rather than "wrong field". Now accepts either shape | FILE: momentum_filter.py:_ask_cents | VERIFY: raw-record test | STATUS: confirmed
[2026-08-18 19:55] FINDING: NBA cluster verified — hub + 4 archetypes (Championship Field, Next Team Destination, Award Winner, Season Wins Ladder), 221 series after excluding 88 WNBA substring false positives, 100% coverage. 5/5 slots on all five notes | FILE: vault | VERIFY: retrieval check | STATUS: confirmed
[2026-08-18 19:55] FINDING: NBA is 81.0% dormant in the off-season — 179 of 221 series with no open market, $29.9M OI against $270k 24h volume (0.9% turnover). ALL 31 in-game segment series and ALL 25 player-prop series are at zero. Every dollar of OI sits in futures | FILE: vault/Vertical - NBA Pro Basketball.md | VERIFY: agent report | STATUS: pending
[2026-08-18 19:55] FINDING: NBA's #2 series by OI ($7.03M) is KXNEXTTEAMNBA — a FREE-AGENCY TRANSACTION contract, not a sporting outcome. Structurally closer to [[Market: Corporate CEO Departure]] than to anything in baseball, and the only top-liquidity NBA contract resolving in 2026 | FILE: vault/Market - NBA Next Team Destination Field.md | VERIFY: agent report | STATUS: pending
[2026-08-18 19:55] FINDING: settlement INVERTS the MLB exposure — MLB season wins settles on ESPN ALONE, NBA season wins on ESPN + the Governing League. MLB's single-outlet standings risk is absent in the NBA | FILE: vault notes | VERIFY: agent report | STATUS: pending

### Retrieval regression caught by verification (not reported by the agent)
[2026-08-18 19:55] FINDING: **once NBA existed, "Boston on pace to win 90 games this season" routed to the NBA Season Wins Ladder.** MLB/NBA/NFL all map to the `sports` domain family, so generic vocabulary (season/wins/games) is shared and cannot separate them. Added league sub-families with only-one-league words (inning/pitcher/bullpen vs rebound/dunk/basketball vs touchdown/quarterback) | FILE: agent/knowledge_graph.py:DOMAIN_MARKERS | VERIFY: 6 disambiguation cases pass both directions | STATUS: confirmed
[2026-08-18 19:55] FINDING: two of my own tests were stale, not broken code — the MLB headline was genuinely ambiguous once NBA was modelled (made league-explicit), and "primary" as a political leak term matches `rules_primary`, which legitimately appears in many Resolution Rules sections (replaced with "gop primary" in 4 places) | FILE: tests/test_cross_domain.py | VERIFY: 369 passed | STATUS: confirmed

### NFL + Economics (cycle 12)
[2026-08-18 20:05] FINDING: the Economics subagent DIED mid-run (connection lost) after writing 3 archetype notes but before the hub — leaving orphan archetypes reachable from no hub. Exactly the §2A rule-5 failure mode, inverted. The orphans were verified complete (correct sections, 5/5 slots, retrieving) and adopted; the orchestrator wrote the hub around them | FILE: vault/Vertical - Economics and Macro.md | VERIFY: `python -m pytest tests/ -q` -> 389 passed | STATUS: confirmed
[2026-08-18 20:05] FINDING: added two structural guards so this cannot pass unnoticed again — no hub may link fewer than 2 archetypes or dangle a link, and EVERY Market: note must be reachable from some hub | FILE: tests/test_cross_domain.py | VERIFY: test_no_hub_is_left_half_built, test_every_market_note_is_reachable_from_some_hub | STATUS: confirmed
[2026-08-18 20:05] FINDING: **economics settlement is SPLIT BY STATISTIC** — independently verified on four events: CPI->BLS, rates->Federal Reserve, recession->BEA, retail fuel->AAA. Two are qualitatively unusual: the Fed SETTLES ITS OWN DECISION (no measurement error, nothing to revise), and retail fuel settles on a PRIVATE VENDOR, mirroring weather's Weather Company | FILE: vault/Vertical - Economics and Macro.md | VERIFY: get_event settlement_sources on all four | STATUS: confirmed
[2026-08-18 20:05] FINDING: economics contracts settle on the ADVANCE ESTIMATE vintage — the first print, not a revision. KXSAHM states "Revisions to previously published values will not be considered". A contract can settle on a number the agency later corrects and stay settled. No analogue elsewhere in the vault | FILE: vault/Market - Economics Recession Binary.md | VERIFY: rules_secondary | STATUS: confirmed
[2026-08-18 20:05] FINDING: KXRECSSNBER settles on the BEA despite NBER sitting in the series ticker; its window reaches BACKWARDS ("in 2025 or 2026"), so contractions already in the record could resolve a contract that reads as being about this year | FILE: same | VERIFY: rules_primary | STATUS: confirmed
[2026-08-18 20:05] FINDING: **NFL handles ties TWO different ways inside one vertical.** Verified verbatim: KXNFLGAME rules_secondary says "If the game ends in a tie, the market will resolve to $0.50 for each team" — the ONLY fractional payout in the vault — while KXNFL1Q carries an explicit third leg ("Tie 1st Quarter"). So a 2-leg ME=True field can have a non-binary payout while its ask-sum reads normally | FILE: vault/Market - NFL Single Game Moneyline.md | VERIFY: get_market rules_secondary on both | STATUS: confirmed
[2026-08-18 20:05] FINDING: the NFL agent INDEPENDENTLY found the event-level ME flag bug (it ran before the fix) and correctly deduced the consequence I had not stated: three of six taxonomy values (disputed, independent_basket, and indeterminate-for-2-legs) were unreachable in practice. Post-fix verified: all 36 KXNFLGAME events now classify exclusive_field with a real +0..+1c premium instead of indeterminate | FILE: find_momentum.py | VERIFY: live scan on KXNFLGAME, exit 0 | STATUS: confirmed
[2026-08-18 20:05] FINDING: board counts drift materially — Economics 697 (command) vs 712 (today), Sports 3,444 vs 3,445. Added to KNOWN TRAPS: re-verify, never cite the cached number | FILE: command §9 | VERIFY: get_series_list length | STATUS: confirmed

## 2026-08-19 — Cycle 13: §2C Historical Analog backfill at scale

[2026-08-19 02:40] FINDING: dispatched 3 coverage subagents (index/equities, NHL, combat sports) and took the §2C backfill as serial work — surgical edits to EXISTING notes are riskier than fresh writes, so they stay with the orchestrator | FILE: n/a | VERIFY: baseline 389 passed | STATUS: confirmed
[2026-08-19 02:40] FINDING: **most "None recorded" slots are CORRECT, not a tooling gap.** Surveyed 18 primary series: KXOAIAGI, KXMODELHIGH, KXACQANNOUNCEEBAY, KXBTC2026200, KXRECSSNBER, KXMLB, KXMLBWINS all return ZERO settled markets. These are long-dated contracts (championships, IPOs, recessions, season wins) that have not resolved yet — they have no history BY CONSTRUCTION at this point in their lifecycle. The backfillable set is the high-frequency archetypes, not all 34 notes | FILE: n/a | VERIFY: fetch_settled per series | STATUS: confirmed

### Three more verified base rates
[2026-08-19 02:40] FINDING: **KXBTC15M is a fair coin — 1,196 of 2,400 settled legs resolved YES = 49.8%.** Every event is a single leg, so the YES rate IS the realised hit rate of the spot-referenced strike. This closes the exact gap the note flagged ("for a contract this short the realised distribution IS the fair value"): the unconditional edge is ~zero, so any edge must come from inside the fifteen minutes | FILE: vault/Market - Crypto 15-Minute Price Binary.md | VERIFY: command in the note | STATUS: confirmed
[2026-08-19 02:40] FINDING: **MLB game totals — 193 complete settled games, median total ~10 runs**, right-skewed with a thin tail (one game >23). The measured median matches the live book's 50c crossing at the 9-run leg. Two caveats written in: sample CAPPED at the 12-page fetch limit, and "highest rung reached" is censored where a game exceeded the top listed rung | FILE: vault/Market - MLB Game Totals Ladder.md | VERIFY: command in the note | STATUS: confirmed
[2026-08-19 02:40] FINDING: **KXLLM1 top-model slot — Claude won 12 of 12 decided events (100%)**. Written in with the caveat that matters more than the number: 12 consecutive events are highly AUTOCORRELATED (leaderboard leadership is persistent), so this is closer to one uninterrupted run than twelve independent trials. It licenses a strong incumbency prior, NOT a 100% forward probability | FILE: vault/Market - AI Top Model Ranking Field.md | VERIFY: command in the note | STATUS: confirmed
[2026-08-19 02:40] FINDING: backfill now 5 of 39 notes. Both large samples (KXBTC15M, KXMLBTOTAL) hit fetch_settled's 12-page cap with a cursor outstanding, and the cap is stated in each note per invariant J rather than presenting 2,400 as the complete history | FILE: vault | VERIFY: `grep -rl 'easured from settled contracts' vault \| wc -l` -> 5 | STATUS: confirmed

### NHL + Combat + Equities (cycle 13, subagents)
[2026-08-19 03:00] FINDING: 3 clusters delivered — NHL (50 series, 100% coverage, 39 dormant), Combat (45 series, 100%), Equities (97 index series, 98.7% of all 991 Financials). 13 hubs total, 0 broken wikilinks, 199 notes | FILE: vault | VERIFY: hub integrity check | STATUS: confirmed
[2026-08-19 03:00] FINDING: **NHL has NO tie mechanism at all** — 2-leg ME=True with an EMPTY rules_secondary, because hockey always manufactures a winner. That is the MLB shape, not NFL's $0.50-each-side. Shootouts appear only in the GOAL TOTAL: "the shootout result will be recorded as one goal awarded to the winning team", so a 3-3 shootout totals 7. KXNHLSPREAD has empty rules_secondary despite identical exposure — flagged unverified | FILE: vault/Market - NHL Single-Game Puck Line.md | VERIFY: agent report | STATUS: pending
[2026-08-19 03:00] FINDING: **draws now have FOUR distinct treatments across the vault** — none (MLB, NHL), 3-leg field (soccer), fractional 50/50 (NFL, UFC bout winner), explicit -DRAW leg (UFC method of victory), bundled into OTHER (UFC round). Combat carries three of them inside ONE vertical. Boxing draw settlement is undocumented in the payload across all 24 live legs | FILE: vault/Vertical - Combat Sports.md | VERIFY: agent report | STATUS: pending
[2026-08-19 03:00] FINDING: **Kalshi lists NO single-stock price market.** KXTESLA/KXAAPLA/KXNVDAA/KXGOOG and ~275 KX<TICKER>A series are Fiscal.ai KPI contracts (revenue, funded customers, deliveries) — the biggest ticker-shaped trap in Financials. Added to KNOWN TRAPS | FILE: vault/Vertical - Stock Indices and Equities.md | VERIFY: agent report | STATUS: pending
[2026-08-19 03:00] FINDING: equities market hours are real and visible — KXINXU emits exactly 7 events/day (H1000-H1600, no overnight/weekend, vs KXBTCD hourly around the clock); only the 16:00 leg says "end-of-day" in rules_primary; only it carries a 3-hour expiration lag for the official close to publish | FILE: same | VERIFY: agent report | STATUS: pending

### Three code bugs from these agents — all verified before fixing
[2026-08-19 03:00] FINDING: **a premium was reported for books that cannot support one.** Finalized legs quote ask 1.0000 win OR lose, so a settled 7-leg KXUFCMOV event returned +600c presented identically to real vig; a quoteless book (all bids <=3c) returned +516c, which measures dormancy. Added premium_is_readable(): structure label unaffected, only the derived premium withheld, with a note naming which case fired | FILE: momentum_filter.py:premium_is_readable | VERIFY: live settled/quoteless/healthy books all classify correctly | STATUS: confirmed
[2026-08-19 03:00] FINDING: **is_threshold_ladder still read `yes_ask` directly** while raw /markets records ship only `yes_ask_dollars`. `asks` came back empty, the len<3 guard fired, and genuine ladders (KXINXU 60-leg session, KXHOODA KPI) fell through to exclusive_field with a fabricated +2,345c / +841c premium. Worse, _flag_only_ladder calls it, so attaching the exchange flag mislabelled them independent_basket instead. I had fixed ask_sum_cents for exactly this and MISSED this call site | FILE: momentum_filter.py:is_threshold_ladder | VERIFY: 4 raw-record shapes now classify correctly; 412 passed | STATUS: confirmed
[2026-08-19 03:00] FINDING: **my own domain-family change caused a regression.** Giving MLB/NBA/NFL their own families meant a headline with only GENERIC sports vocabulary boosted generic-sports notes 1.6x while demoting league-tagged notes to 0.35x — so "Rays favored to win the World Series" routed to Vertical: NHL Pro Hockey. Fixed with a parent hierarchy: sports is the parent of mlb/nba/nfl/hockey/combat | FILE: agent/knowledge_graph.py:DOMAIN_PARENTS | VERIFY: 14-domain regression, all route correctly | STATUS: confirmed
[2026-08-19 03:00] FINDING: registered domain vocabulary for the three new verticals (combat: knockout/submission/octagon/bout; hockey: puck/goalie/faceoff/shootout; equities: nasdaq/premarket/dividend) and stopworded bare interrogatives — "which round will the bout end" was hitting a SPACE note via "which" and an EQUITY note via "end" | FILE: agent/knowledge_graph.py | VERIFY: 14-domain regression | STATUS: confirmed
[2026-08-19 03:00] FINDING: two test-term false positives corrected — "spacex" flagged the Corporate hub, which legitimately lists KXIPOSPACEX as an IPO target; narrowed to space-vertical-only terms | FILE: tests/test_cross_domain.py | VERIFY: 412 passed | STATUS: confirmed
[2026-08-19 03:00] FINDING: `test_no_hub_is_left_half_built` runs RED while a subagent is mid-write (hub written, last archetype pending). The test is correct and the timing is the issue; it is a checkpoint gate, not a during-build gate. Recorded rather than weakened | FILE: tests/test_cross_domain.py | VERIFY: passed once the equities agent finished | STATUS: confirmed

## 2026-08-19 — Cycle 14: board re-verification + backfill round 2

[2026-08-19 04:10] FINDING: **§2C item 4 board re-verification — drift is material.** Sports 3,444->3,453, Weather 351->354, Economics 697->741 (+44 in ONE DAY). Financials/Crypto/SciTech unchanged. §3 now carries the drift explicitly and warns that per-key counts are a hint, not a fact | FILE: command §3 | VERIFY: get_series_list per category | STATUS: confirmed
[2026-08-19 04:10] FINDING: **soccer BTTS base rate = 38/79 = 48.1%**, measured from settled KXUCLBTTS. Sits just under the live 52/53c quote, so the archetype is priced near its realised rate rather than at a systematic premium. The note had called this "well-defined and highly tradeable" and unsourced | FILE: vault/Market - Soccer Both Teams To Score.md | VERIFY: command in note | STATUS: confirmed
[2026-08-19 04:10] FINDING: **first-half tie rate = 33/65 = 50.8%**, versus a measured FULL-TIME tie rate of 25.0%. Almost exactly double — which confirms from data the structural claim the note had made from prices alone (half the minutes, half the goals, compressed toward the draw) | FILE: vault/Market - Soccer First-Half Period Market.md | VERIFY: command in note | STATUS: confirmed
[2026-08-19 04:10] FINDING: the first-half book prices the TIE at 45/46c against a measured 50.8%. Written into the note as "a reason to check the pricing, not evidence of an edge" — same qualifying-round sample, n=65, and lopsided fixtures draw less at any horizon | FILE: same | VERIFY: same | STATUS: confirmed
[2026-08-19 04:10] FINDING: **KXRAIN per-city rates span 65 points** — ATL 19/29=65.5%, NYC 51.7%, MIA 44.8%, DC 31.0% vs LV 6.9%, DAL 3.4%, LAX 0/29=0.0%. The 21.0% pooled rate describes NO tradeable contract. This is the clearest demonstration in the vault of what `independent_basket` means: legs share an event but not a subject, which is also why the 276c ask-sum carries no interpretation | FILE: vault/Market - Weather Daily Precipitation Basket.md | VERIFY: command in note | STATUS: confirmed
[2026-08-19 04:10] FINDING: backfill now 8 of 39 notes. All three new entries state their sample window and its limits (UCL qualifying rounds; 29 late-summer days for rain, where LAX 0/29 is a dry-season fact and NOT a claim it never rains) | FILE: vault | VERIFY: `grep -rli 'measured from settled contracts' vault \| wc -l` -> 8 | STATUS: confirmed

## 2026-08-19 — Motorsport + College Sports clusters, and three detector fixes

169. [2026-08-19] Motorsport cluster complete: hub + 4 archetypes (Race Winner
     Grid 41 legs/133c, Qualifying Pole 22 legs/115c, Season Championship,
     Finishing Position Basket). 66 series, 100% grammar coverage.
170. [2026-08-19] Motorsport: QUALIFYING IS A SEPARATE EVENT ~23h before the
     race. Winner and top-10 books on the same NASCAR race close 7 days apart.
171. [2026-08-19] TRAP: `settlement_sources` is EVENT-level. `get_market()`
     returns null for it; only `get_event()` carries it.
172. [2026-08-19] TRAP: `close_time` is a PADDED BACKSTOP, not the event time.
     `occurrence_datetime` is the real one. Every vertical so far has shown a
     multi-day gap (MLB +3d, soccer +3d, college +2d).
173. [2026-08-19] Vig scales loosely with field size, so _VIG_BAND's 130c
     ceiling is NOT an upper bound on real fields: 22 legs 115c, 41 legs 133c,
     45 legs 138c, 50 legs 143c. Any flat ask-sum cap rejects real grids.
174. [2026-08-19] Red-flag / shortened-race rules are UNVERIFIED in motorsport —
     silent across all 1,089 legs read.
175. [2026-08-19] BUG FIXED (momentum_filter): `exclusive_field` guarded the
     BELOW-100 ask-sum but not the far-above case. First fix used a per-leg ask
     allowance; the college agent showed that was wrong-headed — see 176.
176. [2026-08-19] BUG FIXED properly: the discriminator is the BID-sum, not the
     ask-sum. A partition pays 100c total, so selling every leg cannot be worth
     much more than 100c however many legs there are; the ASK-sum just widens
     with illiquidity. Live proof — KXNCAAFAPRANK-26W12R1 asks 219c on 13 legs
     but BIDS 41c (a real AP-poll partition, one 96c favourite + twelve
     zero-bid longshots); KXF1TOP10-DUTGP26 bids 966c across 22 legs, so it is
     provably not a partition. The ask-based version flagged the first and the
     bid-based version flags only the second.
177. [2026-08-19] BUG FIXED: `is_threshold_ladder` tested monotonicity on the
     ASK side only. KXNCAAFWINS-26SCAR asks 85 70 49 36 36 18 63 96 — the 11+
     and 12+ rungs quoted wide against a ZERO bid — so a textbook "at least N
     wins" ladder was demoted to `independent_basket` and the reader told to
     price each leg on its own, exactly backwards. Its bids run 72 65 47 29 19
     7 1 0. Now tested on BOTH sides, accepted if either is monotone.
178. [2026-08-19] BUG FIXED (knowledge_graph): domain detection shared the
     note-matching tokenizer, so words stopworded as TITLE boilerplate were
     also invisible to DOMAIN_MARKERS. "senate", "governor", "election" and
     "primary" are all stopwords (111 political notes are titled `Race: ...` /
     `State: ...`), which made all four politics markers UNREACHABLE. "Senate
     race in Georgia" detected no domain, took no politics boost, and routed to
     an EQUITIES note. Split `_domain_tokens` from `_tokens`.
179. [2026-08-19] BUG FIXED (knowledge_graph): the `sports` parent boost was
     handed to rival leagues. Once the College cluster landed, "Josh Allen wins
     the AP Regular Season MVP quarterback" routed to
     `Market: College Season Wins Ladder` — the headline says `nfl` outright,
     but both notes sat under `sports` and college shared more tokens. Parent
     boost now applies only when the headline names NO league.
180. [2026-08-19] College Sports cluster complete: 313 series (243 by NCAA
     token + 70 with none), 100% coverage, 119 live / 194 dormant, 31.2M OI.
181. [2026-08-19] TRAP: `KXNCAABB*` is college BASEBALL, not basketball; men's
     basketball is `KXNCAAMB*`. And `KXNCAAMBACHAMP` is titled "College
     Baseball Championship" despite the MB prefix. A bare `NCAAB` filter
     silently mixes two sports.
182. [2026-08-19] TRAP: `KXTENNCOACH` is the Tennessee TITANS (pro); the
     one-letter-shorter `KXTENCOACH` is collegiate.
183. [2026-08-19] NEW SETTLEMENT FAMILY (7th): HUMAN JUDGEMENT. Three kinds —
     a sportswriters' ballot (AP poll, single source, no fallback), a private
     paywalled computer rating (KenPom alone), and a SELECTION COMMITTEE
     ("if X is *selected as* a top 4 seed"). Selected, not earned.
184. [2026-08-19] College settles as `Kalshi using information originating from
     the NCAA` with a SPORT-SPECIFIC url, usually + ESPN — not the pro
     `the Governing League`. But the national title series KXNCAAF names no
     NCAA source at all (WSJ/ESPN/Fox): the CFP is a separate corporate entity.
185. [2026-08-19] College ties: pattern #1 (none at all) on games — 176
     KXNCAAFGAME events are bare 2-leg ME=True fields, no tie sentence, despite
     otherwise cloning the NFL template that pays $0.50 each way. But a FIFTH
     treatment appeared: 8 `-TIE` legs exist and NONE is on a game — seven on
     KXNCAAFH2HWINS (a season-win comparison) and one on a coaching award. The
     tie leg attaches to a multi-game aggregate, never to a contest.
186. [2026-08-19] TRUNCATION ANNOUNCED: `KXNCAAFTOPAPRANK` returned exactly
     2,400 open markets = MAX_MARKET_PAGES(12) x 200 with a cursor still
     outstanding. Its 3,136 OI / 3,111 v24 are FLOORS. All other 312 series
     completed their cursors.
187. [2026-08-19] KALSHI-SIDE METADATA BUG (theirs, not ours): six pro/soccer
     series carry the collegiate NCAA settlement source — KXEPLANYGOAL and
     KXNFL{1H,1Q,2H,2Q,3Q,4Q}WINNER. Any settlement_sources scan for "NCAA"
     over-collects and must be title-checked.
188. [2026-08-19] `get_event()` returns an EMPTY `markets[]` for collegiate
     events — absent, not merely price-free. Prices require
     `get_markets(event_ticker=..., status='open')`.
189. [2026-08-19] Company KPI cluster complete: hub + 5 archetypes. The
     premise was only two-thirds right — Fiscal.ai is 275 series, but the
     reliable family marker is the series `KPIs` TAG, not the settlement
     source and not the ticker: 320 series across FIVE categories, 45 of them
     non-Fiscal. 256 live / 64 dormant, 982,314 OI, 316 open events.
190. [2026-08-19] ALL 316 open KPI events are `mutually_exclusive: false`.
     Not one partitioned field exists in the vertical.
191. [2026-08-19] KPI settlement splits by series GENERATION, not KPI type:
     Fiscal.ai alone (275 series), company self-report (31), media panel of
     10–21 names (14). Never the SEC, never an independent recomputation.
     Every rule uses the verb "reports" — the contract keys off the company's
     own published figure and Fiscal.ai is a transcription layer over it.
192. [2026-08-19] RESTATEMENTS ARE UNVERIFIED, definitively: zero occurrences
     of restate/revise/amend/correct/supersede/"as reported" across all 2,554
     live KPI markets. No source-precedence rule anywhere in the family —
     materially weaker than economics' explicit advance-estimate clause, and
     worst on the panel-settled markets (10 sources, no precedence, blank
     secondary).
193. [2026-08-19] KPI clock: `can_close_early: true` on 2,554 of 2,554 and
     `strike_date` null on all 316 events. SHARPEST HAZARD — 752 markets have
     `close_time` up to 30 days BEFORE `expected_expiration_time`: trading
     stops a month before the metric is known. 1,253 equal, 522 run up to 90
     days after. The sign is not uniform; check per market.
194. [2026-08-19] TRAP: category is NOT stable between the two /series calls.
     `get_series_list(category='Financials')` returns all 275 Fiscal.ai
     series; the unfiltered listing labels 244 `Financials` and 31
     `Companies`. Identical ticker sets. Any code keying on category
     miscounts.
195. [2026-08-19] BUG FIXED: `is_threshold_ladder` derived strikes from the
     TICKER TAIL only. COSTCOHOTDOG classifies correctly purely by luck — its
     tails are years (27/28/29/30) while `floor_strike` is null on every leg.
     Now prefers `floor_strike`/`cap_strike` (present and authoritative on
     KXRIVNA 68000, KXNCAAFWINS 9, KXCPIYOY 2.5) and falls back to the tail.
196. [2026-08-19] Stale vault claim CORRECTED by re-measurement: the KPI note
     logged `KXHOODA-28JANFUNDED` returning `exclusive_field +841c`. Re-run
     today it returns `threshold_ladder / 941.0c / premium null`. The earlier
     `_ask_cents` fix already cured it; that Update Log entry is stale.
197. [2026-08-19] Kalshi-side defects: COSTCOHOTDOG mixes `KXCOSTCOHOTDOG-*`
     and `COSTCOHOTDOG-*` ticker prefixes INSIDE ONE EVENT, and all four legs
     share one `expected_expiration_time` regardless of horizon.
     `KXTESLASEMI`'s series record lists 15 settlement sources while its event
     record lists 10 — they disagree and nothing says which governs.
198. [2026-08-19] Live classification sweep after all detector changes: 7/7
     correct across all three structures — KXCOSTCOHOTDOG/KXRIVNA/KXCPIYOY/
     KXNCAAFWINS ladders, KXF1POLE/KXNCAAF fields, KXRAIN basket.

## 2026-08-19 — Tennis vertical

199. [2026-08-19 15:17] Tennis cluster complete: hub + 4 archetypes
     (Tournament Winner Field, Match Head-to-Head, Match Games Ladder, Player
     to Compete Binary). 73 series, 24 live / 49 dormant, OI 7,264,129, 24h
     volume 5,051,036. Grammar coverage 58.9% -> 100% in two rounds; residue
     named 12 per-site tournament fields, a set-scoped game family, 5 player
     stat props.
200. [2026-08-19 15:17] EIGHTH SETTLEMENT FAMILY — THE EXCHANGE ITSELF, BY
     DISCRETION. An identical 783-char rules_secondary clause on every
     match-scoped tennis series ends: "Any markets that cannot be
     unconditionally settled will resolve to Fair Market Price, as determined
     at the sole discretion of the Exchange." Every prior family named an
     OUTSIDE authority; this one names Kalshi and states no formula. NFL's
     $0.50 tie payout is a stated rule — this is a post-hoc judgement.
201. [2026-08-19 15:17] Tennis contracts are CONDITIONAL ON THEIR OWN EVENT
     OCCURRING: rules_primary reads "...wins the match AFTER A BALL HAS BEEN
     PLAYED". A match that never starts resolves to a fair price, not to NO.
202. [2026-08-19 15:17] THE VERTICAL CONTRADICTS ITSELF ON WITHDRAWAL. A
     player who withdraws from a TOURNAMENT resolves that leg a clean No
     (KXATP verbatim); a player who does not start a MATCH sends the contract
     to Fair Market Price. Same absence, two regimes, chosen by contract scope.
203. [2026-08-19 15:17] Settlement authority varies BY SCOPE inside one
     vertical: tournament field = Fox Sports + ESPN + ATP; match/set/games =
     ATP alone; player-to-compete = ESPN + ATP.
204. [2026-08-19 15:17] Postponement FLOATS the close rather than voiding:
     "the market will remain open and close after the rescheduled match has
     finished (within two weeks)". That is why close_time sits 14 days after a
     same-day match — further confirmation that close_time is a backstop and
     occurrence_datetime is the real event time.
205. [2026-08-19 15:17] Tennis nests scope THREE levels — match -> set -> game
     (KXATPSETWINNER, KXATPS1GWINNER...S5GWINNER) — one deeper than soccer's
     halves.
206. [2026-08-19 15:17] Games ladders use .5 strikes (16.5/21.5/26.5) so no
     match can land ON a strike: the tie problem is DESIGNED OUT rather than
     ruled on, unlike KXNFLGAME's fractional payout.
207. [2026-08-19 15:17] TRAP: KXATPRETIRE is CAREER retirement ("Djokovic
     announces his retirement from the ATP before 2027"), NOT mid-match
     retirement. It belongs with Corporate CEO Departure, not with the match
     family. Assuming from the ticker would have been wrong.
208. [2026-08-19 15:17] Leg OI does not track price: in KXATP-26USO, Jodar at
     0.06/0.07 carries 289,203 OI — MORE than Alcaraz (268,260 at 0.18/0.19)
     and Sinner (244,733 at 0.29/0.30). Depth is no guide to where the book
     puts probability.
209. [2026-08-19 15:17] Cross-market arithmetic: Alcaraz is 0.60/0.61 to
     COMPETE at the US Open (KXATPCOMPETE-26USOALC) while priced 0.18/0.19 to
     WIN it (KXATP-26USO) — an implied conditional of roughly 31c.
210. [2026-08-19 15:17] TRAP (mine, caught in verification): the /markets
     payload has NO `open_interest`, `volume_24h` or `volume` keys — only the
     STRING `_fp` variants open_interest_fp / volume_24h_fp / volume_fp.
     Reading the plain names returns 0 silently and made all 73 tennis series
     look like zero OI. The repo itself is correct and uses `_fp` throughout;
     this bites ad-hoc scripts and subagents.
211. [2026-08-19] BUG FIXED (knowledge_graph): tennis notes carried the shared
     `sports` tag, so "Alcaraz to win the US Open mens singles" lost on token
     overlap and routed to Market: NBA Season Wins Ladder. Added a `tennis`
     domain family (parent `sports`), matching the college and motorsport
     pattern. 14/14 routing and isolation checks pass.
212. [2026-08-19] TRAP: find_momentum defaults to categories ['Elections'].
     A --series-match for a sports ticker silently scans 0 series unless
     --category Sports is passed.
213. [2026-08-19] TRAP: KXGOLFTENNISMAJORS is a CROSS-SPORT series and is a
     false positive for BOTH a golf and a tennis substring filter.
214. [2026-08-19] MAJOR: `result` HAS THREE VALUES, NOT TWO. The settled feed
     returns `scalar` alongside `yes`/`no`, and it marks exactly the Fair
     Market Price branch. This makes the tennis abandonment rate MEASURABLE:
     KXATPMATCH 35 of 944 events = 3.7%, KXWTAMATCH 38 of 956 = 4.0%.
     KXATPGTOTAL 117 scalar legs, KXATPSETWINNER 106.
215. [2026-08-19] Every scalar PAIR sums to exactly $1.00. Across all 35 ATP
     events the two legs' `settlement_value_dollars` summed to 1.00 every time
     (0.20/0.80, 0.34/0.66, 0.44/0.56, and one dead-heat 0.50/0.50). So the
     exchange's "sole discretion" produces a coherent, arbitrage-free split.
     The RULE for choosing the split is still unverified; observed values sit
     near the last traded price. Field is `settlement_value_dollars`, NOT
     `settlement_value` (which is absent).
216. [2026-08-19] BUG FIXED (agent/history.py): `group_settled` folded every
     non-`yes` result into `losers`, so a Fair Market Price settlement was
     silently counted as a loss and an abandoned match looked like one nobody
     won. Added `SettledEvent.voided`, `.abandoned`, and `void_rate()`, wired
     into `summarise()`. Verified live: 909 decided + 35 abandoned = 944.
217. [2026-08-19] SELF-CORRECTION: the tennis notes originally stated the
     abandonment rate was NOT backfillable from Kalshi "because a walkover
     produces an FMP settlement rather than a clean YES/NO result". That was
     wrong — the feed reports it as `scalar`. Both notes corrected with the
     measured rates.
218. [2026-08-19] Board survey by CATEGORY found the largest unbuilt block on
     the exchange: ENTERTAINMENT, 2,536 series, ZERO vault coverage. Composition
     (substring counts): SONG 267 · ALBUM 217 · SPOTIFY 181 · OSCAR 89 ·
     AWARD 65 · BILLBOARD 55 · TV 52 · GRAMMY 37 · FILM 36 · SHOW 35 ·
     MOVIE 31 · EMMY 32. Also unbuilt: World 149, Health 98, Transportation 44.
     Politics has 2,196 series and 111+ notes but NO hub note.
219. [2026-08-19] STRUCTURAL GAP CLOSED: 119 political notes existed with NO
     hub, so the §2 rotation query reported the vault's largest layer as
     unbuilt. Wrote [[Vertical: US Politics and Governance]].
220. [2026-08-19] The politics LAYER and the politics BOARD do not match. All
     119 notes are elections (3 Race, 50 State, 35 County, 16 Polling, 10
     District, 4 Pattern, 1 Mechanics); the live category is majority
     GOVERNANCE. Built the first two governance archetypes.
221. [2026-08-19] KXTRUMPPARDONS-29JAN21: 52 legs, ME=False, genuine
     independent_basket, ask-sum 1660.7c with premium correctly withheld.
     Settles on WHITE HOUSE + NEW YORK TIMES — the acting body plus a media
     desk, the Corporate Events family, not the election certification family.
     rules_secondary is EMPTY, so pardon-vs-commutation edge cases are
     unverified. Bundles three legally distinct instruments (pardon,
     commutation, reprieve) as equivalent.
222. [2026-08-19] KXELECTIONBILL: 5-leg RISING date ladder (Before Sep 1 2026
     0.5c -> Nov 1 5.5c -> Jan 1 2027 8.7c), 806,400 OI on 16,239 daily
     volume. Settles on the LIBRARY OF CONGRESS — a settlement authority the
     vault had not recorded: not a certifier, not a media desk, not a
     regulator acting, but the STATUTORY RECORD itself.
223. [2026-08-19] My own structural guard caught the retrofit:
     test_every_hub_links_at_least_two_archetypes failed the new politics hub
     because the election layer has no `Market:` notes at all. Fixed by
     building the two governance archetypes rather than weakening the test.

## 2026-08-19 — Golf vertical

224. [2026-08-19] Golf cluster complete: hub + 4 archetypes (Tournament
     Outright Winner Field, Round Leader Field, Finishing Position Basket,
     Career Major Futures). 120 series, 99.2% series coverage / 100% of 3,100
     open legs. OI 13,349,820, 24h volume 6,186,332. 48 live / 72 dormant.
     No series approached MAX_MARKET_PAGES — nothing is a floor.
225. [2026-08-19] 53 SUBSTRING FALSE POSITIVES excluded from golf, the worst
     ratio yet: 43 soccer (the entire 15-series US **Open Cup** family
     KXUSOPENCUP*, plus KXSCOCUPGAME, KXFACUPGAME, KXCHLLDPGAME), 5 basketball,
     3 tennis (KXATPGAME/KXATPGAMESPREAD/KXATPGAMETOTAL), 2 esports. The
     inverse trap also exists: KXLPGA* IS golf and matches "PGA".
226. [2026-08-19] TRAP: 3 golf series carry NO golf token at all and were
     recoverable only from the series `tags` field —
     KXGENESISINVITATIONAL, KXPHOENIXOPEN, KXPRESCUP. Ticker grammar alone
     silently loses them.
227. [2026-08-19] BUG FIXED (momentum_filter): the quoteless guard used
     `max(bids) < _MIN_LIVE_BID_CENTS` where the constant is 5.0.
     KXLPGAR3LEAD-CPKWO26 is a placeholder book — 158 legs asking 71-74c with
     only FOUR legs bid, all at EXACTLY 5.0c — so it sat one tick outside a
     strict comparison and published `premium_cents = +11,245`. Changed to
     `<=`. Verified live: ask_sum 11,345c now returns premium=None with the
     quoteless note.
     BREADTH would have been the WRONG fix: KXNCAAFAPRANK-26W12R1 is a genuine
     partition with one bid leg of thirteen — but it bids 96c. The LEVEL of
     the best bid separates a real field from a placeholder, not the count.
228. [2026-08-19] SCALAR CONFIRMED IN A SECOND VERTICAL, with a DOCUMENTED
     rule this time. Golf round-leader ties settle `scalar` under a stated
     $1/N payout: "Yes positions will pay $1/N (rounded down to the nearest
     cent), where N is the number of tied participants". Observed
     settlement_value_dollars 0.3300 (3-way), 0.2500 (4-way), 0.2000 (5-way).
     So `scalar` spans BOTH the tennis case (exchange discretion, no formula)
     and the golf case (a published formula). Ties are common: 10 of 36
     sampled leader events.
229. [2026-08-19] Golf WITHDRAWAL is written AND enforced, and it splits by
     market class: "Tournament Winner and End of Round Leader markets will
     resolve to No / Finishing Position, Make the Cut, Head-to-Head, and
     3-Ball markets will resolve to Fair Market Value." Verified on a real WD:
     winner leg `no` @ 0.0000, Top-20 `scalar` @ 0.4400, make-cut `scalar` @
     0.4600. NOTE three DIFFERENT PHRASINGS of the same rule across sibling
     books on one tournament ("Fair Market Value" / "Fair Market Price").
230. [2026-08-19] THE CUT: make-the-cut markets exist but NO RULE says what a
     missed cut does to an outright-winner position. Empirically it settles
     No: at KXPGATOUR-WYC26 (153 legs) the 66 missed-cut legs closed ~34h
     BEFORE the 80 survivors — one event, two close times.
231. [2026-08-19] Golf 72-hole WINNER contracts have NO TIE CLAUSE AT ALL,
     though round-leader books do. "playoff" appears in 4 of 3,100 legs.
232. [2026-08-19] WEATHER SILENCE, worse than motorsport's: zero occurrences
     of suspend/weather/delay/postpone/shorten/abandon/darkness/lightning/
     "Monday finish"/36-hole across all 3,100 open golf legs. A
     storm-shortened tournament has no stated treatment anywhere.
233. [2026-08-19] Golf settlement runs THREE regimes: tour-only
     (KXPGAR1LEAD -> pgatour.com alone), tour+media (KXPGATOUR -> Fox, ESPN,
     pgatour.com), and MEDIA-ONLY WITH NO TOUR (KXSCOTTIESLAM -> ESPN, AP,
     Reuters, NYT, WSJ; KXPGAMAJORWIN -> ESPN alone).
234. [2026-08-19] FIELD AVAILABILITY (corrects earlier assumptions):
     `occurrence_datetime`, `settlement_value_dollars` and `settlement_ts`
     exist ONLY on get_market() — absent from both /markets and get_event().
     And occurrence_datetime is UNRELIABLE on golf: KXPGAR1LEAD-BMC26 reports
     it equal to its padded close, and settled KXPGAR1LEAD-ISC26 resolved
     2026-07-09 against a stated occurrence of 2026-07-26.

## 2026-08-19 — Esports + Chess (built as TWO verticals), and three more fixes

235. [2026-08-19] Esports and Chess judged TWO verticals, not one: no shared
     token grammar, no shared settlement authority, no shared clock (a
     116-second match timer vs a 2028 close), no shared structure. Esports:
     108 series, 17 live / 91 dormant, OI 1,392,042, v24 1,316,694, coverage
     38% -> 100%. Chess: 30 series, 9 live / 21 dormant, OI 1,173,486 but only
     44,118 in 24h — 91% of that OI is one long-dated field. Coverage 83% ->
     100%.
236. [2026-08-19] NINTH SETTLEMENT FAMILY: THIRD-PARTY RESULTS AGGREGATORS AND
     COMMUNITY WIKIS. Esports settles on bo3.gg, HLTV, egamersworld, DLTV,
     Sofascore, plus publisher portals — no broadcaster, no governing body.
     THE SOURCE SET CHANGES BETWEEN SUB-BOOKS ON THE SAME MATCH (bo3.gg
     settles the CS2 series and map but not its total-maps leg). Chess splits
     three ways, and notably the WORLD TITLE settles on Fox Sports/ESPN/WSJ
     with FIDE ABSENT.
237. [2026-08-19] Esports forfeit rules are the most explicit yet and use
     `scalar` deliberately: postponed >48h, cancelled before play, or
     forfeited BEFORE play -> fair market price; forfeited AFTER play begins
     -> official result. Measured usage: 239/2,400 KXCS2GAME legs = 10.0%
     (a FLOOR, cursor outstanding) and 96/1,509 KXCS2TOTALMAPS = 6.4%.
     Disconnect, technical pause and map replay are unaddressed everywhere.
     The final clause names "governing body or tournament organizer" — an
     authority that appears in NO settlement_sources list.
238. [2026-08-19] CHESS HAS NO DRAW MARKET AT ALL. Every market at every
     status across all 30 tickers (2,749 markets, no cap hit) contains ZERO
     draw legs. Kalshi avoids chess's modal outcome by NEVER LISTING the
     market: KXCHESSGAME, KXCHESSMATCH, KXSPEEDCHESS, KXFIDECANDIDATES and
     KXFIDECHESSCHAMPION all have 0 markets ever created. That is a FOURTH
     draw treatment beside combat sports' three and soccer's 3-leg field:
     omission.
239. [2026-08-19] Kalshi lists esports map 1 and map 2 but essentially NEVER
     map 3 (2 legs in a 2,400-leg window) — so the decider that 41% of Bo3
     series reach has no book, and the totals ladder is its only tradeable
     expression. Measured: CS2 Bo3 over 2.5 maps 41.2% (573/1,391), LoL Bo3
     39.5% (193/488), LoL Bo5 over 3.5 46.8% (36/77).
240. [2026-08-19] BUG FIXED (find_momentum + 5 more sites): the API sends
     `"series": null` for an empty category — verified live on
     category="Culture" — and a `.get(key, [])` DEFAULT ONLY FIRES WHEN THE
     KEY IS ABSENT, not when its value is null. So `for s in data.get(
     "series", [])` raised TypeError and killed the WHOLE multi-category
     sweep, not just that category. Fixed with `or []` at 8 sites across
     find_momentum.py, agent/history.py, agent/market_lookup.py,
     fetch_political_markets.py and news_momentum.py. Verified: the sweep now
     survives a null category.
241. [2026-08-19] SIXTH STRUCTURE ADDED — FIXED-CARDINALITY BASKET. An
     ME=False event where exactly K legs resolve yes by construction:
     KXCHESSFIDERATINGTOP-26OCTWOMENT10 lists 20 players for "Top 10 Rated"
     and asks 1003c / bids 920c. The legs are CONSTRAINED, so the old advice
     ("the ask-sum has NO meaning, read each leg on its own") was wrong — the
     ask-sum IS readable as K x 100 + vig.
     K IS BRACKETED, NOT ROUNDED: KXF1TOP10 asked 1109c earlier today, which
     rounds to 11 when the truth is 10. Since the basket cannot be bought
     below K x 100 nor sold above it, the two sides bracket K. Live results:
     chess 20 legs -> exactly 10; F1 22 legs -> exactly 10; KXRAIN (20 real
     cities) correctly keeps the plain basket note.
242. [2026-08-19] Classifier disagreements reported by the esports agent and
     NOT yet fixed: (a) KXCS2-BOP26 printed +404c on a 16-leg dormant book;
     (b) two KXCS2MAP events with identical 156c ask-sums got opposite
     premium treatment; (c) KXCS2TOTALMAPS classifies standalone_binary while
     KXLOLTOTALMAPS Bo5 classifies threshold_ladder on identical economics,
     purely because a Bo3 has one interior threshold. (c) in particular is a
     real labelling inconsistency worth a follow-up.

## 2026-08-19 — Music Charts vertical

243. [2026-08-19] Music Charts cluster complete: hub + 4 archetypes (Chart Rank
     Field, Count Threshold Ladder, Release and Role Announcement, Weeks at
     Number One Ratchet). 840 series in scope — far more than the substring
     counts suggested. Coverage 85.3% -> 99.6% (final residue 3 dormant
     zero-OI series). OI 4,161,738, v24 294,400, 4,408 open markets, 100 live
     / 740 dormant (88%). No series hit MAX_MARKET_PAGES.
244. [2026-08-19] TENTH SETTLEMENT FAMILY: THE PLATFORM OPERATOR SELF-
     PUBLISHING A METRIC ABOUT ITS OWN PRODUCT. KXTOPARTISTUSA settles on
     newsroom.spotify.com; KXYTVIEWSHIGH/KXYTTOPVIDEO2D on charts.youtube.com,
     with rules_secondary instructing a UI LOOKUP ("searching for the artist
     and selecting 'Global' as the location"). No publication calendar, no
     archive, no correction policy — and the measured party controls the
     number. Distinct from Billboard (media desk) and Luminate (specialist
     index provider), which stack as TWO SEQUENTIAL authorities in one chain.
245. [2026-08-19] TRADING CLOSES BEFORE THE CHART PUBLISHES. KXTOPSONG-26AUG29
     carries FOUR distinct dates: close 2026-08-24T03:59Z, occurrence
     (publication) 2026-08-25T14:00Z, issue "Week of Aug 29", expiration
     2026-09-12T14:00Z. The Billboard ISSUE is the reference, not the chart
     date, and the tracking week is named only on the ladder side.
246. [2026-08-19] NO CHART-REVISION, TIE, OR NON-PUBLICATION CLAUSE ANYWHERE.
     Regex over rules_primary + rules_secondary across all 4,408 open music
     markets returned ZERO hits for revision/restate/correct/tie/amend/
     not-published. Charts do get corrected; this book defaults to exchange
     discretion through a GAP rather than a rule — unlike tennis and golf,
     where the discretionary branch is at least written down.
247. [2026-08-19] "#1" is THREE different structures and the discriminator is
     whether the event is one chart week or a period: KXTOPSONG-26AUG29 = 25-leg
     ME=True field (ask-sum 124c); KX1ALBUM-26DEC = 103 legs ME=FALSE
     (ask-sum 1561c) because many artists can each hold #1 across a year;
     KX1SONGJUSTINBIEBER-DEC2726 = a 1-leg binary at 0.06/0.09 on 24,159 OI.
248. [2026-08-19] The ratchet is SCOPED to one run: KXTOPALBUMRECORDSWAG
     resolves on "more than 9 CONSECUTIVE weeks" and closes when the streak
     ends — "This market specifically encompasses the FIRST streak". Its
     sibling KXWEEKSNUM1 counts TOTAL weeks in a year and uses
     `greater_or_equal` rather than `greater` — same family, different
     accumulator, and a one-week reading difference.
249. [2026-08-19] KXARTISTSTREAMSY close_time (2027-01-02T15:00Z) sits INSIDE
     the stated publication window for its own settlement data ("may be
     published up to approximately 48 hours after the end of the period").
     Luminate additionally disclaims verification: "a neutral provider of
     market metrics which does not endorse, verify or participate in any way".
250. [2026-08-19] BUG FIXED (find_momentum): CATEGORIES listed 7 of the 13
     categories the API serves, so 5,538 series were UNREACHABLE by discovery
     — Entertainment alone is 2,536, the largest block on the exchange. Also
     confirmed "Elections" (1,592) and "Politics" (2,196) are BOTH live and
     are DIFFERENT groupings, not synonyms. "Culture" serves `series: null`
     and is deliberately excluded — it is the exact payload that used to
     crash the sweep before finding 240's fix.
251. [2026-08-19] BUG FIXED (knowledge_graph): "will the album be released
     before December" routed to Market: KPI Production Milestone Ladder — a
     release-date question is shaped exactly like a production-milestone
     question. Added a `music` domain family. Sixth vertical to need one.
252. [2026-08-19] KALSHI-SIDE DATA DEFECT: KXROLEATEVENTCOACHELLA's
     settlement_sources contains UNRESOLVED TEMPLATE TEXT as source names —
     "official account of <person>", "The Source Agencies are", "in
     hierarchical order", and one name starting with a private-use Unicode
     codepoint. Any code treating settlement_sources[i]["name"] as an
     authority ingests three non-sources.
253. [2026-08-19] BUG FIXED (kalshi_client): retry backoff had NO JITTER, so
     every worker throttled in the same instant waited the SAME interval and
     they all returned together — recreating the burst that caused the 429.
     A parallel 6-worker sweep still lost 7 requests after all retries, and
     those same 7 re-run SERIALLY succeeded immediately, which is the
     signature of synchronised retry rather than genuine rate exhaustion.
     Added full jitter (BACKOFF_JITTER = 0.5) and raised MAX_RETRIES 4 -> 5.
254. [2026-08-19] Category audit (live): 13 categories serve series —
     Sports 3,454 · Entertainment 2,536 · Politics 2,196 · Elections 1,592 ·
     Financials 991 · Economics 741 · Companies 515 · Science and Technology
     381 · Climate and Weather 354 · Crypto 273 · World 149 · Health 98 ·
     Transportation 44. "Culture" serves `series: null`.

## 2026-08-19 — Awards and Screen vertical (Entertainment block complete)

255. [2026-08-19] Awards and Screen cluster complete: hub + 4 archetypes
     (Award Winner Field, Award Nomination Field, Critic Score Ladder,
     Casting Field). 1,225 series in scope, coverage 67.5% -> 99.2%. OI
     10,921,008, v24 648,794, 2,287 open legs, 136 live / 1,079 dormant (88%).
     No series hit MAX_MARKET_PAGES. With music (840) this completes the
     2,536-series Entertainment block.
256. [2026-08-19] SETTLEMENT SUB-FAMILY: PRIVATE VOTING BODY / SECRET BALLOT.
     Awards settle on the body itself as the SINGLE source — Academy of Motion
     Picture Arts and Sciences (30 live series), Academy of Television Arts &
     Sciences (18), Recording Academy (7). Distinct from the college-sports
     human-judgement family: an AP poll defends a PUBLISHED, RE-READABLE
     TABLE, whereas an Academy emits an EVENT, NOT AN ARTIFACT — a sealed
     ballot nobody sees, delivered as a name read aloud once. Nothing to
     re-read, nothing to appeal, and no rule written for the failure modes.
257. [2026-08-19] ROTTEN TOMATOES is a genuinely new instrument: a
     CONTINUOUSLY RECOMPUTED public aggregate with a CONTRACT-IMPOSED SNAPSHOT.
     Not an index provider — an index publishes on a schedule; the Tomatometer
     recomputes on every review arrival and the contract reaches in to take a
     still frame. Verbatim: "a Tomatometer score of above 45 on Aug 24, 2026
     at 10:00 AM ET" + "The market will be determined the Monday after wide
     release at 10:00 AM ET." The freeze is a WALL CLOCK, not a publication
     event. It is the CRITICS' ("All Critics") Tomatometer — "audience score"
     has ZERO hits across 2,287 legs.
258. [2026-08-19] TIES: three incompatible rules in one vertical and NONE of
     them on an award field. KXRTCOMPARE — tied movies each resolve Yes;
     KXMOSTWINSEMMYS — "the market will resolve to 50/50"; KXBIGBROTHER —
     "$1 divided by number of winners". The Oscar/Emmy WINNER fields are
     SILENT, yet 71 events ship a literal `-TIE` contract leg (21,594 OI on
     KXOSCARPIC-27-TIE) whose only rule is the template applied to the word
     "Tie". Whether a shared Oscar also pays the co-winners' legs is unstated.
259. [2026-08-19] POSTPONEMENT: zero hits for "postpon"/"reschedul"/"sole
     discretion" across all 2,287 open legs. Rescission appears exactly ONCE,
     on a CBS reality show, not an Academy market. KXOSCARPIC-27's entire
     rules_secondary is "The 99thth Academy Awards are expected to be held in
     March 2027." (sic). Kalshi wrote seven clauses for Big Brother and none
     for the Oscars.
260. [2026-08-19] BOX OFFICE MARKETS DO NOT EXIST. A sweep of all 13,254
     series in every category returns only KXGGBOXOFFICE and KXGGBOFILM —
     Golden Globe AWARD CATEGORIES, not dollar ladders. My dispatch brief's
     substring count was a false positive; the agent verified and corrected
     it. Nearest real screen-quantity ladder is KXNETFLIXTOPVIEWSMOVIE
     (view counts, settled via FlixPatrol/Luminate).
261. [2026-08-19] KALSHI DATA ERROR ON LIVE MONEY: KXROLEINPRODUCTION* and
     KXPERFORMROLE* — 283,202 combined OI, including KXROLEINPRODUCTIONDOOMSDAY
     at 256,975 OI — list settlement_sources = "San Francisco Unified School
     District" (sfusd.edu). KXACTOR* settle on a boilerplate POLITICAL news
     panel (Fox News, MSNBC, WSJ, Semafor). Award source lists also contain
     unresolved template garbage ("official account of ", "in hierarchical
     order", a private-use Unicode codepoint) — the same defect the music
     agent found on Coachella.
262. [2026-08-19] CALLER HAZARD: get_markets(event_ticker=...) WITHOUT
     status=open returns finalized legs quoting yes_ask 1.0000 —
     KXEMMYDSACTR-26SEP14's ask-sum goes 124.0c -> 624.0c. _all_open_markets
     filters correctly; ad-hoc calls do not.
263. [2026-08-19] Exchange-wide /markets?status=open is UNUSABLE for category
     work: >73,000 legs saturated by KXMVECRO parlay collections, with ZERO
     Entertainment legs in the first 73 pages. Per-series enumeration required.
264. [2026-08-19] BUG FIXED (knowledge_graph): "Emmy nomination for outstanding
     drama SERIES" routed to Vertical: NHL Pro Hockey — `series` is a generic
     sports marker. Added a `screen` domain family. Also added Grammy aliases
     to the award-winner note: "Grammy award winner for ALBUM of the year" is
     genuinely bi-domain and was going to the music cluster. SEVENTH vertical
     to need its own domain family — every new one does.
265. [2026-08-19] Agent scratch cleanup: removed 7 state/_*.json working files
     left by the awards and music agents; added `state/_*` to .gitignore.
     Verified each was scratch (not scan output) before deleting.

## 2026-08-19 — §2C historical-analog backfill (5 notes)

266. [2026-08-19] BACKFILLED Esports Series Match Winner: 9.9% of CS2 series
     matches never reach normal settlement (119 of 1,200 events settled
     `scalar`). That is ~2.5x the tennis abandonment rate (ATP 3.7%, WTA 4.0%)
     — a scheduled esports fixture is far likelier not to be played as
     scheduled than a tour tennis match. FLOOR: 12-page cap, cursor
     outstanding.
267. [2026-08-19] BACKFILLED Esports Map Winner: 8.2% of CS2 MAP events settle
     at fair value (99 of 1,200) — LESS than the 9.9% of their parent series.
     Consistent with the rule split: a match cancelled before play voids every
     map, but one forfeited AFTER play begins settles completed maps on the
     official result while the series question goes to fair value.
268. [2026-08-19] BACKFILLED Music Chart Rank Field with a structural contrast
     that changes how the archetype is priced: KXTOPSONG (Hot 100) had only
     TWO distinct winners across 10 decided weeks, one song holding #1 for 8
     of 10; KXTOPALBUM (Billboard 200) had EIGHT distinct winners across 9.
     The song chart is an INCUMBENCY market, the album chart a RELEASE
     CALENDAR. Pricing them with one model is the error. This is also the
     empirical basis for the Weeks at Number One ratchet, which only makes
     sense on the side that persists. Zero scalar settlements on either —
     charts publish, even though no revision clause exists.
269. [2026-08-19] BACKFILLED Crypto Daily Price Ladder: across 13 settled days
     the strike ladder BRACKETED the outcome every time, settling at the 52nd
     percentile of listed strikes (median 98 winning rungs of 188; min 33%,
     max 74%). The 54.3% leg-level yes-rate is NOT the useful number — on a
     cumulative ladder every rung below the outcome pays, so it only says the
     outcome lands mid-range. Bracketing is the real statistic.
270. [2026-08-19] BACKFILLED Equity Index Session Hour Ladder: the ladder
     FAILED TO BRACKET the index once in 41 settled sessions (40/41 = 97.6%) —
     one event finished with ZERO winning legs, i.e. the index closed outside
     every listed strike. On a book emitting 7 events a day, a 1-in-41 failure
     is not a tail to ignore. void_rate 0/41: the index always prints, so the
     failure mode is a too-narrow strike range, not a missing outcome.
271. [2026-08-19] §2C progress: notes reading "None recorded" 82 -> 77.
     Method that works: prefer archetypes that resolve MANY times (daily
     ladders, weekly charts, per-match books) and report the statistic that is
     actually informative for the shape — bracketing for ladders, distinct-
     winner counts for recurring fields, void_rate for anything with an
     abandonment branch — rather than a leg-level yes-rate, which is nearly
     meaningless on a cumulative ladder.

## 2026-08-19 — Companies vertical

272. [2026-08-19] Companies cluster complete: hub + 4 archetypes (Alt-Data
     Panel Ladder, Layoff Announcement Basket, Announcement Binary, Legal
     Action Binary). 515 series, coverage 93.4% -> 100%. Category OI 1,179,084,
     v24 62,524, 316 live / 199 dormant (38.6% dormant — far healthier than
     the ~88% typical of recent verticals).
273. [2026-08-19] HONEST SCOPING: 318 of 515 (61.7%) were ALREADY COVERED,
     holding 71.2% of the OI — 291 by Company KPI Markets, 25 by Corporate
     Events, 2 by Stock Indices. Only 191 series (37.1%) were genuinely new.
     The KPI overlap is 291, not the 31 recorded earlier: the `KPIs` TAG is
     the family marker, confirmed again.
274. [2026-08-19] ELEVENTH SETTLEMENT FAMILY: A COMMERCIAL ALTERNATIVE-DATA
     VENDOR. 63 series settle on CARBON ARC (57 live, 276,286 OI — 81.2% of
     all new-series OI, and 90.5% live). It carries an EXPLICIT FIRST-PRINT
     RULE on 446/446 markets: "determination will resolve on the first value
     reported by Carbon Arc. Corrections or revisions made after the market
     has been settled will not affect the outcome."
275. [2026-08-19] OPPOSITE RESTATEMENT REGIMES ON THE SAME COMPANIES: Carbon
     Arc states first-print-wins explicitly; the Fiscal.ai KPI family has NO
     restatement clause across 2,554 markets (finding 192). Same issuers, same
     exchange, contradictory treatment of revisions.
276. [2026-08-19] PACER (federal court records) settles the Legal Action
     family — 16 series. KXAPPLEUS closes in 2030 and has
     `can_close_early: true` with `early_close_condition: null` — it asserts
     early close and states no trigger.
277. [2026-08-19] STRIKE UNITS ARE INCONSISTENT INSIDE ONE FAMILY: 15 Carbon
     Arc POS series quote PERCENT (KXDRPEPPERPOS T-15...T1) while 48 quote
     INDEX POINTS (KXAMZNCC T102...T112) — and all 63 carry identical
     "100 = flat YoY" boilerplate. Reading a percent ladder as an index ladder
     is a 100x error.
278. [2026-08-19] VERIFIED ABSENT (searched all 13,255 series): NO
     private-company valuation or funding-round market exists anywhere on
     Kalshi — the 32 regex hits are government appropriations, political
     fundraising, or puns (KXMARMADSEEDROUND is March Madness). NO
     company-specific bankruptcy contract either; KXCH11/KXBANKRUPTCY are
     Economics AGGREGATE FILING COUNTS. No recall, breach or strike markets.
279. [2026-08-19] Zero of 481 live new-series markets contain any
     NON-OCCURRENCE clause, and 15 have a completely empty rules_secondary.
     KXAAPLPRICEFOLD ("the first price announced ... at least $2200",
     32,532 OI) has NO RULEBOOK REFERENT if no foldable is ever priced.
280. [2026-08-19] `get_series_list` CATEGORY IS UNSTABLE: of 515 series
     returned for category="Companies", only 175 carry `category: "Companies"`
     in their own payload — 308 say `Financials`. Consistent with finding 194.
     Never key logic on a series' self-reported category.
281. [2026-08-19] More garbage settlement sources on live money: 28 series name
     an authority literally called `person`, 26 name `company's official
     website`, 4 name `subsidiaries of ` (nothing after), all pointing at
     kalshi.com. KXSUPERBOWLAD is settled by `the Governing League` at
     nfl.com; KXAAPLPRICEFOLD points `The Washington Post` at wsj.com.
282. [2026-08-19] BUG FIXED (knowledge_graph) — a regression I introduced
     earlier today: [[Market: Politics Executive Action Basket]] (presidential
     pardons) captured "chief EXECUTIVE steps down departure" from
     [[Market: Corporate CEO Departure]] on the shared word. Added a `company`
     domain family AND the governance vocabulary politics never had
     (pardon/impeachment/tariff/scotus/legislation). Both now route correctly.
283. [2026-08-19] Retrieval note: two same-domain notes can tie EXACTLY on
     IDF score, and the tiebreak is then reverse-alphabetical by title —
     "Corporate Merger" beat "Company Layoff" on a layoff headline for that
     reason alone. Fixed by grounding the layoff note in its VERIFIED legs
     (Oracle 12,277 OI, Amazon 2,476, Netflix 2,123, Tesla) rather than by
     adding a bare alias, so the alias is backed by content.

## 2026-08-19 - Transport / Public Health / Sovereign Risk (THREE verticals)

284. [2026-08-19] Built THREE verticals from World 149 + Health 98 +
     Transportation 44, split on settlement authority, clock and shape rather
     than Kalshi's labels: Transport and Logistics (operator or commercial
     tracker; operational-day clock; greater_or_equal count ladder), Global
     Public Health (agency reading its own surveillance instrument;
     publication-week clock; greater ladder or declaration binary), Sovereign
     Risk (the deciding body itself; NO CLOCK AT ALL - a calendar deadline
     with no scheduled resolution event; standalone binary).
     Coverage: World 22.8% -> 100%, Health 62.2% -> 98.0%, Transport
     84.1% -> 100%.
285. [2026-08-19] THESE BOARDS ARE EFFECTIVELY DEFUNCT - the most important
     fact about them. 290 of 291 series dormant (99.66%), and 288 of 291
     return ZERO market rows at ANY status (open/closed/settled/unopened).
     Kalshi has purged the contract rows and kept only event shells.
     INDEPENDENTLY VERIFIED: 0 of 42 sampled series carry an open market. The
     single live book, KXFLYCANCJFK-JFK-ALL-26OCT21-T50, shows 3,023,897 OI
     against 0.00 24h volume and 0.0000 liquidity - a stale position, not a
     market. All three hubs record this prominently rather than reading as
     tradeable.
286. [2026-08-19] TWELFTH SETTLEMENT FAMILY: THE DECIDING PARTY AS ITS OWN
     REPORTER. 17 series name a self-interested actor as SOLE source - KXUAW
     (will the UAW strike) settles on the UAW; KXWAYMOLEAVELA on Waymo;
     KXMAERSK on Maersk; BOEINGCEOCHANGE on Boeing; KXARGSTRIKE on Argentina's
     CGT; KXTURKEU on the EU; KXCPTPP on the CPTPP Commission; KXVONCUK on UK
     Parliament. Distinct from family #5 (no regulator listed) and #10 (no
     metric - a discretionary ACT). Sharpened by the universal boilerplate
     "Persons who are employed by any of the Source Agencies are not permitted
     to trade on the Contract", which bars every UAW employee from the market
     on their own union's strike while leaving the UAW as sole authority.
     Control case in the same cluster: KXBOEING737MAX9 settles on the FAA.
287. [2026-08-19] NO UN, NO TREATY COURT, NO TRIBUNAL appears anywhere across
     291 series. The wire-desk answer to "who settles a geopolitical market"
     is Bloomberg alone (8 Argentina series) or a 14-23 name US-centric media
     panel.
288. [2026-08-19] VERIFIED ABSENT: zero international-election series exist in
     the World category - a regex over all 149 titles plus event titles found
     none. The only ballot-shaped books are a papal conclave and one UK
     confidence vote. "World" is a legacy dumping ground, not a vertical:
     foreign macro 14, US macro 16, weather 14, music 13, social-post counting
     12, NYC politics 7, COVID-era local closures 12, one index membership
     basket. The agent named the misfiling instead of manufacturing hubs.
289. [2026-08-19] 33% of the 291 are DUPLICATES - 96 series are the same
     product listed twice under a legacy ticker and its KX twin (World 43,
     Health 37, Transportation 16).
290. [2026-08-19] REVISION POLICY now differs IN KIND across four verticals:
     Economics settles on the ADVANCE ESTIMATE and ignores revisions; Carbon
     Arc states FIRST PRINT WINS explicitly; Transport writes an explicit
     revision cutoff; Public Health writes NOTHING about revisions and instead
     extends the clock - "In the case of a delay in data, the market's latest
     Expiration Date will be one week after the scheduled release." A delay
     clause is not a revision clause.
291. [2026-08-19] status=finalized IS REJECTED by /markets (HTTP 400);
     open/closed/settled/unopened are accepted. VERIFIED, and our
     agent/history.fetch_settled correctly uses `settled` - no repo bug.
292. [2026-08-19] IMPORTANT CLARIFICATION for base-rate work: status=settled
     returns markets whose market.status is `finalized` and which carry a real
     `result` (yes/no/scalar). status=closed returns markets whose `result` is
     the EMPTY STRING - trading stopped, outcome not yet determined. They are
     NOT interchangeable, and only settled rows can support a base rate.
     KXCDCSTATFLU has 0 settled and 9 closed - its contracts closed WITHOUT
     EVER RESOLVING, which is what a purged board looks like from outside.
     This check confirmed every 2026-08-19 backfill is sound.
293. [2026-08-19] /events?series_ticker=KXCDCSTATFLU returns 0 events while
     /markets?series_ticker= returns 9 markets pointing at event
     KXCDCSTATFLU-26, which get_event() then resolves fine. The events listing
     misses an event its own market rows reference.
294. [2026-08-19] settlement_sources is built by SPLITTING A PROSE SENTENCE ON
     COMMAS and storing the fragments as source NAMES. Evidence: `the U` (from
     "the U.S. ..."), `Prevention` (tail of "Centers for Disease Control and
     Prevention"), four spellings of CDC and three of FDA in one category.
     KXCDCSTATFLU's SERIES names `the Center for Disease Control` AND `the
     White House`; its EVENT names `CDC` at cdc.gov/fluview - series and event
     contradict each other on the same product. One event source is literally
     named `Primary Source Agency`, a template placeholder.
     NOT garbage, contrary to earlier suspicion: `San Francisco Unified School
     District` IS the correct authority for KXSCHLSF ("SF school closed?") -
     it is only wrong on the KXROLEINPRODUCTION family.
295. [2026-08-19] COST WARNING: an exchange-wide /markets?status=open pull hits
     200,000+ markets, of which 198,664 are KXMVECROSSCATEGORY parlay combos.
     Never enumerate exchange-wide; go per series.
296. [2026-08-19] BUG FIXED (knowledge_graph): added `transport`, `health` and
     `sovereign` domain families. TWO deliberate omissions, each caught by a
     regression: "who" is NOT a health marker (the WHO and the interrogative
     are the same token, and domain tokens keep stopwords, so it would route
     every "who will win..." headline to public health); and "flight" is NOT a
     transport marker (ambiguous with SPACEflight - it sent "Starship flight
     test 14" to the airport ladder). The same collision recurred through an
     ALIAS carrying the bare token, which had to be reworded too.
297. [2026-08-19] EVERY CATEGORY ON THE BOARD NOW HAS A HUB. 24 -> 27 hubs.

## 2026-08-19 - Politics governance deepening (date-ladder detector fix)

298. [2026-08-19 17:08] STEP ZERO: every category on the board now has a hub,
     so this run is §2C DEEPENING. Verified the governance half of Politics is
     the largest unwritten block: TARIFF 76 series / 13 live / OI 459,564 ·
     SCOTUS 28 / 12 live / OI 220,961 · NOM 23 / 4 live / OI 143,105 (v24
     25,338, the highest) · IMPEACH 16 / 5 live / OI 1,260,952 (the highest OI)
     · APPROV 14 / 3 live / OI 146,663 · SHUTDOWN 6 / 1 live · CABINET 5 / 0.
     TOTAL 38 live series, 178 open markets, ~2.32M OI, ~66k v24.
299. [2026-08-19] METHOD NOTE: single-series sampling nearly killed this
     target. My first probe hit KXTARIFFSPRC, KXTARIFFRATECHN, KX538APPROVEY
     and KXTRUMPNOMS - all DORMANT - and the family looked dead. A full sweep
     showed 38 live series and 2.32M OI. Sample the FAMILY, never a series.
300. [2026-08-19] CRICKET IS DEAD: 7 series, 0 with an open market. Skipped per
     §2C ("never invent a vertical that has no live markets"). RUGBY: 5
     series, 2 live - too small to be worth a hub on its own.
301. [2026-08-19] BUG FIXED (momentum_filter) - the detector bug §2B predicts
     for every new vertical. KXIMPEACH is a genuine RISING DATE LADDER (4 legs
     at 1.0 / 3.8 / 21.0 / 59.0 cents, "Before Sep 1 2026" through "Before Jan
     1 2028", nested by construction) but was classified `independent_basket`,
     whose note tells the reader the ask-sum has NO meaning and each leg
     stands alone - precisely backwards for a cumulative distribution.
     ROOT CAUSE: the ladder ordering was derived only from `floor_strike` and
     the ticker tail. KXIMPEACH's tails are SEP01 / JAN01 / MAR01 / JAN01 -
     month-day fragments with no year, and TWO ARE IDENTICAL (Jan 1 2027 and
     Jan 1 2028). No ticker-based rule can order that. KXSCOTUSN is worse,
     mixing 26OCT / 27 / 27MAY31 / 28 / 29JAN20 in one event.
     FIX: `_subtitle_date_ordinal` reads the date from `yes_sub_title`
     ("Before Sep 1, 2026") as a last resort. Verified live: KXIMPEACH and
     KXSCOTUSN now read threshold_ladder; KXFEDGOVNOM (12 named Fed nominees,
     whose labels are PEOPLE and yield no date) correctly stays
     independent_basket, as does KXRAIN.
302. [2026-08-19] SELF-INFLICTED BUG, caught by the existing suite within one
     run: my first version of that fix defined a second module-level `_MONTHS`
     with LOWERCASE keys, shadowing the original UPPERCASE map at line 184 and
     silently breaking `_strike_value` for EVERY YYMMMDD date strike in the
     repo. Three tests failed immediately, including one comparing None < None.
     Fixed by reusing the existing map. Lesson: grep for the symbol name before
     adding a module-level constant - a shadow parses fine and is wrong.
303. [2026-08-19] KXTARIFFCHECKS carries a TWENTY-TWO NAME media panel
     (NYT, AP, Bloomberg, Reuters, Axios, Politico, Semafor, The Information,
     WSJ, CBS, CNN, Fox, MSNBC, NBC, Guardian, South China Morning Post, CBC,
     ABC, BBC, WaPo, The Verge, ABC News Australia) - the widest recorded in
     this vault, beating Corporate Events' 21. Notably international and
     including a technology outlet.
304. [2026-08-19] THE LIBRARY OF CONGRESS settles impeachment (KXIMPEACH),
     Supreme Court confirmations (KXSCOTUSN) and Fed Board nominations
     (KXFEDGOVNOM) as well as legislation (KXELECTIONBILL). The "statutory
     record" authority is broader than first recorded: it covers the whole
     constitutional-process family, not just bills becoming law.
305. [2026-08-19] BACKFILLED Combat Bout Winner Binary: 7.1% of UFC bouts never
     reach normal settlement (9 of 127 events). Places combat between tennis
     (ATP 3.7%, WTA 4.0%) and CS2 esports (9.9%). Deliberately did NOT report
     per-fighter win rates: across 118 decided bouts nearly every fighter
     appears once, so the top "winner" holds 2% — an artefact, not a tendency.
     For a per-bout market the abandonment rate is the only base rate the
     settled feed can support.
306. [2026-08-19] NEW SHARED MECHANICS NOTE:
     [[Market Mechanics: Scalar Settlement and Abandonment Rates]], companion
     to the settlement-sources note. `scalar` is NOT one rule — four verticals
     give it four meanings: tennis (sole discretion, NO published formula),
     golf round leaders ($1/N, published, observed 0.33/0.25/0.20), golf
     withdrawals (Fair Market Value, and only for SOME market classes),
     esports (an explicit postponed/cancelled/forfeited ladder).
     Measured ordering: CS2 series 9.9% > CS2 map 8.2% > UFC bout 7.1% >
     WTA 4.0% > ATP 3.7% > UFC method 1.7% > scheduled data 0% (charts, daily
     crypto ladder 0/13, index session 0/41). Scheduled recurring instruments
     never abandon because the datum publishes regardless.
     Where discretion is bounded, it is bounded by ARBITRAGE not by rule: all
     35 abandoned ATP pairs summed to exactly $1.00.
     Tagged market-mechanics/resolution/kalshi (NOT `market`), so it stays
     exempt from the hub-reachability guard, and verified not to hijack
     subject headlines.

## 2026-08-19 - Player props, and a correction to my own cardinality guard

307. [2026-08-19 17:20] STEP ZERO: every category has a hub, agents hold the
     politics-governance deepening, so this run took a different residue
     family. PLAYER PROPS is a structural gap - every sports note in the vault
     is TEAM- or EVENT-level and nothing models a contract on one athlete's
     performance, or a season-long stat-leader field drawn across all teams.
     Live and liquid: KXMLBHR 182 mkts / OI 1,110,806 / v24 1,089,755 ·
     KXMLBRBI 214 / 25,322 / 24,126 · KXLEADERMLBHR 32 / 281,651 ·
     KXLEADERMLBRBI 71 / 51,450 · KXLEADERMLBERA 56 / 55,883 ·
     KXNFLSEASONPASSYDS 120 / 46,300. ~1.57M OI, ~1.12M v24. 6 of 17
     candidates live; the rest (KXATPACES, KXPGABIRDIES, KXNHLSAVES,
     KXNFLPASSYDS, KXMLBSTRIKEOUTS, KXMLBPLAYEROTW...) are dormant.
308. [2026-08-19] TRAP: "RBI" as a substring matches KXINDYCARBIGGESTMOVER
     ("...CA-RBI-GGEST..."). The substring problem again, now inside a
     three-letter stat abbreviation - the shortest false positive yet.
309. [2026-08-19] BUG FIXED, AND IT WAS MINE FROM EARLIER TODAY. The
     fixed-cardinality guard (finding 241) keyed ONLY on the bid/ask bracket,
     and that is not evidence. On a GENUINE independent basket the ask-sum IS
     the expected number of legs resolving yes, so it ALWAYS brackets some
     integer. Live false positives it was producing:
       KXMLBHR-26AUG191310SDNYM   35 players "records 1+ home runs"
                                  ask 213c / bid 158c -> claimed "exactly 2"
       KXNFLSEASONPASSYDS-27C4000 30 QBs "records 4000+ passing yards"
                                  ask 1017c / bid 555c -> claimed "6-10"
     Any number of players can homer and any number of quarterbacks can pass
     for 4000 yards. Neither is constrained.
     THE REAL DISCRIMINATOR IS SEMANTIC, NOT NUMERIC: a RANK phrase ("is rated
     TOP 10", "finishes in the TOP 10") means only ten of the listed entrants
     can occupy ten places; a THRESHOLD phrase ("2+", "4000+") means each
     entrant clears the bar independently. `stated_cardinality()` now reads the
     rank phrase from rules_primary, and BOTH signals must agree before any
     constraint is claimed.
310. [2026-08-19] NEW SIGNAL from that fix: when the rules NAME a K but the
     book does not bracket it, that is itself worth reporting rather than
     hiding behind "the ask-sum has no meaning". Of 8 live
     KXCHESSFIDERATINGTOP events, SEVEN bracket their stated K cleanly and ONE
     does not - 26OCTWOMENT10 asks 998.0c against 920.0c of bids for a stated
     TEN-place partition, i.e. the ask side sits BELOW the 1000c floor the
     constraint implies. Added CARDINALITY_MISMATCH_NOTE, which prints the
     stated K, the implied par, and both sides of the book, and claims no
     premium.
311. [2026-08-19] LESSON worth keeping: a numeric coincidence is not a
     structure. The bracket test was necessary and nowhere near sufficient,
     and it took a live board (35 MLB hitters) rather than a synthetic test to
     expose it - my original test used records with no rules text, so the
     semantic signal it should have required was invisible.

## 2026-08-19 - Player Props cluster + Politics governance deepened to 9 archetypes

312. [2026-08-19 17:26] PLAYER PROPS cluster complete: hub [[Vertical: Player
     Props]] + 3 archetypes (Daily Stat Prop, Season Stat Leader Field, Season
     Threshold Basket). The vault's first PERSON-level contracts; every other
     sports note is team- or event-level.
313. [2026-08-19] THE PARTICIPATION LADDER is the whole daily-prop contract.
     KXMLBHR rules_secondary, verbatim: scratched or not in the starting
     lineup -> fair market price; starts but records no plate appearance ->
     fair market price; not in the starting lineup but later enters -> fair
     market price, "PINCH HIT AT BATS WILL NOT COUNT TOWARDS THE MARKET".
     THREE OF FOUR BRANCHES NEVER REACH THE STAT. A player can hit a pinch-hit
     home run and the position still settles at an administrative price. This
     is the FIFTH context for `scalar` and the first keyed on A PERSON rather
     than the event.
314. [2026-08-19] THE VERTICAL CONTRADICTS ITSELF ON NON-APPEARANCE, exactly as
     tennis does on withdrawal: daily prop -> FAIR MARKET PRICE; season leader
     field -> "Participants who do not play any games due to injury,
     suspension, retirement, or other reasons resolve to NO"; season threshold
     basket -> NO CLAUSE AT ALL (13 chars of boilerplate). Same athlete, same
     absence, three answers chosen by contract scope.
315. [2026-08-19] Season leader rules are the richest in the vertical: season
     types fenced (no preseason/postseason/all-star); a TRADED PLAYER'S STATS
     COMBINE ACROSS TEAMS (the contract follows the person, not the roster);
     "League minimum qualification thresholds apply" (decisive for ERA, and
     UNQUANTIFIED); ties pay PROPORTIONALLY; and "statistical corrections are
     only considered if made before the expiration date" - an explicit
     revision cutoff, unlike the daily prop which is silent.
316. [2026-08-19] KXMLBHR turns ~1.0x its open interest daily (v24 1,089,755
     against OI 1,110,806) - the highest turnover ratio recorded in this vault.
317. [2026-08-19] BUG FIXED (knowledge_graph): a note can honestly belong to
     TWO domain families. KXMLBHR is both a player prop and an MLB contract,
     but `_note_domain` returned only the first matching tag, so an MLB
     headline saw the props note as a MISMATCH and demoted it 0.35x - losing
     "will the batter hit a home run tonight" to an AI note that merely shared
     the word "hit". Added `_note_domains` (plural) and matched on ANY family.
318. [2026-08-19] ...and the first version of THAT fix was too permissive: every
     league note also carries a literal `sports` tag, so counting both families
     let any sports headline match any league note and re-broke the NFL/College
     split within one run. Now the generic parent is DROPPED whenever a
     specific league family is present.
319. [2026-08-19] BUG FIXED (knowledge_graph): BARE PREPOSITIONS WERE SCORING AS
     RARE TOKENS. "from" carried idf 4.9 - higher than "player" at 3.65 - so a
     single alias containing it outranked a genuine tennis note on "will the
     player withdraw FROM the tournament". Added from/into/onto/over/under/
     than/that/this/these/those/their/there/been/being/have/has/was/were/are/
     its to STOPWORDS. A preposition must never be evidence.
320. [2026-08-19] RETRIEVAL LESSON, learned twice this lap: an alias is not
     free. Adding "is the player in the starting lineup" and "league leader for
     the season" introduced generic tokens that stole headlines from tennis and
     NBA; "Federal Reserve Board of Governors nominee" introduced bare
     "federal" and stole an AI-legislation headline. Aliases must carry the
     DISTINCTIVE words only.

### Tariff / trade / shutdown (subagent)
321. [2026-08-19] Tariff+shutdown family: 97 series, coverage 48.5% -> 100.0%
     in two passes, 18 live (18.6%). Three archetypes written. My baseline of
     76 TARIFF-token series was exactly right, but 7 trade-policy series carry
     NO tariff token (KXSTOPTRADE, KXTRADEDEALCUBA/PRC, KXCIT301,
     KXDJTVOSTARIFFS, KXTRUMPSCOTUS/VOTE) and account for the whole OI gap;
     shutdown is 14 series, not 6, once GOVSHUT/SHUTLENGTH abbreviations are
     included.
322. [2026-08-19] OPPOSITE RESCISSION CONVENTIONS INSIDE ONE FAMILY. The rate
     ladder: "Only tariffs that are currently active and being collected count
     - announced but not implemented tariffs, paused tariffs, or suspended
     tariffs do not qualify." KXTARIFFSECTOR: "resolves based on the issuance
     of an executive action, INDEPENDENT of the effective date or whether the
     tariffs are subsequently implemented." An announced-then-stayed tariff
     pays YES on one and NO on the other.
323. [2026-08-19] TRAP: THE TARIFF LADDER'S TICKER SUFFIX IS HALF THE STRIKE.
     KXTARIFFRATEPRC-27JAN01-50 is the 100% rung; -25 is 50%, -15 is 30%,
     -10 is 20%, -5 is 10%. Reading the suffix as the percentage is a 2x error.
324. [2026-08-19] The 22-NAME MEDIA PANEL is CONFIRMED at both series and event
     level on KXTARIFFCHECKS, KXCANTARIFFSEFFECT and KXTARIFFAGREE - the widest
     in this vault, beating Corporate Events' 21. The rate ladder instead takes
     a 16-name MIXED panel of press plus Congress and the President, with NO
     USTR, NO CBP and NO Federal Register - despite its own rule turning on
     whether duties are actually being collected.
325. [2026-08-19] SHUTDOWN settles on OMB + OPM only, verbatim: OMB "orders
     heads of the affected agencies to 'execute plans for an orderly
     shutdown'" or OPM posts "Federal Government operations vary by agency".
     Explicitly NOT enough: "A technical lapse in appropriations occurs, but
     OMB directs agencies to continue standard operations." It is a 10:00 ET
     SNAPSHOT with no persistence requirement.
326. [2026-08-19] KXNUMSHUTDOWNS IS ONLY IN category="Elections", never in
     "Politics" - yet its own category field and its event's both read
     "Politics". A Politics-only enumeration silently drops a 10,011-OI
     governance market. Another reason to sweep both groupings.
327. [2026-08-19] KXNUMSHUTDOWNS is an INCOMPLETE PARTITION: legs exist for
     exactly 2/3/4/5 shutdowns and for NOTHING ELSE - no 0, no 1, no 6+. It is
     flagged exclusive_field with a +13.0c premium, and that number has no vig
     interpretation because the partition does not cover the outcome space.
     NOT fixed: no numeric rule can detect missing outcomes, and I have just
     been burned once this session by inferring structure from arithmetic
     (see 309). Documented as a limitation instead.
328. [2026-08-19] Garbage sources, live money: KXNUMSHUTDOWNS names "the
     Statistical Review of World Energy" - a BP energy publication - as the
     settlement authority for a US government-shutdown count (event level is
     correctly OMB/OPM). KXTRADEDEALCUBA carries a source literally named
     "country". Both point at kalshi.com.
329. [2026-08-19] DANGLING CONTRACT REFERENCE: KXNUMSHUTDOWNS rules_secondary
     is only "Link to associated contract: GOVTSHUTLENGTH." and
     KXGOVTSHUTLENGTH returns ZERO markets at any status. The definition it
     defers to is unreadable on the exchange.
330. [2026-08-19] CLOSE PRECEDES MEASUREMENT by exactly 10h01m on the rate
     ladders (close 04:59Z vs occurrence 15:00Z). KXGOVTSHUTDOWN is the
     opposite extreme: close_time == occurrence_datetime exactly, so there is
     ZERO hedging window.
331. [2026-08-19] The date-ladder fix (301) was INDEPENDENTLY CONFIRMED by the
     agent on KXTARIFFBILL and KXTARIFFAGREE - both now classify
     threshold_ladder, and it found no remaining mislabelled "before date D"
     family anywhere in 97 series.

### Judicial / confirmation / impeachment / approval (subagent)
332. [2026-08-19] Judicial family: 168 in-domain series, coverage 36.6% -> 94.0%
     (true in-domain residue 1.2%; 8 of the 10 unclassified are regex false
     positives). Four archetypes written.
333. [2026-08-19] MY OWN SCOPE NUMBERS UNDERSTATED THE FAMILY BY ~780,000 OI.
     KXALITOOUT (394,718) and KXSCOURT (385,670) carry NO `SCOTUS` token. The
     dominant residue grammar is a BARE SURNAME ticker - BARR, COOK, SOHN,
     BRAINARD, CHILDS, JEFFERSON, LIZARRAGA - where the ticker carries a
     person, not a subject.
334. [2026-08-19] THE LIBRARY OF CONGRESS DOCTRINE COVERS ONLY THE
     CONGRESSIONAL HALF. Senate-side contracts (KXSCOTUSN, KXSCOURT,
     KXFEDGOVNOM, KXIMPEACH) settle on the Library of Congress; COURT-side
     contracts (KXSCOTUSCASE, KXSCOTUSCERT, KXSCOTUSRESIGN) settle on
     supremecourt.gov. Impeachment splits the same way - KXIMPEACHCABINET
     settles on house.gov. Authority follows WHO ACTS, not the subject.
335. [2026-08-19] APPROVAL SETTLES ON RCP AND VOTEHUB - not 538, not Gallup,
     and all eight 538APPROVE* tickers are dormant. They are also different
     INSTRUMENTS: KXAPRPOTUS is an RCP point-in-time snapshot into 8 exclusive
     bins (ask-sum 103.0c, a genuine ~3c vig - the only readable vig in the
     vertical), while KXTRUMPAPPROVALBELOW is a VoteHub ONE-TOUCH BARRIER over
     13 months. Neither names a fallback if the aggregator stops publishing.
336. [2026-08-19] "NOMINATED" IS DEFINED IN OPPOSITE WAYS INSIDE ONE SERIES.
     KXFEDGOVNOM-27: "The nomination must be sent by the President and received
     by the United States Senate." KXFEDGOVNOM-29: "Official announcements made
     by the President of a nomination shall satisfy the Payout Criterion, EVEN
     IF THEY ARE NOT YET SENT TO THE SENATE." One announcement resolves one
     event and not the other. The settlement sources track it honestly - the
     announcement ladder adds whitehouse.gov as a second source.
337. [2026-08-19] IMPEACHMENT COLLAPSES ITS STAGES to the House vote:
     "The President must hold the office when an impeachment resolution passes
     against him or her." Senate trial and conviction are OUTSIDE the payout
     criterion. And that stage rule appears on only TWO of KXIMPEACH's FOUR
     legs - the Sep-2026 leg carries a single space and the Mar-2027 leg an
     empty string.
338. [2026-08-19] THE KXSCOTUSN 86c/82c PAIR IS NOT AN ARBITRAGE. I flagged it
     as suspicious when briefing the agent; it verified the crossing condition
     properly. The later leg strictly CONTAINS the earlier, so a cross needs
     bid(earlier) > ask(later): 63 > 82 is FALSE. The books are 63/86 and 3/82
     - 23c and 79c wide - on 1,790 and 415 OI with 20 and 64 contracts of ask
     size. The 203c ask-sum is stacked asks on near-empty rungs, not vig.
339. [2026-08-19] KXALITOOUT LISTS "SAMUEL ALITO" - A NAMED LIVING PERSON - AS
     A SETTLEMENT SOURCE, alongside the Court and six media outlets: a sitting
     justice as the authority on his own retirement. It also hands the exchange
     discretion on death ("may resolve to the last fair price as determined in
     the sole discretion of the Exchange"). Separately
     KXCALLIMPEACHRCONGRESS-26 lists "The Washington Post" with url wsj.com.
340. [2026-08-19] SYSTEMATICALLY BAD CLOCKS in this family: KXIMPEACH carries
     expected_expiration_time 2026-11-03 on ALL FOUR legs - identical across
     rungs closing 2026/2027/2028, and BEFORE three of the four close times.
     KXSCOTUSN's five legs all expire 2027-01-01 while closing out to 2029.
     KXALITOOUT's three legs carry occurrence_datetime 2026-07-01, ALREADY IN
     THE PAST. occurrence_datetime is present on 2 of KXIMPEACH's 4 legs.
341. [2026-08-19] INVARIANT J HONOURED BY A SUBAGENT: it launched a
     2,198-series background sweep, the output never flushed, and it ANNOUNCED
     that it did not wait rather than reporting a number. No conclusion in its
     report depended on it.
342. [2026-08-19] The `/markets` payload has no int-cent `yes_bid`/`yes_ask`
     either - only the `_dollars` STRING forms. Same trap class as the `_fp`
     fields. momentum_filter._ask_cents/_bid_cents already handle both.

## 2026-08-19 - Board re-verified, and four more analog slots measured

343. [2026-08-19] BOARD RE-VERIFIED (rotation item 4). 13 categories,
     13,332 series: Sports 3,458 · Entertainment 2,536 · Politics 2,198 ·
     Elections 1,592 · Financials 991 · Economics 741 · Companies 517 ·
     Science and Technology 381 · Climate and Weather 354 · Crypto 273 ·
     World 149 · Health 98 · Transportation 44. Drift since 08-18: Sports
     3,453 -> 3,458, Companies 515 -> 517, Crypto 272 -> 273.
344. [2026-08-19] RESIDUE SWEEP for the remaining unwritten families:
     nfl_inplay 24 series / 18 LIVE / 1,624 open markets (the largest live
     surface left) · cabinet 10 / 2 live / OI 116,606 · crypto_token 36 / 2 /
     41,248 · scotus_case 5 / 4 / 21,930 · soccer_corner 22 / 4 / 2,757 ·
     soccer correct-score: ZERO series exist.
345. [2026-08-19] NOVEL SHAPE FOUND, previously unmodelled: KXNFL1QSPREAD is a
     HANDICAP LADDER - "If Las Vegas wins by MORE THAN 7.5 POINTS in the 1st
     Quarter", 10 legs ME=False, ask-sum 437c. A signed-margin ladder is NOT a
     totals ladder: it is centred on zero, its rungs can be negative, and it
     distributes over MARGIN rather than over a count. The vault had no
     handicap archetype at all. Dispatched.
346. [2026-08-19] KXNFL1H is 3 legs ME=True at 108c - an explicit TIE LEG for a
     HALF, while the full-game KXNFLGAME pays $0.50 to each side on a tie. Two
     tie conventions inside one league, split by scope.
347. [2026-08-19] KXSCOTUSCASE settles on the SUPREME COURT itself and prices
     the CONTENT of a decision, not whether a person is confirmed - the vault's
     first ruling-content contract. Dispatched.
348. [2026-08-19] THE "None recorded" COUNT WAS BEING MEASURED WRONG. A naive
     `grep -l "None recorded"` counts any file mentioning the phrase anywhere,
     including hubs and briefs that merely quote it. Counting the ## Historical
     Analog SECTION specifically gives the real figure. Corrected: 20 measured
     / 102 empty (the rotation's cached "77" was the naive number).
349. [2026-08-19] BACKFILLED Crypto 15-Minute Price Binary: 49.9% of 15-minute
     binaries resolve YES - 1,198 of 2,400 - within a tenth of a point of a
     coin flip, with ZERO abandonment. That is the calibration statement the
     archetype needs: no directional edge exists in this book, so any edge must
     come from spread, strike placement or realised volatility. FLOOR (12-page
     cap, ~1 month at ~96 events/day).
350. [2026-08-19] BACKFILLED MLB Single-Game Moneyline: 872 of 876 games settled
     normally - abandonment 0.5%, THE LOWEST OF ANY EVENT CONTRACT MEASURED.
     Full ordering now: CS2 9.9% > UFC bout 7.1% > WTA 4.0% > ATP 3.7% >
     UFC method 1.7% > MLB games 0.5% > scheduled data 0%. Baseball
     postponements are RESCHEDULED AND PLAYED rather than voided, so the
     contract follows the game to a new date instead of paying an
     administrative price. That is why its ask-sum reads cleanly as vig.
351. [2026-08-19] BACKFILLED Weather Daily Precipitation Basket with a direct
     CALIBRATION TEST: 125 of 600 city-legs recorded rain across 30 settled
     days = 20.8%, i.e. ~4.17 of 20 cities. A live KXRAIN book asked 490c,
     which on the basket reading implies ~4.9 cities. Close, book on the higher
     side. Recorded explicitly as NOT an edge - one day's book against a 30-day
     seasonal average is not the same quantity, and the ask side carries the
     spread. What it DOES establish is that the ask-sum behaves as an expected
     count rather than as vig, which is the note's structural claim.
352. [2026-08-19] BACKFILLED Combat Method of Victory: across 113 decided bouts,
     KO/TKO/DQ 46.0% · Decision 31.0% · Submission 23.0%. A FINISH IS THE MODAL
     OUTCOME - 69% of bouts do not reach the judges.
     METHOD NOTE: the winner labels are "<fighter> by <method>", so counting
     winners by label returns each fighter once and the top "winner" holds
     1.8%. The base rate only appears once the fighter name is STRIPPED and the
     method suffix aggregated. A label is not a category.

## 2026-08-19 - Systematic backfill pass (19 -> 25 measured) + backfill_probe.py

353. [2026-08-19] BUILT `backfill_probe.py` (in the repo, with tests) instead of
     guessing which notes to backfill. It maps each empty note to the KX
     tickers named in its OWN ALIASES - the only reliable note->ticker mapping,
     since filenames carry archetype names and no ticker - and asks the settled
     feed how much history exists. Measured: 82 empty notes name a ticker,
     **35 have ANY settled history, and only about 8 have a sample big enough
     to state a rate**. That ratio is the point: most empty slots are
     CORRECTLY empty.
354. [2026-08-19] BACKFILLED Player Daily Stat Prop, and the UNIT turned out to
     matter enormously: 13.9% of EVENTS (10 of 72) contain at least one voided
     leg, but only 0.9% of individual PLAYER LEGS void (21 of 2,400). A game
     lists a median of 34 hitters, so "somebody is scratched" is common while
     "YOUR player is scratched" is rare. Quoting the event rate against a
     single position overstates the risk ~15x. This closes the measurement the
     note itself flagged as pullable-but-untaken.
355. [2026-08-19] BACKFILLED Combat Round and Distance Ladder: Round 1 38.1% ·
     Decision 31.0% · Round 2 17.7% · Round 3 11.5% · Round 4 0.9% · Round 5
     0.9% across 113 decided bouts. ROUND 1 IS THE MODAL OUTCOME - more likely
     than the fight reaching the judges - and rounds 4-5 are 1.8% combined
     because only title/main events are scheduled for five.
356. [2026-08-19] CROSS-CHECK THAT VALIDATES BOTH MEASUREMENTS: summing the
     finish rungs of KXUFCVICROUND (38.1+17.7+11.5+0.9+0.9) gives 69.1%,
     against the 69.0% finish rate computed independently from KXUFCMOV
     (KO/TKO/DQ 46.0% + Submission 23.0%). Two different series, two different
     settled feeds, the same number to a tenth of a point.
357. [2026-08-19] BACKFILLED Tennis Match Games Ladder: 5.3% abandoned (43 of
     804) against 3.7% for the ATP match-winner book ON THE SAME SPORT. The gap
     is the retirement rule doing exactly what it says - a mid-match retirement
     still DETERMINES A WINNER (the opponent advances) so the moneyline settles
     normally, but it does NOT determine a completed games count, so the ladder
     cannot. ABANDONMENT IS A PROPERTY OF THE QUESTION, NOT OF THE MATCH: the
     finer the quantity, the more often it cannot be settled on partial play.
358. [2026-08-19] BACKFILLED Motorsport Race Winner Grid: 15 different drivers
     won 21 settled races, no driver more than twice, 0% abandonment on 33-39
     leg fields. The turnover is the case for the wide field price - a book
     whose modal winner takes 2 of 21 has genuinely diffuse probability. NOTE
     the zero abandonment does NOT vindicate the unverified red-flag rules;
     they simply were not exercised in these 21 races.
359. [2026-08-19] BACKFILLED Politics Approval Rating Aggregator: 7 different
     winning bins across 9 snapshots, but ALL clustered in a ~0.5 point band.
     The bins are only 0.3 points wide, so ordinary aggregator drift steps
     across one. THE QUANTITY IS STABLE AND THE CONTRACT IS NOT - a position
     can lose on a move far smaller than any news would justify.
360. [2026-08-19] DELIBERATELY NOT BACKFILLED: KXNFLGAME (17 events, 1
     abandoned) and KXNEXTTEAMNBA (8 events). Both have settled history but
     the samples cannot support a rate, and the NFL sample is preseason. An
     empty slot is better than a number with no sample behind it.
361. [2026-08-19] Analog slots now 25 measured / 97 empty (from 19/103 at the
     start of the pass).

## 2026-08-19 - Fixed cardinality CONFIRMED against settled outcomes

362. [2026-08-19] THE FIXED-CARDINALITY STRUCTURE IS NOW EMPIRICALLY PROVEN,
     not inferred. Across 20 settled KXNASCARTOP10 races, EXACTLY 10 legs
     resolved yes EVERY SINGLE TIME - mean 10.00, ZERO VARIANCE - on fields of
     33-39 drivers. Ten drivers finish in the top ten because ten places exist.
363. [2026-08-19] The contrast with a genuine independent basket is total:
       KXNASCARTOP10 "top 10 finishers"  mean 10.00 yes legs, NEVER varies
       KXRAIN 20 cities                  mean  4.17 yes legs, varies daily
     Same measurement, same kind of window. That is the difference between a
     CONSTRAINED basket (ask-sum = K x 100 + vig, K fixed by the rules) and an
     INDEPENDENT one (ask-sum = an expected count the book is forecasting).
364. [2026-08-19] FULL VALIDATION LOOP CLOSED for the sixth structure:
     rules_primary says "finishes in the top 10" -> stated_cardinality reads
     K=10 -> the bid/ask bracket contains 10 -> the classifier reports
     CONSTRAINED -> the settled feed shows exactly 10 winners in 20/20 races.
     Live check today: KXNASCARTOP10 (41 legs) and KXF1TOP10 (22 legs) both
     CONSTRAINED with statedK=10; KXRAIN statedK=None -> plain basket.
     This retires the doubt raised in finding 309, where the bracket-only
     version of the rule produced false positives on KXMLBHR and
     KXNFLSEASONPASSYDS.
365. [2026-08-19] BACKFILLED Motorsport Finishing Position Basket with the
     above, and added a regression test pinning the classifier to the observed
     difference rather than to the arithmetic.
     NOTE the limit of the evidence: the quantity has zero variance BY
     CONSTRUCTION, so 20 races is plenty for this claim and tells us nothing
     about whether a race shortened by a red flag still fills ten positions -
     those rules remain UNVERIFIED in this vertical.

## 2026-08-19 - SEVENTH STRUCTURE (two-sided handicap) + SCOTUS/cabinet

366. [2026-08-19] SEVENTH STRUCTURE ADDED: TWO-SIDED HANDICAP. A spread book
     lists BOTH teams at the SAME margins and Kalshi stores the margin
     UNSIGNED in floor_strike, so the two sides collide at every rung. That
     breaks both existing labels: `threshold_ladder` claims one cumulative
     distribution, but HOU-over-3.5 and LVR-over-3.5 cannot both win;
     `independent_basket` says "read each leg on its own", but same-team rungs
     are strictly nested. The repo gave PERIOD spreads the first label and
     FULL-GAME spreads the second - one archetype, two wrong answers, decided
     by which event you happened to read.
367. [2026-08-19] DETECTION IS EXACT, not a heuristic. A one-sided ladder
     cannot repeat a strike. Measured live: KXNFL1QSPREAD 5 duplicated strikes
     of 10, KXNFLSPREAD 9 of 27, each repeated EXACTLY twice; KXNFL1QTOTAL,
     KXCPIYOY, KXNCAAFWINS and KXMLBTOTAL all have ZERO duplicates.
368. [2026-08-19] ...and the first version of that rule had a FALSE POSITIVE I
     caught before shipping: KXRAIN lists 20 cities that ALL carry
     floor_strike 0.0 ("more than zero precipitation"), which is one strike
     twenty times over. Tightened to require >=3 DISTINCT strikes and a
     maximum multiplicity of EXACTLY 2 - because there are exactly two sides.
     Live re-check after the fix: 12/12 correct across all seven structures.
369. [2026-08-19] I MIS-BRIEFED THE NFL AGENT. I told it "the repo classifier
     AGREED with the exchange flag, so there is no detector bug to work
     around", based on probing ONE event. It correctly pushed back: the
     agreement is only on the ME FLAG and only when attach_event_flags has
     run, while the LABEL stays wrong either way. Verified and fixed.
     PARTIAL CORRECTION TO ITS REPORT: its "+391c fabricated premium" did NOT
     reproduce on the events I checked - the bid-sum and quoteless guards
     withhold the premium in both the raw and flagged paths. The label was the
     real defect, not the number.
370. [2026-08-19] NFL period family: 24 series / 1,624 open markets, 18 live.
     769 of 803 naive substring hits were NON-NFL false positives (soccer and
     other leagues use identical 1Q/1H/SPREAD grammar). The 6 dormant series
     are shells - they return ZERO markets at any status.
371. [2026-08-19] HANDICAP MECHANICS, verbatim: 1,461 open legs carry ZERO
     negative strikes, ZERO integer strikes, and strike_type "greater" on
     every one. Direction lives in custom_strike/the ticker token, not the
     number. A PUSH IS STRUCTURALLY IMPOSSIBLE - every strike is x.5 with a
     strict inequality. Grid is 1.5-7.5 dense then sparse, with NO 8.5 and NO
     12.5.
372. [2026-08-19] A HOLE AT ZERO: KXNFLSPREAD-26SEP13ARILAC gives JAC 14 rungs
     and CAR 11 - asymmetric. Both teams' over-1.5 legs resolve No on {CAR by
     1, tie, JAC by 1}, so their 96c sum is a DEADBAND, not vig.
373. [2026-08-19] TIE BY SCOPE CONFIRMED UNIVERSAL: all 16/16 period-winner
     events across all six series carry a -TIE leg (96 tie legs), while the
     full-game KXNFLGAME pays $0.50 a side. On KXNFL1H-26AUG22WASDET the TIE
     leg (313 OI, 141 v24) OUTDRAWS a team leg. Spreads and totals have no tie
     leg at all - a scoreless quarter resolves every rung to No.
374. [2026-08-19] THE OVERTIME GAP, found: "(excluding overtime)" appears in
     exactly SIX series - KXNFL4Q, KXNFL2H and their SPREAD/TOTAL siblings -
     and NOWHERE in KXNFLSPREAD, KXNFLTOTAL or KXNFLGAME. So OT points count
     for the full game but not for 2H/4Q: a 1H+2H totals pair does NOT
     reconstruct the full-game total in overtime, and a 4Q TIE can pay on a
     game that has a winner.
375. [2026-08-19] NOTHING IN THE PAYLOAD MARKS AN IN-PLAY MARKET. No live
     flag; status is "active" throughout; and occurrence_datetime is KICKOFF
     at every scope, so a 1Q and a 2H market on one game share one timestamp
     and the payload cannot order the six settlements in time.
376. [2026-08-19] PRESEASON is labelled only in product_metadata
     ('competition': 'Pro Football Preseason'). NO rule text in any of the 24
     series treats preseason differently - no starter or snap-count clause -
     and none carries the 48-hour postponement/fair-price clause KXNFLGAME has.

### SCOTUS ruling-content and cabinet (subagent)
377. [2026-08-19] MY OWN RESIDUE SWEEP UNDERCOUNTED CABINET BY ~20x. I briefed
     10 series / 2 live / OI 116,606 from a CABOUT|CABCOUNT|CABINET match; the
     truth is 16 live series / 93 open markets / OI 2,261,020. The `CAB` token
     reaches 18.8% of series and just 5.4% OF THE OI. The residue is the
     bare-surname grammar in four dialects: <SURNAME>OUT, LEAVE<SURNAME>,
     <SURNAME>ANNOUNCEOUT, and ADMIN. Same lesson as finding 299 - sweep the
     FAMILY, and never trust one token.
378. [2026-08-19] CABINET DEPARTURE HAS THREE INCOMPATIBLE TRIGGERS:
     VACATE-ONLY ("must have an actual departure date and vacate the role"),
     ANNOUNCE-BASED ("resolves based on when the departure is publicly
     announced, REGARDLESS OF THE EFFECTIVE DATE"), and a FIELD form (first
     member to leave or announce). KXLEAVEPOWELLGOV is a fourth hybrid where
     announcements more than a year out do NOT count and DEATH DOES NOT
     SATISFY the criterion.
379. [2026-08-19] MATERIAL DIVERGENCE ON THE SAME PERSON: KXTRUMPADMINLEAVE
     (1.65M OI, the largest book in the vertical) drops "expulsion" and the
     word "involuntary" that its per-person sibling KXKASHOUT carries. Kash
     Patel prices in BOTH books under different definitions.
380. [2026-08-19] ACTING OFFICIALS: only KXCABOUT and KXCABLEAVE address them
     ("Acting roles are not included"); the other 14 series are SILENT. And
     KXLOOMERADMIN INVERTS it - acting service explicitly COUNTS.
381. [2026-08-19] DISPOSITION RISK is universal on merits contracts - 24/24
     open markets carry a dismissal/DIG/remand clause - but its SCOPE is
     uneven: only 3/24 cover "settled", 2/24 "moot", 1/24 a split ruling, and
     0/24 mention a 4-4 split or a per curiam. If the Court simply does not
     decide before close, it resolves NO. There is no push state.
382. [2026-08-19] CERT CONTRACTS CARRY ZERO DISPOSITION MACHINERY:
     rules_secondary is the EMPTY STRING on all 10 KXSCOTUSCERT legs. Denial,
     relist, GVR and a limited grant are all unaddressed.
383. [2026-08-19] WORSE GARBAGE SOURCES THAN KXALITOOUT: living people named
     as the settlement authority on their OWN departure - "Pete Hegseth" ->
     x.com/PeteHegseth, "Kash Patel" -> x.com/FBIDirectorKash, "Jeanine
     Pirro", "Kevin Warsh". Plus UNEXPANDED TEMPLATE PLACEHOLDERS shipped on
     live money with the angle brackets intact: "office or organization where
     <person> holds <office>". And KXCABLEAVE's rules_secondary OPENS with a
     named-person carve-out: "Any action related to Tulsi Gabbard will not
     qualify."
384. [2026-08-19] SECOND INCOMPLETE-PARTITION CASE (after KXNUMSHUTDOWNS,
     finding 327): KXCABOUT-26MAY22 is ME=True with a 12.0c premium, but its
     rules define a 25-office Cabinet while only 21 legs exist and there is no
     residual "any other" leg. The premium mixes vig with unmodelled mass on
     4+ uncovered offices. STILL NOT FIXED, deliberately: two instances do not
     justify a fragile parser for "how big is the true outcome space", and I
     have already been burned once inferring structure from arithmetic
     (finding 309). Documented as a limitation.
385. [2026-08-19] The Library-of-Congress / supremecourt.gov split HOLDS on
     the court side (all 24 merits events + all cert series name the Supreme
     Court alone) with TWO breaks: KXSCOTUSPOWER (what the Court will look
     like) settles on the LIBRARY OF CONGRESS, and KXSCOTUSCHANGE (the size of
     the Court) on a 13-outlet MEDIA PANEL - neither the Court nor Congress.

## 2026-08-19 - The seventh structure, verified AT SCALE and corrected twice

386. [2026-08-19] BOARD-WIDE SWEEP of the new two-sided-handicap structure.
     244 SPREAD-token series exist; 67 are live carrying 2.89M OI. The
     structure is NOT an NFL curiosity - it spans MLB (KXMLBSPREAD, 1,307,451
     OI, the LARGEST spread book on the exchange), NFL, WNBA, college
     football, CFL, club soccer and the Slovak Cup.
387. [2026-08-19] ...and the first version of my own rule had FALSE NEGATIVES,
     found by that sweep. Requiring >=3 DISTINCT margins missed the COMMON
     case: KXMLSSPREAD, KXLALIGASPREAD, KXUCLSPREAD and KXMLBF5SPREAD are all
     4 legs - two teams at 1.5 and 2.5 - because soccer and first-five-innings
     books simply do not list deep margins. Every one was still being called a
     `threshold_ladder`.
388. [2026-08-19] Worse, KXATPGSPREAD is two-sided with ASYMMETRIC margins -
     Tiafoe at -1.5 against Auger-Aliassime at -2.5 and -5.5 - so NO strike
     repeats at all and a duplicate-counting rule cannot see it even in
     principle.
389. [2026-08-19] BETTER SIGNAL, tested offline before touching code (14/15
     correct): COUNT THE SIDES. Each leg's ticker suffix is a subject token
     plus a rung index (SKC2/SKC3/ATL2/ATL3), so stripping trailing digits and
     counting distinct prefixes counts the teams - and a handicap has EXACTLY
     two. One-sided ladders give sides=1 (KXMLBTOTAL, KXCPIYOY, KXNCAAFWINS,
     KXNFL1QTOTAL all measured); KXRAIN gives 20 and KXNASCARTOP10 gives 41,
     so baskets are excluded by the same test. The symmetric duplicate-strike
     rule is kept as a FALLBACK for ticker grammars with no subject token.
390. [2026-08-19] RESULT OF THE FIX, re-measured live: two-sided handicaps go
     from 18 to 55 of 67 live spread series, and from ~1.9M to 3,262,556 OI.
     THAT IS 3.26M OF OPEN INTEREST THAT WAS BEING MISLABELLED as either a
     cumulative ladder or an independent basket until today. The 12 remaining
     `threshold_ladder` spreads hold 6,462 OI between them - 0.2% of the
     family - and are NOT individually verified; a full re-sweep timed out and
     I did not repeat it.
     Spot-verified after the fix: KXATPGSPREAD (3 legs, asymmetric),
     KXMLSSPREAD and KXUCLSPREAD (4 legs each) all now read
     two_sided_handicap, while KXMLBTOTAL, KXCPIYOY, KXRAIN, KXNASCARTOP10,
     KXF1POLE and KXIMPEACH are untouched.
391. [2026-08-19] METHOD NOTE - this structure took THREE rounds to get right,
     and each round was caught by evidence rather than by review:
       round 1  duplicate strikes only        -> false POSITIVE on KXRAIN
                                                 (20 cities at floor 0.0)
       round 2  >=3 distinct margins, mult 2  -> false NEGATIVES on every
                                                 4-leg soccer/F5 spread
       round 3  count the sides (==2)         -> 14/15 offline, 55/67 live
     The lesson that generalises: a structural claim should be tested against
     the WHOLE board before it is trusted, not against the one vertical that
     suggested it. Two of the three rounds looked correct on NFL alone.
392. [2026-08-19] The last 12 mislabelled spread series identified and fixed:
     all are 2-leg FIRST-HALF SOCCER spreads (KXLALIGA1HSPREAD, KXUCL1HSPREAD,
     KXMLS1HSPREAD, KXCONMEBOLLIB1HSPREAD and 8 more) listing ONE margin per
     team - "Vallecano wins the 1H by more than 1.5" against its opponent.
     Two sides, two legs. My >=3-leg floor excluded them; lowered to 2.
     The STRIKE guard is what protects 2-leg moneylines: KXMLBGAME and
     KXNFLGAME have two legs and two sides but NO floor_strike, so they never
     reach the handicap test. Verified live: KXLALIGA1HSPREAD now
     two_sided_handicap while KXMLBGAME and KXNFL1H stay exclusive_field.
     ALL 67 live spread series are now classified; the family is closed.
393. [2026-08-19] FUND DESIGN SPEC written to
     docs/superpowers/specs/2026-08-19-prediction-market-fund-design.md via
     the superpowers:brainstorming architectural path. Key decisions recorded
     there: reward on CALIBRATION (Brier delta) not P&L, because a binary
     outcome is one bit and rewarding P&L amplifies luck; contextual bandit
     with Thompson sampling rather than deep RL, because 10-50 trades/week
     cannot validate RL; Deflated Sharpe Ratio as the acceptance gate; the
     risk model validated SEPARATELY from the alpha model; and the online
     learner barred from changing any limit (it adjusts beliefs, never
     limits). Self-review caught a contradiction - §7.4 tuned `ru_budget_pct`
     while §9.1 declared it untunable - resolved by splitting the online
     learner from the monthly human-approved offline re-fit.
