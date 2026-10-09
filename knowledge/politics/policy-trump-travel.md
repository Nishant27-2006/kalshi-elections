---
aliases:
  - "Policy: Trump Foreign Travel 2026"
tags:
  - politics
  - policy
  - trump
  - travel
  - international
created: 2026-10-09
as_of: 2026-10-09
markets:
  - KXTRUMPCOUNTRIES-27JAN01
  - KXTRUMPIRAN
---

# Policy: Trump Foreign Travel 2026

Back to [[Politics Knowledge Index]]

Scope: which countries Trump physically visits before Jan 1, 2027, and whether he visits Iran. Covers trips taken so far in 2026, trips on the schedule, and current per-country prices.

## Claims

- Trump attended the World Economic Forum in Davos, Switzerland on Jan. 21-22, 2026. (as_of: 2026-01-22; source: https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Donald_Trump)
- Trump made a state visit to Beijing, China on May 13-15, 2026 and met Xi Jinping. (as_of: 2026-05-15; source: https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Donald_Trump)
- Trump attended the 52nd G7 summit in Évian-les-Bains, France on June 15-17, 2026, including a dinner at Versailles. (as_of: 2026-06-17; source: https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Donald_Trump)
- Trump attended the NATO summit in Ankara, Turkey on July 7-8, 2026. On the way home, amid an Iranian assassination threat, he secretly moved from Air Force One to a C-32A while the older plane flew on to RAF Mildenhall as a decoy. (as_of: 2026-07-08; source: https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Donald_Trump)
- Trump visited Ireland on Sep. 12-13, 2026 (Dublin and his Doonbeg resort in County Clare). (as_of: 2026-09-13; source: https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Donald_Trump)
- Across his second term to date, Trump has visited Qatar and the UK twice each. He has visited Canada, China, Egypt, France, Ireland, Israel, Italy, Japan, Malaysia, the Netherlands, Saudi Arabia, South Korea, Switzerland, Turkey, the UAE and Vatican City once each. (as_of: 2026-10-09; source: https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Donald_Trump)
- Scheduled trips for the rest of 2026: Manila, Philippines on Nov. 16-18 (ASEAN and East Asia Summits) and Shenzhen, China on Nov. 18-19 (APEC). (as_of: 2026-10-09; source: https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Donald_Trump)
- Putin plans to attend the Shenzhen APEC summit on Nov. 18-19 and will likely skip the G20 that Trump hosts in Florida. Russian officials have floated a Trump-Xi-Putin trilateral at APEC if Trump attends. (as_of: 2026-09-21; source: https://www.straitstimes.com/world/europe/putin-plans-to-attend-xis-apec-summit-and-skip-g-20-with-trump)
- China proposed moving the APEC foreign and trade ministers' meeting in Shenzhen online, drawing pushback from partners. (as_of: 2026-10-06; source: https://www.afr.com/world/asia/china-fuels-tensions-with-partners-over-scaled-down-apec-summit-plans-20261006-p613bu)
- Trump said on Truth Social that the US would not attack Iran before the Nov. 3 midterms, that talks were "productive," and that the blockade of Iranian ports would stay. (as_of: 2026-10-08; source: https://www.iranintl.com/en/202610086381)
- Jimmy Carter made an official visit to Tehran on Dec. 31, 1977-Jan. 1, 1978 and met the Shah. (as_of: 1978-01-01; source: https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Jimmy_Carter)
- KXTRUMPCOUNTRIES-27JAN01 leaders on Oct. 9, 2026: Germany 0.17 (bid 0.17 / ask 0.18), Israel 0.13, Japan 0.13 (bid 0.12 / ask 0.15), Saudi Arabia 0.12, Poland last 0.11 on a 0.015/0.08 book, Qatar 0.10, Norway 0.10 (thin). (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXTRUMPCOUNTRIES-27JAN01?with_nested_markets=true)
- Other KXTRUMPCOUNTRIES prices on Oct. 9, 2026: Venezuela 0.098, North Korea 0.096 (bid 0.098 / ask 0.099), Italy 0.096, Pakistan 0.08, Russia 0.072, India 0.07, Ukraine 0.062, Mexico 0.06, Canada 0.05, Denmark 0.05, Hungary 0.05, Cuba 0.045, Palestine 0.04, Taiwan 0.033, Vatican City 0.02. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXTRUMPCOUNTRIES-27JAN01?with_nested_markets=true)
- The KXTRUMPCOUNTRIES event endpoint listed 22 active country markets on Oct. 9, 2026. China and the Philippines, the two scheduled November stops, were not among them. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXTRUMPCOUNTRIES-27JAN01?with_nested_markets=true)
- KXTRUMPIRAN-27JAN01 (Trump visits Iran before 2027) last traded 0.033 (bid 0.023 / ask 0.029) on Oct. 9, 2026. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXTRUMPIRAN&with_nested_markets=true)

