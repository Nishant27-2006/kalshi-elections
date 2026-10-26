---
aliases:
  - "Nomination: 2028 General Election"
tags:
  - politics
  - nomination
  - president
  - general-election
created: 2026-10-09
as_of: 2026-10-09
markets:
  - KXPRESPERSON-28
  - KXPRESPARTY-2028
  - POWER-28
  - KXPRESMATCHUP-28NOV07
---

# Nomination: 2028 General Election

Back to [[Politics Knowledge Index]]

Scope: the 2028 presidential winner (by person and by party), control of the Presidency, House, and Senate together, and the nominee-matchup markets, plus general-election polling and the national environment.

## Claims

### Head-to-head polls
- Emerson (Aug 25–26, 2025): Vance and Newsom tied 44–44, with 12% undecided. That was a shift from a 45–42 Vance lead in July 2025. (as_of: 2025-08-29; source: https://emersoncollegepolling.com/august-2025-national/)
- Emerson (Aug 16–17, 2026; 1,000 LV), against Vance: Buttigieg 49–44, Newsom 49–44, Ossoff 49–44, Ocasio-Cortez 46–48. (as_of: 2026-08-20; source: https://www.coloradopolitics.com/2026/08/20/buttigieg-performs-best-among-democrats-against-rubio-or-vance-in-possible-2028-contest-poll/)
- Same poll, against Rubio: Buttigieg 49–44, Ossoff 47–44, Newsom 47–49, Ocasio-Cortez 45–50. Emerson's headline was that Rubio outperforms Vance. (as_of: 2026-08-20; source: https://www.coloradopolitics.com/2026/08/20/buttigieg-performs-best-among-democrats-against-rubio-or-vance-in-possible-2028-contest-poll/)

### National environment
- Emerson Feb 2026: Trump job approval 43%, disapproval 55%. (as_of: 2026-02-26; source: https://emersoncollegepolling.com/february-2026-national-poll-trump-approval-steady-as-disapproval-rises-vance-leads-gop-field-while-democrats-hold-midterm-edge/)
- Emerson May 2026: Democrats led the generic congressional ballot 50–41. (as_of: 2026-05-28; source: https://emersoncollegepolling.com/may-2026-national-poll/)
- Emerson Aug 2026: Trump approval 40/56; Democrats led the generic ballot 51–43. (as_of: 2026-08-20; source: https://emersoncollegepolling.com/august-2026-national-poll/)
- Emerson (Sep 21–22, 2026): Trump approval 39/58, his highest disapproval of the term in Emerson polling; Democrats led the generic ballot 53–42. (as_of: 2026-09-24; source: https://emersoncollegepolling.com/september-2026-national-poll-democrats/)

### Kalshi prices (snapshot)
- KXPRESPARTY-2028 last prices: Democratic 59¢ (bid 58 / ask 59), Republican 42¢ (bid 41 / ask 42). (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXPRESPARTY-2028?with_nested_markets=true)
- KXPRESPERSON-28 last prices: Vance 19¢, Ossoff 12¢, Ocasio-Cortez 10¢, Newsom 9.4¢, Rubio 9.4¢, Harris 4.5¢, Beshear 3.4¢, Kelly 3.3¢. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXPRESPERSON-28?with_nested_markets=true)
- POWER-28 last prices: Democratic sweep 49¢, Republican sweep 17¢, D-House/R-Senate/D-President 8¢, D-House/R-Senate/R-President 6.9¢, D-House/D-Senate/R-President 5¢. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/POWER-28?with_nested_markets=true)
- KXPRESMATCHUP-28NOV07 last prices: Newsom v. Vance 17¢, Ocasio-Cortez v. Vance 11¢, Ossoff v. Vance 11¢, Ocasio-Cortez v. Rubio 8.8¢, Ossoff v. Rubio 8.4¢, Harris v. Vance 7.1¢, Newsom v. Rubio 3.9¢. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXPRESMATCHUP-28NOV07?with_nested_markets=true)
- Cross-market check on the same day: Newsom v. Vance trades at 17¢ while the Newsom-nominee (13¢) and Vance-nominee (44¢) markets imply about 6¢ if the two were independent. The 0.13 × 0.44 product treats them as independent, so this may point to a rich matchup price or a stale last trade. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXPRESMATCHUP-28NOV07?with_nested_markets=true)

## Resolution notes
- KXPRESPERSON-28: "If [person] is the next person inaugurated as President for the term beginning in 2029, then the market resolves to Yes." Source: Office of the Presidency. Expected expiration 2029-01-21. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/series/KXPRESPERSON)
- KXPRESPARTY-2028: Yes for a party "if a representative of the [party] is inaugurated as President for the term beginning January 20, 2029." Settles on inauguration, not on Election Day. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXPRESPARTY-2028?with_nested_markets=true)
- POWER-28: each of the 8 outcomes is a combination of which party wins the House, the Senate, and the Presidency in the 2028 election. Settlement source: congress.gov. Expected expiration 2029-02-01. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/POWER-28?with_nested_markets=true)
- KXPRESMATCHUP-28NOV07 is a combination market. It pays only if both named people become the D and R nominees under the PRESNOM rulesets, and it resolves No as soon as either leg becomes impossible. Close 2028-11-07. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXPRESMATCHUP-28NOV07?with_nested_markets=true)

## Related
- [[nomination-2028-democratic]]
- [[nomination-2028-republican]]
- [[nomination-base-rates]]

## Timeline
- [2026-10-09] Market: KXPRESPARTY-2028 at D 59¢ / R 42¢. https://api.elections.kalshi.com/trade-api/v2/events/KXPRESPARTY-2028?with_nested_markets=true
- [2026-09-24] Poll: Emerson, Trump approval 39/58, generic ballot D+11. https://emersoncollegepolling.com/september-2026-national-poll-democrats/
- [2026-08-20] Poll: Emerson 2028 head-to-heads; Rubio runs better than Vance. https://www.coloradopolitics.com/2026/08/20/buttigieg-performs-best-among-democrats-against-rubio-or-vance-in-possible-2028-contest-poll/
- [2025-08-29] Poll: Emerson, Vance 44, Newsom 44. https://emersoncollegepolling.com/august-2025-national/
