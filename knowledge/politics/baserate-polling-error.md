---
aliases:
  - "Base Rate: Polling Error"
tags:
  - politics
  - base-rate
  - polling
created: 2026-10-09
as_of: 2025-02-17
markets: []
---

# Base Rate: Polling Error

Back to [[Politics Knowledge Index]]

How far late polls miss the final margin, by race type, cycle and timing, and which way the miss has leaned.

## Claims

- 538's pollster-ratings database covers polls in the final 21 days of governor and congressional races since 1998 and presidential primaries and generals since 2000, more than 8,500 polls in all. (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- 538 found that error on the margin grows down the ballot (House > Senate/governor > president) and that primary polling error is much larger than general-election error. (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- 538 found that polls in the final 7 days miss by 5.5 points on average, against 5.9 for polls in the final 21 days, so late gains in accuracy are modest. (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- In 538's 1998-2018 data, statistical bias moved from cycle to cycle: R+4.3 in 1998, D+2.2 in 2001-02, R+2.5 in 2011-12, D+2.6 in 2013-14, D+3.0 in 2015-16 and R+2.3 in 2017-18 (combined, all race types). (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- AAPOR's 2016 task force found that 2016 national polls had an average absolute error of 2.2 points on the margin (signed error 1.3). State presidential polls had an average absolute error of 5.1 points, with a signed error of 3.0 toward Clinton. (as_of: 2017-05-04; source: https://aapor.org/wp-content/uploads/2023/01/AAPOR-2016-Election-Polling-Report.pdf)
- AAPOR 2016 reported that 2012 national polls had an average absolute error of 2.9 points and that the 1936-2016 average for national polls is 4.4 points. In 2000 and 2012, state polls overestimated the Republican by about 2 points. (as_of: 2017-05-04; source: https://aapor.org/wp-content/uploads/2023/01/AAPOR-2016-Election-Polling-Report.pdf)
- AAPOR's 2020 task force found that 2020 polling error was the highest in 40 years for the national popular vote. It was also the highest in at least 20 years for state-level presidential, Senate and governor estimates. (as_of: 2021-07-19; source: https://aapor.org/wp-content/uploads/2022/11/AAPOR-Task-Force-on-2020-Pre-Election-Polling_Report-FNL.pdf)
- AAPOR 2020: in polls from the final two weeks, the average absolute error on the margin was 4.5 points nationally and 5.1 points for state presidential polls. The signed error favored Biden by 3.9 points nationally and 4.3 points in state polls. (as_of: 2021-07-19; source: https://aapor.org/wp-content/uploads/2022/11/AAPOR-Task-Force-on-2020-Pre-Election-Polling_Report-FNL.pdf)
- AAPOR 2020: Senate and governor polls combined were on average 6.0 points too favorable to Democrats on the margin, which is more than the presidential overstatement. (as_of: 2021-07-19; source: https://aapor.org/wp-content/uploads/2022/11/AAPOR-Task-Force-on-2020-Pre-Election-Polling_Report-FNL.pdf)
- 538: from 1972 to 2020, the final 538 national polling average missed the popular-vote margin by 2.3 points on average. 538's model treats about 3 points as a normal-sized national miss. (as_of: 2020-11-11; source: https://fivethirtyeight.com/features/the-polls-werent-great-but-thats-pretty-normal/)
- 538 found that Senate and governor polls taken in the first six months of an election year (1998-2021) had essentially no partisan bias overall: R+0.1 for Senate and R+0.02 for governor. (as_of: 2022-03-22; source: https://fivethirtyeight.com/features/why-early-senate-and-governor-polls-have-plenty-to-tell-us-about-november/)
- 538 said 2021-22 polling was the most accurate cycle in its database since 1998, with a weighted-average error of 4.8 and bias of D+0.8. Generic-ballot polls made up 46% of that cycle's House polls, against 21% across all cycles. (as_of: 2023-03-10; source: https://fivethirtyeight.com/features/2022-election-polling-accuracy/)
- Silver Bulletin found that 2024 polls underestimated Republicans for a third straight presidential cycle. Bias was about 3 points toward Democrats in presidential, Senate and House polls and about 2 points in governor polls. (as_of: 2025-02-17; source: https://www.natesilver.net/p/so-how-did-the-polls-do-in-2024-its)

## Base rates

- base_rate: avg_abs_poll_error_all_races_final21d = 5.9; n = 8500+ polls; window = 1998-2018; (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- base_rate: avg_abs_poll_error_pres_primary_final21d = 8.7; window = 2000-2016; (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- base_rate: avg_abs_poll_error_pres_primary_2016 = 10.1; window = 2015-16; (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- base_rate: avg_abs_poll_error_pres_general_final21d = 4.0; window = 2000-2016; (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- base_rate: avg_abs_poll_error_pres_state_polls_final21d = 4.8; window = 1972-2016; (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- base_rate: avg_abs_poll_error_pres_national_polls_final21d = 4.1; window = 1972-2016; (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- base_rate: avg_abs_poll_error_governor_final21d = 5.4; window = 1998-2018; (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- base_rate: avg_abs_poll_error_senate_final21d = 5.4; window = 1998-2018; (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- base_rate: avg_abs_poll_error_house_final21d = 6.2; window = 1998-2018; (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- base_rate: poll_leader_win_rate_all_races_final21d = 0.79; window = 1998-2018; (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- base_rate: avg_poll_bias_toward_D_all_races_final21d = 0.3; window = 1998-2018; (as_of: 2018-05-30; source: https://fivethirtyeight.com/features/the-polls-are-all-right/)
- base_rate: avg_abs_poll_error_senate_early_jan_jun = 8.2; n = 261 races; window = 1998-2021; (as_of: 2022-03-22; source: https://fivethirtyeight.com/features/why-early-senate-and-governor-polls-have-plenty-to-tell-us-about-november/)
- base_rate: avg_abs_poll_error_governor_early_jan_jun = 8.6; n = 225 races / 994 polls; window = 1998-2021; (as_of: 2022-03-22; source: https://fivethirtyeight.com/features/why-early-senate-and-governor-polls-have-plenty-to-tell-us-about-november/)
- base_rate: avg_abs_poll_error_sen_gov_final3wk = 5.4; window = 1998-2020; (as_of: 2022-03-22; source: https://fivethirtyeight.com/features/why-early-senate-and-governor-polls-have-plenty-to-tell-us-about-november/)
- base_rate: avg_abs_poll_error_all_races_final21d = 6.0; window = 1998-2022; (as_of: 2023-03-10; source: https://fivethirtyeight.com/features/2022-election-polling-accuracy/)
- base_rate: avg_abs_poll_error_pres_primary_final21d = 9.2; window = 2000-2020; (as_of: 2023-03-10; source: https://fivethirtyeight.com/features/2022-election-polling-accuracy/)
- base_rate: avg_abs_poll_error_pres_primary_2020 = 10.2; window = 2019-20; (as_of: 2023-03-10; source: https://fivethirtyeight.com/features/2022-election-polling-accuracy/)
- base_rate: avg_abs_poll_error_house_generic_ballot = 3.9; window = 1998-2022; (as_of: 2023-03-10; source: https://fivethirtyeight.com/features/2022-election-polling-accuracy/)
- base_rate: avg_abs_poll_error_house_district_polls = 6.7; window = 1998-2022; (as_of: 2023-03-10; source: https://fivethirtyeight.com/features/2022-election-polling-accuracy/)
- base_rate: avg_poll_bias_toward_D_all_races_2019_20 = 4.7; window = 2019-20; (as_of: 2023-03-10; source: https://fivethirtyeight.com/features/2022-election-polling-accuracy/)
- base_rate: avg_poll_bias_toward_D_all_races_final21d = 1.0; window = 1998-2022; (as_of: 2023-03-10; source: https://fivethirtyeight.com/features/2022-election-polling-accuracy/)
- base_rate: avg_abs_poll_error_all_races_2023_24 = 4.5; window = 2023-24; (as_of: 2025-02-17; source: https://www.natesilver.net/p/so-how-did-the-polls-do-in-2024-its)
- base_rate: avg_abs_poll_error_pres_general_2024 = 3.4; window = 2023-24; (as_of: 2025-02-17; source: https://www.natesilver.net/p/so-how-did-the-polls-do-in-2024-its)
- base_rate: avg_abs_poll_error_senate_2024 = 4.1; window = 2023-24; (as_of: 2025-02-17; source: https://www.natesilver.net/p/so-how-did-the-polls-do-in-2024-its)
- base_rate: avg_poll_bias_toward_D_all_races_2024 = 2.9; window = 2023-24; (as_of: 2025-02-17; source: https://www.natesilver.net/p/so-how-did-the-polls-do-in-2024-its)

## Resolution notes

- 538 and Silver Bulletin measure error as the absolute difference between a poll's margin and the actual margin between the top two finishers. Bias is the signed version, computed only for D-vs-R races. Both use polls whose median field date falls in the final 21 days, weighted by 1/sqrt(polls per firm). (as_of: 2023-03-10; source: https://fivethirtyeight.com/features/2022-election-polling-accuracy/)

## Related

- [[Base Rate: Poll and Forecast Favorites]]
- [[Base Rate: Ratings Accuracy]]
- [[Base Rate: Primaries]]
- [[Base Rate: Midterm Penalty]]

## Timeline

- [2025-02-17] Analysis: Silver Bulletin 2024 polling review: 4.5-pt error, lowest on record; D+2.9 bias. https://www.natesilver.net/p/so-how-did-the-polls-do-in-2024-its
- [2023-03-10] Analysis: 538 says 2021-22 was the most accurate polling cycle since 1998 (4.8-pt error, D+0.8). https://fivethirtyeight.com/features/2022-election-polling-accuracy/
- [2022-03-22] Analysis: 538 on early (Jan-Jun) Senate and governor polls: 8.2/8.6-pt error, no net bias. https://fivethirtyeight.com/features/why-early-senate-and-governor-polls-have-plenty-to-tell-us-about-november/
- [2021-07-19] Report: AAPOR 2020 task force finds the largest national error in 40 years, with polls too favorable to Biden by 3.9 nationally and 4.3 in state polls. https://aapor.org/wp-content/uploads/2022/11/AAPOR-Task-Force-on-2020-Pre-Election-Polling_Report-FNL.pdf
- [2020-11-11] Analysis: 538 says the 2020 miss was about 4 pts nationally, and the 1972-2020 average national miss was 2.3. https://fivethirtyeight.com/features/the-polls-werent-great-but-thats-pretty-normal/
- [2018-05-30] Analysis: 538 "The Polls Are All Right": 5.9-pt average error since 1998; primaries 8.7. https://fivethirtyeight.com/features/the-polls-are-all-right/
- [2017-05-04] Report: AAPOR 2016 task force finds national error of 2.2 and state error of 5.1. https://aapor.org/wp-content/uploads/2023/01/AAPOR-2016-Election-Polling-Report.pdf
