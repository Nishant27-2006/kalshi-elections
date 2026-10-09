---
aliases:
  - "Policy: Trump Impeachment and Removal"
tags:
  - politics
  - policy
  - base-rate
  - impeachment
  - trump
created: 2026-10-09
as_of: 2026-10-09
markets:
  - KXIMPEACH
  - KXIMPEACH-29
  - KXTRUMPREMOVE
  - KXTRUMPOUT27-27
---

# Policy: Trump Impeachment and Removal

Back to [[Politics Knowledge Index]]

Scope: impeachment resolutions filed against Trump in his second term, how the House disposed of them, current House composition, historical impeachment and conviction base rates, and pricing for the impeachment, removal and early-departure markets.

## Claims

- Rep. Shri Thanedar announced an impeachment push on Apr. 29, 2025 and filed seven articles on May 14, 2025 (obstruction of justice, bribery, corruption); other congressional Democrats condemned the move. (as_of: 2025-05-14; source: https://en.wikipedia.org/wiki/Efforts_to_impeach_Donald_Trump)
- Rep. Al Green submitted impeachment articles as H.Res. 415 on May 15, 2025. (as_of: 2025-05-15; source: https://en.wikipedia.org/wiki/Efforts_to_impeach_Donald_Trump)
- The House tabled H.Res. 537 (impeaching Trump) 344-79 on June 24, 2025, with 9 members not voting yea or nay. (as_of: 2025-06-24; source: https://www.govtrack.us/congress/votes/119-2025/h175)
- The House tabled H.Res. 939 (Al Green's impeachment resolution) 237-140 on Dec. 11, 2025, with 56 voting present or not voting; Democratic leaders voted "present." (as_of: 2025-12-11; source: https://www.govtrack.us/congress/votes/119-2025/h322)
- After Trump's Apr. 7, 2026 Truth Social post threatening Iran, several current and former officials called for impeachment or the 25th Amendment. (as_of: 2026-04-07; source: https://en.wikipedia.org/wiki/Efforts_to_impeach_Donald_Trump)
- House Democrats described impeachment of administration officials as "ongoing conversations" if they win the House. Rep. Robert Garcia: "a lot of others should be impeached." (as_of: 2026-09-10; source: https://idahonews.com/news/nation-world/democrats-plan-to-go-after-defense-secretary-hegseth-if-they-win-2026-midterms-robert-garcia-pentagon-jason-crow)
- The House tabled H.Res. 1486 (impeaching Trump) 232-147 on Sep. 15, 2026, with 54 voting present or not voting. That is the third tabled impeachment resolution of the 119th Congress. (as_of: 2026-09-15; source: https://www.govtrack.us/congress/votes/119-2026/h298)
- House Clerk party breakdown: 218 Republicans, 214 Democrats, 1 Independent, 2 vacancies. Impeachment takes a simple majority of members voting. (as_of: 2026-10-09; source: https://clerk.house.gov/Members)
- KXIMPEACH ladder on Oct. 9, 2026: before Jan 1, 2027 last 0.044; before Feb 1, 2027 0.29 (bid 0.11 / ask 0.26); before Mar 1, 2027 0.32; before Jul 1, 2027 0.43; before Oct 1, 2027 0.64; before Jan 1, 2028 0.68. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXIMPEACH?with_nested_markets=true)
- KXIMPEACH-29 (impeached before Jan 20, 2029) last 0.66 (bid 0.65 / ask 0.66) on Oct. 9, 2026. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXIMPEACH-29?with_nested_markets=true)
- KXTRUMPREMOVE (impeached and convicted before Jan 20, 2029) last 0.20 (bid 0.19 / ask 0.20) on Oct. 9, 2026. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXTRUMPREMOVE?with_nested_markets=true)
- KXTRUMPOUT27-27 (Trump leaves or announces departure, excluding death) last prices on Oct. 9, 2026: before 2027 0.036, before 2028 0.17, before Jan 20, 2029 0.25. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXTRUMPOUT27-27?with_nested_markets=true)
- Kalshi settled KXIMPEACH-26-SEP01 (impeached before Sep 1, 2026) No. (as_of: 2026-09-01; source: https://api.elections.kalshi.com/trade-api/v2/events/KXIMPEACH?with_nested_markets=true)

## Base rates

- base_rate: presidential_impeachments_ending_in_conviction = 0.0; n = 4; window = 1868-2021 (Johnson 1868, Clinton 1999, Trump 2020, Trump 2021 all "Not guilty"); (as_of: 2021-02-13; source: https://www.senate.gov/about/powers-procedures/impeachment/impeachment-list.htm)
- base_rate: senate_impeachment_trials_ending_in_conviction = 0.38; n = 21; window = 1799-present (8 convictions, all federal judges); (as_of: 2026-10-09; source: https://www.senate.gov/about/powers-procedures/impeachment/impeachment-list.htm)
- base_rate: second_term_house_votes_to_table_trump_impeachment = 3; n = 3; window = 2025-06-24..2026-09-15 (all three tabled); (as_of: 2026-09-15; source: https://www.govtrack.us/congress/votes/119-2026/h298)

## Resolution notes

- KXIMPEACH and KXIMPEACH-29 resolve Yes if the House passes an impeachment resolution while the President is in office. Conviction is not required. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXIMPEACH-29?with_nested_markets=true)
- KXTRUMPREMOVE needs impeachment and Senate conviction before Jan 20, 2029, with the President still sitting on the day of the conviction vote. Conviction takes a two-thirds supermajority. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXTRUMPREMOVE?with_nested_markets=true)
- KXTRUMPOUT27 also counts an announcement that he will leave within the next year, but not an acknowledgement of the normal term limit. Death settles at the last traded price. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXTRUMPOUT27-27?with_nested_markets=true)

## Related

- [[Politics Knowledge Index]]
- [[policy-trump-approval]]
- [[policy-cabinet-departures]]

## Timeline

- [2026-10-09] Market: impeached-during-term 0.66; removed 0.20. https://api.elections.kalshi.com/trade-api/v2/events/KXIMPEACH-29?with_nested_markets=true
- [2026-09-15] Vote: House tables H.Res. 1486, 232-147. https://www.govtrack.us/congress/votes/119-2026/h298
- [2026-09-10] Statement: House Democrats signal impeachment talk about administration officials. https://idahonews.com/news/nation-world/democrats-plan-to-go-after-defense-secretary-hegseth-if-they-win-2026-midterms-robert-garcia-pentagon-jason-crow
- [2025-12-11] Vote: House tables H.Res. 939, 237-140. https://www.govtrack.us/congress/votes/119-2025/h322
- [2025-06-24] Vote: House tables H.Res. 537, 344-79. https://www.govtrack.us/congress/votes/119-2025/h175
- [2025-05-14] Filing: Thanedar files seven articles. https://en.wikipedia.org/wiki/Efforts_to_impeach_Donald_Trump