## Base rates

- base_rate: trump_2026_foreign_trips_jan_to_sep = 5; window = 2026-01-01..2026-09-30 (Switzerland, China, France, Turkey, Ireland; one country per trip); (as_of: 2026-09-13; source: https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Donald_Trump)

## Resolution notes

- KXTRUMPCOUNTRIES rule text: "If Donald Trump has physically travelled to and been present within the geographic boundaries of [country] after Issuance and before Jan 1, 2027, then the market resolves to Yes." Secondary: "The following do NOT constitute a visit: Flying over the area without landing; Layovers during which the person remains in an airplane; Virtual or remote appearances; Presence in international waters adjacent to the area; Presence solely within embassy or consulate grounds; Plans, announcements, or scheduling of future visits that do not occur during the applicable time period. For the avoidance of doubt, a visit occurs only when the person exits an aircraft, vehicle, vessel, or train within the area, or otherwise physically enters the area not aboard one. Remaining aboard, including during flyovers, drive-throughs, and non-exit refueling stops, does not constitute a visit. Exiting within the area constitutes a visit regardless of duration or method of exit." The event opened Dec. 2, 2025. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXTRUMPCOUNTRIES-27JAN01?with_nested_markets=true)
- KXTRUMPIRAN rule text: "If Donald Trump has physically travelled to and been present within the geographic boundaries of Iran before Jan 1, 2027, then the market resolves to Yes." Secondary: "Physical presence within the geographic boundaries of the area is required. Flying over without landing, layovers during which the person remains in the airplane or airport, virtual or remote appearances, future visit plans, or (unless explicitly specified) presence in adjacent international waters or solely within embassy or consulate grounds do NOT constitute a visit. International airports are considered within the boundaries of their host jurisdiction. A visit that began before the specified time period and is ongoing as of its start does not count; however, if the person departs and re-enters the area during the time period, the re-entry constitutes a new visit and does count." (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXTRUMPIRAN&with_nested_markets=true)

## Related

- [[Politics Knowledge Index]]
- [[intl-iran-markets]]
- [[intl-israel-2026-election]]
- [[policy-greenland-territory]]

## Timeline

- [2026-10-09] Market: Germany 0.17 leads country board; Iran visit 0.033. https://api.elections.kalshi.com/trade-api/v2/events/KXTRUMPCOUNTRIES-27JAN01?with_nested_markets=true
- [2026-10-08] Statement: no US attack on Iran before the midterms; blockade stays. https://www.iranintl.com/en/202610086381
- [2026-10-06] Report: China wants to move the APEC ministerial online. https://www.afr.com/world/asia/china-fuels-tensions-with-partners-over-scaled-down-apec-summit-plans-20261006-p613bu
- [2026-09-21] Report: Putin to attend Shenzhen APEC and skip the US G20. https://www.straitstimes.com/world/europe/putin-plans-to-attend-xis-apec-summit-and-skip-g-20-with-trump
- [2026-09-13] Trip: Ireland. https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Donald_Trump
- [2026-07-08] Trip: NATO summit in Ankara, Turkey. https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Donald_Trump
- [2026-06-17] Trip: G7 in France. https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Donald_Trump
- [2026-05-15] Trip: state visit to China. https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Donald_Trump
- [2026-01-22] Trip: Davos, Switzerland. https://en.wikipedia.org/wiki/List_of_international_presidential_trips_made_by_Donald_Trump
