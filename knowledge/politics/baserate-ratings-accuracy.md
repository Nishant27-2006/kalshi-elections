---
aliases:
  - "Base Rate: Ratings Accuracy"
tags:
  - politics
  - base-rate
  - ratings
created: 2026-10-09
as_of: 2024-05-29
markets: []
---

# Base Rate: Ratings Accuracy

Back to [[Politics Knowledge Index]]

How often races in each Cook / Sabato / 538 rating category went to the favored party.

## Claims

- Campbell evaluated Cook's pre-Labor Day House ratings for 11 elections from 1984 to 2008, leaving out 1986 and 1990. Of districts rated Solid, Likely or Lean Republican, 97.5% (2,056 of 2,108) went Republican. Of those rated Solid, Likely or Lean Democratic, 97.8% (2,309 of 2,361) went Democratic. (as_of: 2010-08-24; source: https://www.acsu.buffalo.edu/~jcampbel/documents/CookAccuracySummary.pdf)
- Campbell found that the Lean category's hit rate swung widely by year. In some cycles a party carried under 70% of its Lean seats: Democrats in 1984, Republicans in 2006 and 2008. (as_of: 2010-08-24; source: https://www.acsu.buffalo.edu/~jcampbel/documents/CookAccuracySummary.pdf)
- Sabato's Crystal Ball reported 2012 results of 31 of 33 Senate races correct, probably 10 of 11 governor races, about 97% of House seats, and 48 of 50 states for president. (as_of: 2012-11-08; source: https://centerforpolitics.org/crystalball/?p=8427)
- Sabato's Crystal Ball reported 2014 results of 476 of 490 called races correct (97%), including 32 of 33 called Senate races and 415 of 423 called House races. (as_of: 2014-11-06; source: https://centerforpolitics.org/crystalball/?p=12953)
- Sabato's Crystal Ball's final 2018 tally was 34 of 35 Senate races correct (missed FL), 423 of 434 House races correct, and 32 of 35 governor races correct (missed FL, IA and OH; GA left as a Toss-up). (as_of: 2018-12-20; source: https://centerforpolitics.org/crystalball/?p=18503)
- Cook says it has rated at least 10,374 races since 1984 across House, Senate, governor and president. Based on final ratings, Lean ratings are right about 94% of the time, Likely about 97%, and Solid almost 100%. (as_of: 2024-04-10; source: https://www.cookpolitical.com/analysis/national/cpr-archives/how-accurate-are-cook-political-reports-race-ratings)
- Of more than 7,000 races Cook rated Solid, only 2 went the other way: LA-02 in 2008 and UT-03 in 1990. (as_of: 2024-04-10; source: https://www.cookpolitical.com/analysis/national/cpr-archives/how-accurate-are-cook-political-reports-race-ratings)
- Across all offices in Cook's archive, Lean R and Likely R ratings were right more often than Lean D and Likely D ratings. Toss-ups split nearly evenly, with Republicans winning the average Toss-up by 0.7 points of two-party vote. (as_of: 2024-04-10; source: https://www.cookpolitical.com/analysis/national/cpr-archives/how-accurate-are-cook-political-reports-race-ratings)
- In 2022, nearly 98% of Cook Toss-ups were decided by under 10 points. (as_of: 2024-04-10; source: https://www.cookpolitical.com/analysis/national/cpr-archives/how-accurate-are-cook-political-reports-race-ratings)
- Half of Cook's missed presidential state calls happened in 2016, when MI, PA and WI were all rated Lean D. (as_of: 2024-04-10; source: https://www.cookpolitical.com/analysis/national/cpr-archives/how-accurate-are-cook-political-reports-race-ratings)
- Split Ticket looked at November generals in 2016-2022, runoffs excluded. Among races Cook rated Toss-up, Sabato picked the winner in 78% in 2018 and in only half in 2022. (as_of: 2024-05-29; source: https://split-ticket.org/2024/05/29/whats-in-a-rating/)
- Split Ticket found that 538's model rated about 40% fewer races Lean or Toss-up than Cook or Sabato. It also found two 538 Solid misses in 2016-2022 (2018 OK-05, 2022 WA-03) and one Crystal Ball Safe miss (the 2022 AK-AL special). (as_of: 2024-05-29; source: https://split-ticket.org/2024/05/29/whats-in-a-rating/)

## Base rates

- base_rate: cook_house_solid_favored_win_rate = 0.998; n = 3387; window = 1984-2008; ratings = pre-Labor Day; (as_of: 2010-08-24; source: https://www.acsu.buffalo.edu/~jcampbel/documents/CookAccuracySummary.pdf)
- base_rate: cook_house_likely_favored_win_rate = 0.949; n = 641; window = 1984-2008; ratings = pre-Labor Day; (as_of: 2010-08-24; source: https://www.acsu.buffalo.edu/~jcampbel/documents/CookAccuracySummary.pdf)
- base_rate: cook_house_lean_favored_win_rate = 0.857; n = 441; window = 1984-2008; ratings = pre-Labor Day; (as_of: 2010-08-24; source: https://www.acsu.buffalo.edu/~jcampbel/documents/CookAccuracySummary.pdf)
- base_rate: cook_house_tossup_incumbent_party_hold_rate_R = 0.55; n = 160; window = 1984-2008; ratings = pre-Labor Day; (as_of: 2010-08-24; source: https://www.acsu.buffalo.edu/~jcampbel/documents/CookAccuracySummary.pdf)
- base_rate: cook_house_tossup_incumbent_party_hold_rate_D = 0.492; n = 130; window = 1984-2008; ratings = pre-Labor Day; (as_of: 2010-08-24; source: https://www.acsu.buffalo.edu/~jcampbel/documents/CookAccuracySummary.pdf)
- base_rate: sabato_called_races_correct_rate_2014 = 0.97; n = 490; window = 2014; (as_of: 2014-11-06; source: https://centerforpolitics.org/crystalball/?p=12953)
- base_rate: sabato_house_correct_rate_2018 = 0.975; n = 434; window = 2018; (as_of: 2018-12-20; source: https://centerforpolitics.org/crystalball/?p=18503)
- base_rate: cook_final_lean_correct_rate = 0.94; n = 10374 total races (all categories); window = 1984-2022, all offices; (as_of: 2024-04-10; source: https://www.cookpolitical.com/analysis/national/cpr-archives/how-accurate-are-cook-political-reports-race-ratings)
- base_rate: cook_final_likely_correct_rate = 0.97; window = 1984-2022, all offices; (as_of: 2024-04-10; source: https://www.cookpolitical.com/analysis/national/cpr-archives/how-accurate-are-cook-political-reports-race-ratings)
- base_rate: cook_final_solid_miss_count = 2; n = 7000+; window = 1984-2022, all offices; (as_of: 2024-04-10; source: https://www.cookpolitical.com/analysis/national/cpr-archives/how-accurate-are-cook-political-reports-race-ratings)
- base_rate: cook_lean_avg_two_party_margin_pts = 10.6; window = 1984-2022; (as_of: 2024-04-10; source: https://www.cookpolitical.com/analysis/national/cpr-archives/how-accurate-are-cook-political-reports-race-ratings)
- base_rate: cook_likely_avg_two_party_margin_pts = 18.2; window = 1984-2022; (as_of: 2024-04-10; source: https://www.cookpolitical.com/analysis/national/cpr-archives/how-accurate-are-cook-political-reports-race-ratings)
- base_rate: sabato_lean_correct_rate = 0.77; window = 2016-2022 November generals; (as_of: 2024-05-29; source: https://split-ticket.org/2024/05/29/whats-in-a-rating/)
- base_rate: fivethirtyeight_lean_correct_rate = 0.78; window = 2016-2022 November generals; (as_of: 2024-05-29; source: https://split-ticket.org/2024/05/29/whats-in-a-rating/)
- base_rate: fivethirtyeight_likely_correct_rate = 0.92; window = 2016-2022 November generals; (as_of: 2024-05-29; source: https://split-ticket.org/2024/05/29/whats-in-a-rating/)

## Resolution notes

- Category definitions differ by rater. Cook's Lean behaves like high confidence, while Sabato's Lean means a "small edge" and Sabato usually removes Toss-ups in its final ratings. A Lean prior should therefore be chosen per rater. (as_of: 2024-05-29; source: https://split-ticket.org/2024/05/29/whats-in-a-rating/)

## Related

- [[Base Rate: Polling Error]]
- [[Base Rate: Poll and Forecast Favorites]]
- [[Base Rate: Incumbency]]

## Timeline

- [2024-05-29] Analysis: Split Ticket compares Cook, Sabato and 538 categories (Sabato Lean 77%, 538 Lean 78% / Likely 92%). https://split-ticket.org/2024/05/29/whats-in-a-rating/
- [2024-04-10] Analysis: Cook's 40-year self-audit (Lean ~94%, Likely ~97%, 2 Solid misses). https://www.cookpolitical.com/analysis/national/cpr-archives/how-accurate-are-cook-political-reports-race-ratings
- [2018-12-20] Analysis: Crystal Ball 2018 final tally (Senate 34/35, House 423/434, Gov 32/35). https://centerforpolitics.org/crystalball/?p=18503
- [2014-11-06] Analysis: Crystal Ball 2014 tally, 476/490. https://centerforpolitics.org/crystalball/?p=12953
- [2012-11-08] Analysis: Crystal Ball 2012 tally (Senate 31/33). https://centerforpolitics.org/crystalball/?p=8427
- [2010-08-24] Paper: Campbell on Cook pre-Labor Day House ratings, 1984-2008. https://www.acsu.buffalo.edu/~jcampbel/documents/CookAccuracySummary.pdf
