---
aliases:
  - "Nomination: Base Rates"
tags:
  - politics
  - base-rate
  - nomination
  - president
created: 2026-10-09
as_of: 2019-06-18
markets:
  - KXPRESNOMD-28
  - KXPRESNOMR-28
  - KXVPRESNOMR-28
  - KXPRESPARTY-2028
  - KXPRESPERSON-28
---

# Nomination: Base Rates

Back to [[Politics Knowledge Index]]

Scope: historical priors for presidential nomination and party-control markets: early poll leaders, sitting vice presidents, and the "time for change" penalty against a party seeking another term.

## Claims
- Pew found that early GOP front-runners held on to win the nomination in six of seven open Republican contests between 1960 and 2004. (as_of: 2007-02-14; source: https://www.pewresearch.org/politics/2007/02/14/how-reliable-are-the-early-presidential-polls/)
- Pew found that early Democratic poll leaders won four of eight open contests between 1960 and 2004. Exceptions included Gary Hart in 1988 (withdrew over scandal) and Mario Cuomo in 1992 (did not run). (as_of: 2007-02-14; source: https://www.pewresearch.org/politics/2007/02/14/how-reliable-are-the-early-presidential-polls/)
- FiveThirtyEight (Skelley) looked at polls from the year before the primaries in competitive contests from 1972 to 2016. National polls were "relatively good indicators" of the nominee. The correlation with primary vote share was 0.70 for January–June polls and 0.80 for July–December polls. (as_of: 2019-04-24; source: https://fivethirtyeight.com/features/we-analyzed-40-years-of-primary-polls-even-early-on-theyre-fairly-predictive/)
- FiveThirtyEight: of 84 well-known candidates polling below 10% in the first half of the year before the primaries, only Donald Trump went on to win the nomination (1972–2016). (as_of: 2019-04-24; source: https://fivethirtyeight.com/features/we-analyzed-40-years-of-primary-polls-even-early-on-theyre-fairly-predictive/)
- FiveThirtyEight: the only nominees with low name recognition in the first half of the year before the primaries were all Democrats: McGovern 1972, Carter 1976, Dukakis 1988, and Clinton 1992. (as_of: 2019-04-24; source: https://fivethirtyeight.com/features/we-analyzed-40-years-of-primary-polls-even-early-on-theyre-fairly-predictive/)
- FiveThirtyEight found four candidates since 1972 who consistently led national polls at above 20% and still lost the nomination: Muskie 1972, Hart 1988, and Hillary Clinton and Rudy Giuliani in 2008. Giuliani never consistently led in either of the two main early states. (as_of: 2019-06-18; source: https://fivethirtyeight.com/features/bidens-leading-the-primary-race-but-front-runners-dont-always-get-nominated/)
- FiveThirtyEight on 2016: no clear GOP front-runner in the first half of 2015 (Walker and Jeb Bush led a field with seven candidates above 10% adjusted); Trump took the lead in the second half and won. Clinton led the Democratic field at 67% and then 61% and won. (as_of: 2019-04-09; source: https://fivethirtyeight.com/features/what-more-than-40-years-of-early-primary-polls-tell-us-about-2020-part-2/)
- FiveThirtyEight on 2000 and 2012: in 2000 both parties nominated their clear early front-runners, George W. Bush and Vice President Al Gore. In 2012 the GOP returned to nominating its early polling front-runner, Romney. (as_of: 2019-04-09; source: https://fivethirtyeight.com/features/what-more-than-40-years-of-early-primary-polls-tell-us-about-2020-part-2/)
- In June 2019, FiveThirtyEight described Joe Biden as the early front-runner in the 2020 Democratic race, leading national polls and most early-state surveys. (as_of: 2019-06-18; source: https://fivethirtyeight.com/features/bidens-leading-the-primary-race-but-front-runners-dont-always-get-nominated/)
- NPR (Rudin): when the president is not running and the vice president wants the nomination, "it's his for the asking." Nixon (1960), Humphrey (1968), Bush (1988), and Gore (2000) were all nominated. Alben Barkley (1952) was the only recent VP who sought the nomination and failed. (as_of: 2013-05-07; source: https://www.kmuw.org/2013-05-07/joe-biden-has-history-on-his-side-but-little-else-if-hillary-clinton-runs)
- National Constitution Center: across 57 presidential elections, eight sitting vice presidents ran as major-party nominees and only four won the presidency. (as_of: 2015-08-17; source: https://constitutioncenter.org/blog/why-sitting-vice-presidents-dont-fare-well-as-presidential-candidates)
- The Hill: since 1950 a party has had seven chances to hold the White House beyond two consecutive terms (1952, 1960, 1968, 1976, 1988, 2000, 2008) and succeeded only once, in 1988. Four of those elections were very close; the incumbent party's average popular-vote deficit in them was 0.68 points. (as_of: 2015-04-15; source: https://digital-release.thehill.com/?p=238812)

## Base rates
- base_rate: gop_early_poll_leader_wins_open_nomination = 0.857; n = 7; window = 1960-2004; (as_of: 2007-02-14; source: https://www.pewresearch.org/politics/2007/02/14/how-reliable-are-the-early-presidential-polls/)
- base_rate: dem_early_poll_leader_wins_open_nomination = 0.50; n = 8; window = 1960-2004; (as_of: 2007-02-14; source: https://www.pewresearch.org/politics/2007/02/14/how-reliable-are-the-early-presidential-polls/)
- base_rate: nominee_rate_poll_avg_35plus_first_half_prior_year = 0.75; window = 1972-2016; (as_of: 2019-04-24; source: https://fivethirtyeight.com/features/we-analyzed-40-years-of-primary-polls-even-early-on-theyre-fairly-predictive/)
- base_rate: nominee_rate_poll_avg_20to35_first_half_prior_year = 0.36; window = 1972-2016; (as_of: 2019-04-24; source: https://fivethirtyeight.com/features/we-analyzed-40-years-of-primary-polls-even-early-on-theyre-fairly-predictive/)
- base_rate: nominee_rate_poll_avg_10to20_first_half_prior_year = 0.09; window = 1972-2016; (as_of: 2019-04-24; source: https://fivethirtyeight.com/features/we-analyzed-40-years-of-primary-polls-even-early-on-theyre-fairly-predictive/)
- base_rate: nominee_rate_poll_avg_35plus_second_half_prior_year = 0.83; window = 1972-2016; (as_of: 2019-04-24; source: https://fivethirtyeight.com/features/we-analyzed-40-years-of-primary-polls-even-early-on-theyre-fairly-predictive/)
- base_rate: nominee_rate_poll_avg_20to35_second_half_prior_year = 0.25; window = 1972-2016; (as_of: 2019-04-24; source: https://fivethirtyeight.com/features/we-analyzed-40-years-of-primary-polls-even-early-on-theyre-fairly-predictive/)
- base_rate: nominee_rate_high_name_rec_under10_first_half = 0.012; n = 84; window = 1972-2016; (as_of: 2019-04-24; source: https://fivethirtyeight.com/features/we-analyzed-40-years-of-primary-polls-even-early-on-theyre-fairly-predictive/)
- base_rate: sitting_vp_wins_nomination_when_sought_open_seat = 0.80; n = 5; window = 1952-2000; (as_of: 2013-05-07; source: https://www.kmuw.org/2013-05-07/joe-biden-has-history-on-his-side-but-little-else-if-hillary-clinton-runs)
- base_rate: sitting_vp_major_party_nominee_wins_presidency = 0.50; n = 8; window = 1789-2012; (as_of: 2015-08-17; source: https://constitutioncenter.org/blog/why-sitting-vice-presidents-dont-fare-well-as-presidential-candidates)
- base_rate: party_wins_third_consecutive_term = 0.143; n = 7; window = 1952-2008; (as_of: 2015-04-15; source: https://digital-release.thehill.com/?p=238812)

## Resolution notes
- The poll-leader rates above measure polls from the calendar year just before the primaries (for 2028, that is 2027 polling). Polls taken in 2026, more than a year earlier, are further out than these windows, so they are a weaker signal. (as_of: 2019-04-01; source: https://fivethirtyeight.com/features/what-more-than-40-years-of-early-primary-polls-tell-us-about-2020-part-1/)

## Related
- [[nomination-2028-democratic]]
- [[nomination-2028-republican]]
- [[nomination-2028-general]]

## Timeline
- [2019-06-18] Analysis: FiveThirtyEight on how front-runners fail (Muskie, Hart, Clinton, Giuliani). https://fivethirtyeight.com/features/bidens-leading-the-primary-race-but-front-runners-dont-always-get-nominated/
- [2019-04-24] Analysis: FiveThirtyEight, 40 years of primary polls are fairly predictive. https://fivethirtyeight.com/features/we-analyzed-40-years-of-primary-polls-even-early-on-theyre-fairly-predictive/
- [2015-08-17] Analysis: National Constitution Center on sitting VPs as nominees. https://constitutioncenter.org/blog/why-sitting-vice-presidents-dont-fare-well-as-presidential-candidates
- [2015-04-15] Analysis: The Hill, third-term record since 1950. https://digital-release.thehill.com/?p=238812
- [2013-05-07] Analysis: NPR, VPs usually win nominations they seek. https://www.kmuw.org/2013-05-07/joe-biden-has-history-on-his-side-but-little-else-if-hillary-clinton-runs
- [2007-02-14] Analysis: Pew, reliability of early presidential polls. https://www.pewresearch.org/politics/2007/02/14/how-reliable-are-the-early-presidential-polls/
