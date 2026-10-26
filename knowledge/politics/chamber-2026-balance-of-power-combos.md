---
aliases:
  - "Chamber: 2026 Balance of Power Combos"
tags:
  - politics
  - chamber
  - mechanics
created: 2026-10-09
as_of: 2026-10-09
markets:
  - KXBALANCEPOWERCOMBO-27FEB
  - KXBLUEWAVECOMBO-27FEB
  - KXBLUETSUNAMICOMBO-27FEB
---

# Chamber: 2026 Balance of Power Combos

Back to [[Politics Knowledge Index]]

Scope: exact rules of the Kalshi combination markets on House and Senate outcomes, current prices, and how they line up with the single-chamber and seat-count markets.

## Claims

- KXBALANCEPOWERCOMBO-27FEB has four mutually exclusive outcomes: DD (Democrats sweep), RR (Republicans sweep), DR (D House, R Senate) and RD (R House, D Senate). Each is a combination contract that requires every component to hold. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXBALANCEPOWERCOMBO-27FEB?with_nested_markets=true)
- Balance-of-power prices: DD 0.61/0.62, DR 0.28/0.29, RR 0.10/0.11, RD 0.007/0.008 (bid/ask). Midpoints sum to about 1.01. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXBALANCEPOWERCOMBO-27FEB?with_nested_markets=true)
- Open interest in the balance-of-power event is concentrated in RR (about 13.3M contracts) and RD (about 7.8M). DD has about 2.76M and DR about 1.93M. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXBALANCEPOWERCOMBO-27FEB?with_nested_markets=true)
- DD + DR midpoints come to about 0.90, matching the CONTROLH-2026 Democratic midpoint of about 0.90. DD + RD come to about 0.62, close to the CONTROLS-2026 Democratic midpoint of about 0.615. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/CONTROLS-2026?with_nested_markets=true)
- KXBLUEWAVECOMBO-27FEB rule: Yes if Democrats hold 218 or more House seats AND 49 or more Senate seats after the 2026 midterms. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXBLUEWAVECOMBO-27FEB?with_nested_markets=true)
- Under the blue-wave definition Democrats can win while staying in the Senate minority: 49 or 50 D seats with a Republican VP is not control, but it still pays Yes. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXBLUEWAVECOMBO-27FEB?with_nested_markets=true)
- KXBLUEWAVECOMBO-27FEB is priced at 0.86 bid / 0.87 ask, with open interest of about 717K. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXBLUEWAVECOMBO-27FEB?with_nested_markets=true)
- KXDSENATESEATS-27 midpoints put P(D Senate ≤ 48) at about 0.16, so P(D ≥ 49) is about 0.84. That is below the 0.865 blue-wave midpoint, even though the combo requires the Senate ≥ 49 leg. On bids, the ≤48 buckets sum to 0.15. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXDSENATESEATS-27?with_nested_markets=true)
- KXBLUETSUNAMICOMBO-27FEB rule: Yes if Democrats hold 235 or more House seats AND 51 or more Senate seats after the 2026 midterms. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXBLUETSUNAMICOMBO-27FEB?with_nested_markets=true)
- KXBLUETSUNAMICOMBO-27FEB is priced at 0.43 bid / 0.45 ask, with open interest of about 313K. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXBLUETSUNAMICOMBO-27FEB?with_nested_markets=true)
- Ladder bounds for the tsunami legs: KXDHOUSESEATS-27 midpoints give P(D House ≥ 238) of about 0.42 plus a 234-237 bucket of about 0.145, so P(D ≥ 235) lies between about 0.42 and 0.57. KXDSENATESEATS-27 gives P(D Senate ≥ 51) of about 0.685. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXDHOUSESEATS-27?with_nested_markets=true)
- DDHQ's Oct 8, 2026 forecast projects 235 D House seats and 51 D Senate seats, exactly the tsunami thresholds. (as_of: 2026-10-08; source: https://votes.decisiondeskhq.com/forecast/2026/house)
- KXBALANCEPOWERCOMBO-27FEB-DD daily closes: 0.33 on Feb 1, 0.472 on Apr 1, 0.41 on Jul 1, 0.47 on Sep 1, 0.62 on Oct 1 and 0.65 on Oct 7, 2026. (as_of: 2026-10-07; source: https://api.elections.kalshi.com/trade-api/v2/series/KXBALANCEPOWERCOMBO/markets/KXBALANCEPOWERCOMBO-27FEB-DD/candlesticks?start_ts=1767247200&end_ts=1791522000&period_interval=1440)

## Resolution notes

- Combination rule: if any single component resolves No or becomes impossible, the whole contract resolves No immediately. Balance-of-power components use the CONTROL ruleset, which allows accelerated resolution on media calls and otherwise uses the Speaker and President pro tempore party on Feb 1, 2027. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXBALANCEPOWERCOMBO-27FEB?with_nested_markets=true)
- The blue-wave and blue-tsunami components use the SEATSCONGRESS ruleset. They resolve on House and Senate composition on Feb 1, 2027, with independents who caucus with a party counted with it (for example, Sanders as D). All four combo events close Feb 1, 2027 at 15:00 UTC. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXBLUETSUNAMICOMBO-27FEB?with_nested_markets=true)
- The wave and tsunami contracts count seats held on Feb 1, 2027, not election-night results. Vacancies, deaths or party switches before that date count, and so do Louisiana House seats decided in the Dec 12, 2026 general. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXBLUEWAVECOMBO-27FEB?with_nested_markets=true)

## Related

- [[chamber-2026-house-control]]
- [[chamber-2026-senate-control]]
- [[chamber-2026-generic-ballot]]

## Timeline

- [2026-10-09] Market: DD 0.61/0.62, blue wave 0.86/0.87, blue tsunami 0.43/0.45. https://api.elections.kalshi.com/trade-api/v2/events/KXBALANCEPOWERCOMBO-27FEB?with_nested_markets=true
- [2026-10-07] Market: DD daily close 0.65. https://api.elections.kalshi.com/trade-api/v2/series/KXBALANCEPOWERCOMBO/markets/KXBALANCEPOWERCOMBO-27FEB-DD/candlesticks?start_ts=1767247200&end_ts=1791522000&period_interval=1440
- [2026-07-01] Market: DD daily close 0.41. https://api.elections.kalshi.com/trade-api/v2/series/KXBALANCEPOWERCOMBO/markets/KXBALANCEPOWERCOMBO-27FEB-DD/candlesticks?start_ts=1767247200&end_ts=1791522000&period_interval=1440
- [2026-02-01] Market: DD daily close 0.33. https://api.elections.kalshi.com/trade-api/v2/series/KXBALANCEPOWERCOMBO/markets/KXBALANCEPOWERCOMBO-27FEB-DD/candlesticks?start_ts=1767247200&end_ts=1791522000&period_interval=1440
- [2025-12-12] Listing: KXBLUEWAVECOMBO-27FEB opens. https://api.elections.kalshi.com/trade-api/v2/events/KXBLUEWAVECOMBO-27FEB?with_nested_markets=true
- [2025-12-11] Listing: KXBALANCEPOWERCOMBO-27FEB opens. https://api.elections.kalshi.com/trade-api/v2/events/KXBALANCEPOWERCOMBO-27FEB?with_nested_markets=true
