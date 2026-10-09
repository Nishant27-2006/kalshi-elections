---
aliases:
  - "International: World Leaders Leaving Office in 2026"
tags:
  - politics
  - international
  - mechanics
created: 2026-10-09
as_of: 2026-10-09
markets:
  - KXLEADERSOUT-27JAN01
---

# International: World Leaders Leaving Office in 2026

Back to [[Politics Knowledge Index]]

Tracks the leaders in Kalshi's "which leaders will leave office in 2026" event who face elections, government formation or confidence fights before Jan 1, 2027, along with each strike's price.

## Claims

- KXLEADERSOUT-27JAN01-GPETCOL (Gustavo Petro, Colombia) is finalized Yes, with the market closing 2026-08-08. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXLEADERSOUT-27JAN01?with_nested_markets=true)
- New Zealand's parliament held its final sitting before the Nov 7, 2026 general election. (as_of: 2026-09-23; source: https://www.usnews.com/news/world/articles/2026-09-23/new-zealand-parliament-adjourns-before-november-election)
- RNZ-Reid Research: Labour 30.8%, National 25.9% (National's weakest since 2020), Greens 14.8%, NZ First 10.6%, ACT 9%, Opportunity 5.5%. (as_of: 2026-10-06; source: https://www.aa.com.tr/en/asia-pacific/opposition-labour-leads-ruling-national-as-new-zealand-heads-toward-nov-7-election/4079343)
- In the RNZ-Reid poll, neither the current coalition nor a Labour-Greens-Te Pāti Māori bloc reaches a majority of 120 seats, and Opportunity's seven projected MPs could put either side over. 1News-Verian had National 29, Labour 28, Greens 16 and Opportunity 7, with the blocs tied at 58 seats each in a 124-seat House. (as_of: 2026-10-07; source: https://thespinoff.co.nz/politics/07-10-2026/chris-v-chris-hipkins-takes-the-win-while-both-struggle-to-win-over-voters)
- Undecided voters judged Labour's Chris Hipkins the narrow winner of the first leaders' debate against PM Christopher Luxon. (as_of: 2026-10-06; source: https://www.standard.net.au/story/9363932/hipkins-edges-first-new-zealand-election-debate/)
- Spanish PM Pedro Sánchez called a snap general election for Nov 29, 2026, after parliament rejected his housing decrees. (as_of: 2026-10-05; source: https://www.yahoo.com/news/articles/spanish-pm-sanchez-morning-announcement-062558434.html)
- A Sigma Dos projection gave PP plus Vox 203 of 350 seats and Socialists plus Sumar 112. (as_of: 2026-10-05; source: https://www.yahoo.com/news/articles/spanish-pm-sanchez-morning-announcement-062558434.html)
- Israel's Knesset election stays on its legally set date of Oct 27, 2026. (as_of: 2026-07-12; source: https://www.globalbankingandfinance.com/israels-election-held-october-27-coalition-head/)
- Brazil's presidential runoff, Lula vs. Flávio Bolsonaro, is Oct 25, 2026. (as_of: 2026-10-05; source: https://en.mercopress.com/2026/10/05/flavio-bolsonaro-edges-lula-in-the-first-round-both-head-to-an-october-25-runoff)
- French PM Sébastien Lecornu's minority government faces a "particularly treacherous" budget season as opposition parties dig in over the 2027 budget. (as_of: 2026-10-01; source: https://www.msn.com/en-us/news/other/explainer-how-frances-2027-budget-battle-could-play-out/ar-AA2dl864)
- On Kalshi, election-exposed strikes bid/ask: Luxon 0.47/0.49, Netanyahu 0.38/0.40, Sánchez 0.26/0.28, Lecornu 0.24/0.33, Lula 0.041/0.059. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXLEADERSOUT-27JAN01?with_nested_markets=true)
- On Kalshi, other strikes bid/ask: Merz 0.12/0.13, Díaz-Canel 0.08/0.10, Zelenskyy 0.069/0.074, Putin 0.045/0.055, Macron 0.026/0.05, Sheinbaum 0.039/0.054, Takaichi 0.033/0.049, Xi 0.023/0.024. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXLEADERSOUT-27JAN01?with_nested_markets=true)

## Base rates

- base_rate: nz_govt_formation_days_2023 = 44; window = 2023-10-14 to 2023-11-27; (as_of: 2023-11-27; source: https://en.wikipedia.org/wiki/Sixth_National_Government_of_New_Zealand)
- base_rate: israel_govt_formation_days_2022 = 58; window = 2022-11-01 to 2022-12-29; (as_of: 2022-12-29; source: https://en.wikipedia.org/wiki/Thirty-seventh_government_of_Israel)
- base_rate: israel_govt_formation_days_2021 = 82; window = 2021-03-23 to 2021-06-13; (as_of: 2021-06-13; source: https://en.wikipedia.org/wiki/Thirty-sixth_government_of_Israel)

## Resolution notes

- A strike resolves Yes if the leader officially announces they will leave the named office, or actually leaves it, before Jan 1, 2027. An announcement counts only if a Source Agency reports it and it does not put the departure more than a year out. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXLEADERSOUT-27JAN01?with_nested_markets=true)
- "Leaving office" means no longer holding the office in any capacity: effective resignation, removal, recall, or a term ending without renewal. Medical leave, suspension or delegation does not count. Death does NOT satisfy the contract, and forced departures count without an announcement. So a defeated PM still serving as caretaker has not left office. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXLEADERSOUT-27JAN01?with_nested_markets=true)
- From an election to Dec 31 there are 54 days for New Zealand (Nov 7), 65 days for Israel (Oct 27) and 32 days for Spain (Nov 29). A change of PM therefore has to beat the historical formation lags above, unless the leader concedes with an announcement that counts. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXLEADERSOUT-27JAN01?with_nested_markets=true)

## Related

- [[International: Israel 2026 Knesset Election]]
- [[International: Brazil 2026 Presidential Election]]
- [[International: France 2027 Presidential Election]]
- [[International: Venezuela Leadership]]
- [[Policy: Trump Cabinet and Staff Departures]]

## Timeline

- [2026-10-09] Market: Kalshi has Luxon 0.47/0.49, Netanyahu 0.38/0.40, Sánchez 0.26/0.28. https://api.elections.kalshi.com/trade-api/v2/events/KXLEADERSOUT-27JAN01?with_nested_markets=true
- [2026-10-07] Poll: NZ blocs deadlocked in RNZ-Reid and 1News-Verian. https://thespinoff.co.nz/politics/07-10-2026/chris-v-chris-hipkins-takes-the-win-while-both-struggle-to-win-over-voters
- [2026-10-05] Event: Sánchez calls a Spanish election for Nov 29. https://www.yahoo.com/news/articles/spanish-pm-sanchez-morning-announcement-062558434.html
- [2026-10-04] Event: Brazil's first round sends Lula to a runoff. https://en.mercopress.com/2026/10/05/flavio-bolsonaro-edges-lula-in-the-first-round-both-head-to-an-october-25-runoff
- [2026-08-08] Market: Petro strike finalized Yes. https://api.elections.kalshi.com/trade-api/v2/events/KXLEADERSOUT-27JAN01?with_nested_markets=true
