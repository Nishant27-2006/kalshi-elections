---
aliases:
  - "Policy: Supreme Court Vacancies and Cases"
tags:
  - politics
  - policy
  - base-rate
  - supreme-court
created: 2026-10-09
as_of: 2026-10-09
markets:
  - KXALITOOUT
  - KXSCOURT-29
  - KXSCOTUSCASE
---

# Policy: Supreme Court Vacancies and Cases

Back to [[Politics Knowledge Index]]

Scope: justices' ages and tenure, historical timing of departures, Alito-retirement and next-justice pricing, and the KXSCOTUSCASE single-case markets.

## Claims

- Clarence Thomas, born June 23, 1948, took his seat Oct. 23, 1991. He is the oldest and longest-serving sitting justice (78 in October 2026). (as_of: 2026-10-09; source: https://www.supremecourt.gov/about/biographies.aspx)
- Samuel Alito, born Apr. 1, 1950, took his seat Jan. 31, 2006 (76 in October 2026). (as_of: 2026-10-09; source: https://www.supremecourt.gov/about/biographies.aspx)
- Sonia Sotomayor, born June 25, 1954, took her seat Aug. 8, 2009 (72 in October 2026). (as_of: 2026-10-09; source: https://www.supremecourt.gov/about/biographies.aspx)
- Chief Justice John Roberts, born Jan. 27, 1955, took his seat Sep. 29, 2005 (71 in October 2026). (as_of: 2026-10-09; source: https://www.supremecourt.gov/about/biographies.aspx)
- The other five justices were born 1960 or later: Kagan (Apr. 28, 1960), Kavanaugh (Feb. 12, 1965), Gorsuch (Aug. 29, 1967), Jackson (Sep. 14, 1970), Barrett (Jan. 28, 1972). (as_of: 2026-10-09; source: https://www.supremecourt.gov/about/biographies.aspx)
- The last vacancy was Breyer's retirement, effective June 30, 2022. No justice left the Court in 2025 or through Oct. 6, 2026. (as_of: 2026-10-06; source: https://en.wikipedia.org/wiki/List_of_justices_of_the_Supreme_Court_of_the_United_States)
- In Learning Resources v. Trump (Feb. 20, 2026), the Court ruled 6-3 against the administration's IEEPA tariffs. (as_of: 2026-02-20; source: https://en.wikipedia.org/wiki/Learning_Resources,_Inc._v._Trump)
- Kalshi settled KXALITOOUT-26SEP01 (Alito retires before Sep 1, 2026) No, so there was no end-of-term 2026 retirement. (as_of: 2026-09-01; source: https://api.elections.kalshi.com/trade-api/v2/events/KXALITOOUT?with_nested_markets=true)
- KXALITOOUT on Oct. 9, 2026: before Jan 1, 2027 last 0.07 (bid 0.042 / ask 0.069); before Jul 1, 2027 last 0.25 (bid 0.27 / ask 0.32). The market prices the June 2027 end of term as the main retirement window. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXALITOOUT?with_nested_markets=true)
- KXSCOURT-29 (next justice confirmed by Jan 20, 2029) on Oct. 9, 2026: Andrew Oldham 0.21, James Ho 0.14, Aileen Cannon 0.11 (bid 0.071 / ask 0.099), Amul Thapar 0.061, Neomi Rao 0.017. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXSCOURT-29?with_nested_markets=true)
- KXSCOTUSCASE-RNCMIF28 (Court allows Arizona's proof-of-citizenship and pre-election noncitizen-removal rules in RNC v. Mi Familia Vota) last 0.69 (bid 0.60 / ask 0.70) on Oct. 9, 2026. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXSCOTUSCASE-RNCMIF28?with_nested_markets=true)
- KXSCOTUSCASE-DHSDVD28 (Court rules for DHS on third-country removals in DHS v. D.V.D.) last 0.70 on Oct. 9, 2026. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXSCOTUSCASE-DHSDVD28?with_nested_markets=true)
- KXSCOTUSCASE-SUNCOM26 (federal law bars Boulder's state-law climate claims against Suncor and Exxon) last 0.68 on Oct. 9, 2026. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXSCOTUSCASE-SUNCOM26?with_nested_markets=true)

## Base rates

- base_rate: associate_justice_voluntary_departures_effective_jun_to_aug = 0.78; n = 9; window = 1990-2022 (Brennan, White, Blackmun, Souter, Stevens, Kennedy, Breyer in Jun-Aug; Marshall Oct 1, 1991 and O'Connor Jan 31, 2006 outside); (as_of: 2022-06-30; source: https://www.supremecourt.gov/about/members_text.aspx)
- base_rate: associate_justice_departures_by_death_share = 0.18; n = 11; window = 1990-2022 (Scalia Feb 13, 2016; Ginsburg Sep 18, 2020); (as_of: 2022-06-30; source: https://www.supremecourt.gov/about/members_text.aspx)
- base_rate: years_since_last_vacancy = 4.3; window = 2022-06-30..2026-10-09; (as_of: 2026-10-06; source: https://en.wikipedia.org/wiki/List_of_justices_of_the_Supreme_Court_of_the_United_States)

## Resolution notes

- KXALITOOUT resolves on the effective date of the resignation, not the announcement. Death may settle at the last fair price. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXALITOOUT?with_nested_markets=true)
- KXSCOURT-29 resolves on the first person confirmed by the Senate as a Justice by Jan. 20, 2029, not on who is nominated. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXSCOURT-29?with_nested_markets=true)
- O'Connor's 2005 retirement was announced effective on confirmation of her successor, so her effective date (Jan. 31, 2006) came seven months after the July 1, 2005 announcement. (as_of: 2006-01-31; source: https://en.wikipedia.org/wiki/Samuel_Alito)

## Related

- [[Politics Knowledge Index]]
- [[policy-legislation]]
- [[policy-impeachment-removal]]

## Timeline

- [2026-10-09] Market: Alito out before Jul 2027 at 0.25; Oldham leads next justice at 0.21. https://api.elections.kalshi.com/trade-api/v2/events/KXALITOOUT?with_nested_markets=true
- [2026-09-01] Settlement: no Alito retirement before Sep 1, 2026. https://api.elections.kalshi.com/trade-api/v2/events/KXALITOOUT?with_nested_markets=true
- [2026-02-20] Ruling: IEEPA tariffs struck 6-3. https://en.wikipedia.org/wiki/Learning_Resources,_Inc._v._Trump
- [2022-06-30] Vacancy: Breyer retirement effective. https://www.supremecourt.gov/about/members_text.aspx
