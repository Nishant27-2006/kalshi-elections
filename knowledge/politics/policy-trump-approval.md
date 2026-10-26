---
aliases:
  - "Policy: Trump Approval (RCP average)"
tags:
  - politics
  - policy
  - approval
  - trump
created: 2026-10-09
as_of: 2026-10-09
markets:
  - KXTRUMPAPPROVE
  - KXTRUMPAPPROVE-26OCT09
---

# Policy: Trump Approval (RCP average)

Back to [[Politics Knowledge Index]]

Scope: Trump job-approval averages (RealClearPolitics, Silver Bulletin, NYT, Ballotpedia) across 2025-2026, plus how fast the RCP "Approve" number moves, for the daily KXTRUMPAPPROVE bracket markets.

## Claims

- RCP average reached a second-term low of 42.3% approve on Nov. 14, 2025, during the Epstein-emails controversy; NYT's average hit its term low of 41% on Nov. 12. (as_of: 2025-11-26; source: https://www.yahoo.com/news/articles/donald-trumps-approval-rating-see-110607620.html)
- RCP average stood at 43% approve / 54.8% disapprove as of Nov. 25, 2025. (as_of: 2025-11-26; source: https://www.yahoo.com/news/articles/donald-trumps-approval-rating-see-110607620.html)
- RealClearPolling average was 43.8% approve / 52.6% disapprove (net -8.2) for polls from Dec. 9, 2025 to Jan. 11, 2026. (as_of: 2026-01-12; source: https://kogo.iheart.com/content/2026-01-12-trumps-approval-rating-sees-shift)
- RealClearPolling average was 42.6% approve / 54.7% disapprove (net -12.1) for polls from Jan. 8-22, 2026. (as_of: 2026-01-23; source: https://www.iheart.com/content/2026-01-23-trumps-approval-rating-sees-shift/)
- Silver Bulletin net approval was -13.7 as of Feb. 9, 2026, up from -14.6 the prior week; the strong-disapprove share topped 46% for the first time. (as_of: 2026-02-10; source: https://newsweek.com/donald-trump-approval-rating-record-nate-silver-11495027)
- RealClearPolling average was 41.4% approve / 56.6% disapprove (net -15.2) for polls from Mar. 20 to Apr. 12, 2026, up from 40.9% approve the week before. (as_of: 2026-04-13; source: https://www.iheart.com/content/2026-04-13-trumps-current-average-approval-rating-revealed/)
- Reuters/Ipsos put approval at 35% in mid-September 2026, up from a record-low 33% in its Aug. 28-31 poll; 63% disapproved of Trump's proposed $5,000 dividend. (as_of: 2026-09-14; source: https://gvwire.com/2026/09/14/trump-approval-up-from-record-low-but-outlook-sours-for-republicans-reuters-ipsos-poll-finds/)
- RCP "Approve" settled at 39.6% on Sep. 2, 40.0% on Sep. 16 and 40.2% on Sep. 21, 2026 (Kalshi KXTRUMPAPPROVE settlements). (as_of: 2026-09-21; source: https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXTRUMPAPPROVE&limit=1000)
- RCP "Approve" settled at 38.8% on Sep. 24, 2026, down 1.4 points from 40.2% on Sep. 21, the largest short move in the September settlement series. (as_of: 2026-09-24; source: https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXTRUMPAPPROVE&limit=1000)
- Ballotpedia's polling average put September 2026 at the lowest monthly average of the second term: 38% on Sep. 29, ending the month at 39% approve / 60% disapprove; the term high was 54% on Jan. 22, 2025. (as_of: 2026-10-01; source: https://news.ballotpedia.org/2026/10/01/trump-saw-lowest-average-approval-rating-of-his-second-term-in-september/)
- RCP "Approve" settled at 38.8% on Oct. 1, 38.2% on Oct. 3 and Oct. 4, 38.5% on Oct. 5 and Oct. 6, and 38.4% on Oct. 7, 2026. (as_of: 2026-10-07; source: https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXTRUMPAPPROVE&limit=1000)
- RCP average on Oct. 8, 2026 was 38.3% approve / 59.5% disapprove. (as_of: 2026-10-08; source: https://spokesman.com/stories/2026/oct/08/trump-voters-not-excited-for-midterms-as-approval-)
- On Oct. 8, 2026 the NYT average was 37% approve / 60% disapprove and Silver Bulletin was 37.1% / 60.1%, so RCP ran about 1 point above both. (as_of: 2026-10-08; source: https://spokesman.com/stories/2026/oct/08/trump-voters-not-excited-for-midterms-as-approval-)
- On the morning of Oct. 9, 2026, KXTRUMPAPPROVE-26OCT09 "Below 38.1%" traded at 0.84 (bid 0.83 / ask 0.84); the "38.1%" bracket was at 0.07 and every bracket at 38.2% or above was at 0.03 or less. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXTRUMPAPPROVE-26OCT09?with_nested_markets=true)
- The RCP average is a straight average of the polls RCP chooses to include, with no weighting for sample size or recency and no house-effect adjustment; a poll leaves the average when it ages out or the same pollster releases a newer one. (as_of: 2024-04-15; source: https://www.pollyvote.com/pollyvote-election-forecasting/polls/realclearpolitics-poll-average/)

## Base rates

- base_rate: rcp_approve_daily_abs_change_mean = 0.09; n = 25; window = 2026-09-02..2026-10-08 consecutive-day pairs from Kalshi settlements; (as_of: 2026-10-08; source: https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXTRUMPAPPROVE&limit=1000)
- base_rate: rcp_approve_daily_unchanged_share = 0.40; n = 25; window = 2026-09-02..2026-10-08; (as_of: 2026-10-08; source: https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXTRUMPAPPROVE&limit=1000)
- base_rate: rcp_approve_weekly_abs_change_median = 0.5; n = 21; window = 7-day pairs 2026-09-02..2026-10-08 (max 1.5, Sep 21 to Sep 28); (as_of: 2026-10-08; source: https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXTRUMPAPPROVE&limit=1000)

## Resolution notes

- KXTRUMPAPPROVE daily events settle on the RCP average "Approve" value at exactly 1:00 PM ET on the event date; the sole source is the "Approve" column of the "RCP Average" row in the "President Trump Job Approval" table. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXTRUMPAPPROVE-26OCT09?with_nested_markets=true)
- Brackets are 0.1-point wide with open-ended tails ("Below X" / "Above Y"), and the tails move each day. Single brackets (e.g., 38.1%) need the exact one-decimal value. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXTRUMPAPPROVE-26OCT09?with_nested_markets=true)
- The series lists RealClearPolitics (realclearpolling.com/polls/approval/donald-trump/approval-rating) as its settlement source. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/series/KXTRUMPAPPROVE)

## Related

- [[Politics Knowledge Index]]
- [[policy-cabinet-departures]]
- [[policy-impeachment-removal]]
- [[policy-legislation]]

## Timeline

- [2026-10-09] Market: KXTRUMPAPPROVE-26OCT09 "Below 38.1%" at 0.84. https://api.elections.kalshi.com/trade-api/v2/events/KXTRUMPAPPROVE-26OCT09?with_nested_markets=true
- [2026-10-08] Poll avg: RCP 38.3 / 59.5; NYT 37 / 60; Silver Bulletin 37.1 / 60.1. https://spokesman.com/stories/2026/oct/08/trump-voters-not-excited-for-midterms-as-approval-
- [2026-10-03] Settlement: RCP Approve 38.2%, lowest in the Sep-Oct settlement series. https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXTRUMPAPPROVE&limit=1000
- [2026-10-01] Poll avg: Ballotpedia says September was the lowest month of the term (38% on Sep 29). https://news.ballotpedia.org/2026/10/01/trump-saw-lowest-average-approval-rating-of-his-second-term-in-september/
- [2026-09-24] Settlement: RCP Approve 38.8%, down from 40.2% on Sep 21. https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXTRUMPAPPROVE&limit=1000
- [2026-09-14] Poll: Reuters/Ipsos 35%, up from a 33% low (Aug 28-31). https://gvwire.com/2026/09/14/trump-approval-up-from-record-low-but-outlook-sours-for-republicans-reuters-ipsos-poll-finds/
- [2026-04-13] Poll avg: RCP 41.4 / 56.6. https://www.iheart.com/content/2026-04-13-trumps-current-average-approval-rating-revealed/
- [2026-02-10] Poll avg: Silver Bulletin net -13.7. https://newsweek.com/donald-trump-approval-rating-record-nate-silver-11495027
- [2026-01-23] Poll avg: RCP 42.6 / 54.7. https://www.iheart.com/content/2026-01-23-trumps-approval-rating-sees-shift/
- [2025-11-26] Poll avg: RCP 43.0 / 54.8 after a 42.3 low on Nov 14. https://www.yahoo.com/news/articles/donald-trumps-approval-rating-see-110607620.html
