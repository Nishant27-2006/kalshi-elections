---
aliases:
  - "Misc: Citrini Scenario (AI Macro Crisis)"
tags:
  - politics
  - mechanics
  - economics
created: 2026-10-09
as_of: 2026-10-09
markets:
  - KXCITRINI-28JUL01
---

# Misc: Citrini Scenario (AI Macro Crisis)

Back to [[Politics Knowledge Index]]

Scope: the Citrini Research "2028 Global Intelligence Crisis" scenario, the five macro triggers Kalshi uses to test it (3 of 5 must hit before July 2028), and where each indicator stood on 2026-10-09.

## Claims

- Citrini Research published "The 2028 Global Intelligence Crisis," by James van Geelen and Alap Shah, in February 2026. It is framed as a scenario, not a prediction. (as_of: 2026-02-25; source: https://en.wikipedia.org/wiki/The_2028_Global_Intelligence_Crisis)
- The report went viral and reportedly drove down the stock prices of major tech and financial firms. (as_of: 2026-02-25; source: https://en.wikipedia.org/wiki/The_2028_Global_Intelligence_Crisis)
- In the scenario, US unemployment reaches 10.2% and the S&P 500 falls 38% peak to trough, as AI agents displace white-collar work and "Ghost GDP" fails to circulate through the economy. (as_of: 2026-02-27; source: https://en.wikipedia.org/wiki/The_2028_Global_Intelligence_Crisis)
- The Financial Times called the report's economics "extreme and improbable," and The Economist said it "gets its economics wrong." (as_of: 2026-02-27; source: https://en.wikipedia.org/wiki/The_2028_Global_Intelligence_Crisis)
- The KXCITRINI-28JUL01 market opened (Issuance) at 15:00 UTC on 25 February 2026. (as_of: 2026-02-25; source: https://api.elections.kalshi.com/trade-api/v2/events/KXCITRINI-28JUL01?with_nested_markets=true)
- The S&P 500 closed at 6,946.13 on 25 Feb 2026. A decline of more than 30% from that close means falling below about 4,862. (as_of: 2026-02-25; source: https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?period1=1771804800&period2=1791590400&interval=1d)
- The lowest S&P 500 close since Issuance was 6,343.72 on 30 March 2026, about 8.7% below the Issuance close. The index closed at 7,765.36 on 8 October 2026. (as_of: 2026-10-08; source: https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?period1=1771804800&period2=1791590400&interval=1d)
- The BLS seasonally adjusted unemployment rate (LNS14000000) was 4.2% for September 2026. Every monthly reading from January to September 2026 fell between 4.1% and 4.4%. (as_of: 2026-10-09; source: https://api.bls.gov/publicAPI/v2/timeseries/data/LNS14000000?startyear=2025&endyear=2026)
- The BLS series has no October 2025 unemployment value; that month shows "-". (as_of: 2026-10-09; source: https://api.bls.gov/publicAPI/v2/timeseries/data/LNS14000000?startyear=2025&endyear=2026)
- CPI-U all items, not seasonally adjusted (CUUR0000SA0), was 334.980 in August 2026 against 323.976 in August 2025, about +3.4% year on year. (as_of: 2026-10-09; source: https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2025&endyear=2026)
- Zillow metro ZHVI (all homes, mid-tier, smoothed, seasonally adjusted) changed year on year to August 2026 by: New York +4.7%, Los Angeles +1.2%, San Francisco +2.3%, Chicago +4.9%, Houston -1.9%, Phoenix -1.2%. The trigger is a fall of more than 10%. (as_of: 2026-10-09; source: https://files.zillowstatic.com/research/public_csvs/zhvi/Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv)
- KXCITRINI-28JUL01 was 0.19 bid / 0.21 ask (last 0.18) on about 25.9 million contracts traded. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXCITRINI-28JUL01?with_nested_markets=true)

## Resolution notes

- The market resolves Yes if at least 3 of these 5 conditions occur in a release published after Issuance (25 Feb 2026) and before July 2028: (1) monthly BLS unemployment rate above 10%; (2) S&P 500 more than 30% below its closing level on Issuance; (3) Zillow Home Value Index down more than 10% year on year in any of NYC, LA, San Francisco, Chicago, Houston or Phoenix; (4) the first-release labor share of gross domestic income for any quarter below 50%; (5) CPI-U (all items, not seasonally adjusted) year on year below 0% in any monthly release. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXCITRINI-28JUL01?with_nested_markets=true)
- Settlement sources are BLS, Zillow research data, FRED (series SP500) and BEA GDP/GDI. The market closes and expires at 14:00 UTC on 1 July 2028. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXCITRINI-28JUL01?with_nested_markets=true)
- The rules do not say the three conditions must hold at the same time, only that each occurs in some qualifying release in the window. The rules also do not name a ZHVI variant (tier, smoothing, seasonal adjustment). (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXCITRINI-28JUL01?with_nested_markets=true)

## Related

- [[Policy: Trump Approval (RCP average)]]
- [[Mechanics: Kalshi Political Market Settlement]]

## Timeline

- [2026-10-09] Market: KXCITRINI-28JUL01 at 0.19/0.21. Unemployment 4.2%, CPI +3.4% YoY, no ZHVI metro below -2%. https://api.elections.kalshi.com/trade-api/v2/events/KXCITRINI-28JUL01?with_nested_markets=true
- [2026-03-30] Data: S&P 500 post-Issuance low close of 6,343.72 (-8.7%). https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?period1=1771804800&period2=1791590400&interval=1d
- [2026-02-25] Market: Issuance; S&P 500 closes at 6,946.13. https://api.elections.kalshi.com/trade-api/v2/events/KXCITRINI-28JUL01?with_nested_markets=true
- [2026-02-25] Report: the Citrini report goes viral and moves markets. https://en.wikipedia.org/wiki/The_2028_Global_Intelligence_Crisis
