---
aliases:
  - "Mechanics: Kalshi Political Market Settlement"
  - "Political Settlement Rules"
tags:
  - politics
  - mechanics
  - resolution
  - kalshi
created: 2026-10-09
as_of: 2026-10-09
markets:
  - SENATEGA-26
  - CONTROLS-2026
  - CONTROLH-2026
  - KXHOUSERACE-MN01-26
  - KXHOUSEPOPVOTEMARGIN-27NOV03
  - KXCLOSESTSENATE-27JAN03
  - PRES-2024
  - POPVOTE-24
  - CONTROLH-2024
  - CONTROLS-2024
  - SENATEPA-24
  - HOUSECA45-24
---

# Mechanics: Kalshi Political Market Settlement

Back to [[Politics Knowledge Index]]

Scope: how Kalshi election and party-control contracts settle (sworn-in and inauguration triggers, media-call accelerated determination, certification-based margin and placement contracts, withdrawal, replacement, recount, tie and void handling), taken from rule text pulled with read-only GETs and from Kalshi's CFTC filings and help center.

## Claims

### Seat and chamber winner contracts (2026 cycle)
- SENATEGA-26-D `rules_primary` reads: "If a representative of the Democratic party is sworn in as a Senator of Georgia for the term beginning in 2027, then the market resolves to Yes." (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/markets?event_ticker=SENATEGA-26)
- SENATEGA-26 `rules_secondary` reads: "This market is eligible for accelerated determination after a consensus of media organizations project the winner. See full rules for details." (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/markets?event_ticker=SENATEGA-26)
- SENATEGA-26 has `can_close_early: true`, expected expiration 2027-01-04T15:00Z, latest expiration 2027-11-03T15:00Z, and event-level `settlement_sources` = United States Congress (congress.gov). (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/SENATEGA-26?with_nested_markets=true)
- The SENATEPARTY contract terms set accelerated resolution when (A) at least 4 of 8 Designated Media Sources (NYT, AP, DDHQ, CNN, Fox News, NBC News, CBS News, ABC News) have declared a winner and (B) none has issued a contradictory declaration. (as_of: 2026-10-09; source: https://assets.kalshi.com/contract_terms/SENATEPARTY.pdf)
- Under those terms, a "declaration" is either a formal decision-desk projection or "an unambiguous statement in a news article that the candidate/party/option has won". A network and all its local affiliates count as one source, and a national-desk call overrides an affiliate's call. (as_of: 2026-10-09; source: https://assets.kalshi.com/contract_terms/SENATEPARTY.pdf)
- Without accelerated determination, SENATEPARTY expires at the first 10:00 AM ET after the Senator for the seat is sworn in, or one year after the popular vote, whichever comes first. (as_of: 2026-10-09; source: https://assets.kalshi.com/contract_terms/SENATEPARTY.pdf)
- SENATEPARTY pays on the party of the first person who presents a certificate of election and is sworn in. If a Senator-elect leaves the seat before being seated, the party of the first temporary or permanent replacement sworn in decides it. A party switch between election day and swearing-in resolves on the election-day party. (as_of: 2026-10-09; source: https://assets.kalshi.com/contract_terms/SENATEPARTY.pdf)
- KXHOUSERACE-MN01-26-D resolves on the party of "the House member sworn in for MN-01 for the term beginning in 2027" and carries the same accelerated-determination `rules_secondary` as the Senate seat markets. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXHOUSERACE-MN01-26?with_nested_markets=true)
- CONTROLH-2026 and CONTROLS-2026 `rules_secondary` say the market "may be determined early based on a consensus of media calls projecting control". Otherwise it is decided by the party of the Speaker (House) or the President pro tempore (Senate) on February 1, 2027. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/CONTROLH-2026?with_nested_markets=true)
- The CONTROL contract terms use the same 4-of-8 Designated Media Source rule and make the Expiration Date February 1 of the year the new Congress term begins. (as_of: 2026-10-09; source: https://assets.kalshi.com/contract_terms/CONTROL.pdf)

### Certification-based and scalar contracts
- KXHOUSEPOPVOTEMARGIN-27NOV03 settles on the Clerk of the House election statistics. Its bucket ranges include the lower bound and exclude the upper bound, with "No rounding". The latest expiration is 2028-02-01. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXHOUSEPOPVOTEMARGIN-27NOV03?with_nested_markets=true)
- KXCLOSESTSENATE-27JAN03 measures the final-round margin for ranked-choice races. It uses preliminary results if official results are missing by the deadline but at least 95% of the expected vote is counted. Ties to the hundredth of a point split the payout. Postponed races, or races without enough results, resolve No. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/KXCLOSESTSENATE-27JAN03?with_nested_markets=true)
- Kalshi's ELECTIONPLACE (finishing-place) terms settle on certified results. A candidate who withdraws or is disqualified after the filing deadline but stays on the ballot is settled on their certified vote. If the election is cancelled, postponed past the date, or has no certified results by expiration, every market resolves No. (as_of: 2026-07-13; source: https://www.cftc.gov/filings/orgrules/rules0713269597.pdf)
- Kalshi's ELECTIONMOV (margin of victory) terms say that a recount which changes the certified percentage after the first certification but before expiration is settled on "the most recent certified percentage". (as_of: 2026-08-13; source: https://www.cftc.gov/filings/orgrules/rules08132616689.pdf)
- The ELECTIONMOV "Fully Conducted" clause covers an election held in full whose results are nullified or not certified by expiration. It does not resolve No. It settles on the most recent unofficial Source Agency results that cover at least 95% of votes cast. (as_of: 2026-09-10; source: https://www.cftc.gov/filings/orgrules/rules09102624601.pdf)
- The amended ELECTIONMOV terms let a margin strike resolve early once 4 of 8 Designated Media Sources make declarations that settle whether that strike's Yes condition is definitively met or definitively cannot be met. Otherwise the latest expiration is one year after the election, moved earlier once certified results are published. (as_of: 2026-09-10; source: https://www.cftc.gov/filings/orgrules/rules09102624601.pdf)

### Nominee contracts: withdrawal and replacement
- Kalshi's GENERICNOM nominee terms do not count a "presumptive," "likely," or "expected" nominee as the Nominee. Only a convention nomination, government certification, or selection by an authorized party committee counts. (as_of: 2026-07-06; source: https://www.cftc.gov/filings/ptc/ptc0706269047.pdf)
- Under GENERICNOM, "If <person> becomes the Nominee and is later replaced, such replacement shall not affect Contract resolution". If a named person dies before expiration, Kalshi may settle at the last traded price from before the death. (as_of: 2026-07-06; source: https://www.cftc.gov/filings/ptc/ptc0706269047.pdf)

### 2024 precedents (inauguration and sworn-in triggers)
- Decrypt reported that Polymarket's presidential market resolves when AP, Fox News, and NBC News all call the race for the same candidate, falling back to inauguration if they have not agreed by January 20. Kalshi used inauguration alone. (as_of: 2024-11-04; source: https://decrypt.co/290121/where-prediction-markets-draw-line-trump-harris-win)
- Joe Biden announced his withdrawal on July 21, 2024, and Harris became the formal nominee on August 5, 2024. PRES-2024 strikes were written as "<candidate> or another representative of the <party> party", so a substitution inside the party did not change the settlement condition. (as_of: 2024-08-05; source: https://en.wikipedia.org/wiki/Withdrawal_of_Joe_Biden_from_the_2024_United_States_presidential_election)
- PRES-2024-DJT settled Yes at 2025-01-20T18:04Z on the condition "inaugurated as President for the term beginning January 20, 2025". The event's `rules_secondary` was empty, meaning no media-call acceleration. (as_of: 2025-01-20; source: https://api.elections.kalshi.com/trade-api/v2/historical/markets?event_ticker=PRES-2024)
- SENATEPA-24-R and HOUSECA45-24-D settled at about 2025-01-03T20:20Z, the day the new Congress was sworn in. Their `rules_secondary` was empty. (as_of: 2025-01-03; source: https://api.elections.kalshi.com/trade-api/v2/historical/markets?event_ticker=SENATEPA-24)
- CONTROLH-2024-R and CONTROLS-2024-R settled Yes at about 2025-02-01T16:00Z, using the Feb 1 Speaker and President pro tempore test with no early media-call clause. (as_of: 2025-02-01; source: https://api.elections.kalshi.com/trade-api/v2/historical/markets?event_ticker=CONTROLH-2024)
- POPVOTE-24 closed early and settled at 2025-01-06T19:16Z under an early-close condition of "If the Underlying data has been released". (as_of: 2025-01-06; source: https://api.elections.kalshi.com/trade-api/v2/historical/markets?event_ticker=POPVOTE-24)

### Help-center context
- Kalshi's help center says the displayed close time "may not equal determination time". It also says "A market remaining open is not an indication that payout criteria have not been met". (as_of: 2026-04-12; source: https://help.kalshi.com/en/articles/13823821-market-faqs)

## Resolution notes
- Two settlement families now apply. Seat and chamber contracts (SENATEPARTY, CONTROL, KXHOUSERACE) can settle on 4-of-8 media calls, and otherwise wait for swearing-in or the Feb 1 leadership test. Margin, placement, and closest-race contracts settle on certified results, with recount, tie, and 95%-unofficial fallbacks. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/events/SENATEGA-26?with_nested_markets=true)
- The 2024 seat, control, and presidential markets had no acceleration clause and settled 2 to 12 weeks after election day. Lockup on 2024 analogs is not representative of the 2026 rules. (as_of: 2026-10-09; source: https://api.elections.kalshi.com/trade-api/v2/historical/markets?event_ticker=CONTROLS-2024)

## Related
- [[mechanics-runoffs-rcv-top-two]]
- [[mechanics-vote-count-timing]]
- [[cycle-2024-general-results]]
- [[Market Mechanics: Kalshi Settlement Sources – Certification vs Media Call]]

## Timeline
- [2026-10-09] Rules: SENATEGA-26, CONTROLH/S-2026, KXHOUSERACE, KXCLOSESTSENATE rule text pulled via GET https://api.elections.kalshi.com/trade-api/v2/events/SENATEGA-26?with_nested_markets=true
- [2026-09-10] Filing: ELECTIONMOV amended with Fully-Conducted and media-declaration accelerated resolution https://www.cftc.gov/filings/orgrules/rules09102624601.pdf
- [2026-08-13] Filing: ELECTIONMOV terms (recount, tie) https://www.cftc.gov/filings/orgrules/rules08132616689.pdf
- [2026-07-13] Filing: ELECTIONPLACE terms (withdrawal, no-certification → No) https://www.cftc.gov/filings/orgrules/rules0713269597.pdf
- [2026-07-06] Filing: GENERICNOM nominee contract (presumptive ≠ nominee; replacement) https://www.cftc.gov/filings/ptc/ptc0706269047.pdf
- [2026-03-02] News: Kalshi licenses AP election data https://cdcgaming.com/brief/kalshi-licenses-election-data-from-the-associated-press
- [2025-02-01] Settlement: CONTROLH-2024 / CONTROLS-2024 settle R https://api.elections.kalshi.com/trade-api/v2/historical/markets?event_ticker=CONTROLH-2024
- [2025-01-20] Settlement: PRES-2024 settles at inauguration https://api.elections.kalshi.com/trade-api/v2/historical/markets?event_ticker=PRES-2024
- [2025-01-06] Settlement: POPVOTE-24 settles R https://api.elections.kalshi.com/trade-api/v2/historical/markets?event_ticker=POPVOTE-24
- [2025-01-03] Settlement: 2024 Senate/House seat markets settle on swearing-in https://api.elections.kalshi.com/trade-api/v2/historical/markets?event_ticker=SENATEPA-24
- [2024-11-04] News: Kalshi inauguration vs Polymarket media-consensus rules https://decrypt.co/290121/where-prediction-markets-draw-line-trump-harris-win
- [2024-07-21] Event: Biden withdraws https://en.wikipedia.org/wiki/Withdrawal_of_Joe_Biden_from_the_2024_United_States_presidential_election
