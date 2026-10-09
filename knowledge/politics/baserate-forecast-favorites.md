---
aliases:
  - "Base Rate: Poll and Forecast Favorites"
tags:
  - politics
  - base-rate
  - polling
  - forecasting
created: 2026-10-09
as_of: 2025-02-17
markets: []
---

# Base Rate: Poll and Forecast Favorites

Back to [[Politics Knowledge Index]]

How often the candidate leading in polls (final 21 days) or favored by a published forecast actually won, by size of lead and rating bucket.

## Claims

- 538's "call" metric counts a poll as correct if the candidate leading in the poll wins the race; the database covers polls in the final 21 days of gubernatorial and congressional general elections since 1998 and presidential primaries and general elections since 2000. (as_of: 2018-05-30; source: https://www.goodreads.com/author_blog_posts/16871327-the-polls-are-all-right)
- Across all years in 538's database, polls got the winner right about 80 percent of the time. (as_of: 2018-05-30; source: https://www.goodreads.com/author_blog_posts/16871327-the-polls-are-all-right)
- In the 2017-18 cycle to date (pre-midterm, specials and primaries), polls called 66 percent of races correctly, the lowest of any cycle in the table; 2007-08 was the highest at 88 percent. (as_of: 2018-05-30; source: https://www.goodreads.com/author_blog_posts/16871327-the-polls-are-all-right)
- Silver: "polls are much more likely to misidentify the winner when they show a close race." (as_of: 2019-11-05; source: https://www.goodreads.com/author_blog_posts/19102010-the-state-of-the-polls-2019)
- In 2024, polls called 70 percent of races correctly, the lowest share in the Silver Bulletin database; presidential general election polls called 63 percent and House polls 66 percent. (as_of: 2025-02-17; source: https://www.natesilver.net/p/so-how-did-the-polls-do-in-2024-its)
- Silver Bulletin: historically, polls showing leads under 3 points call only 56 percent of races correctly, "not much better than a coin flip." (as_of: 2025-02-17; source: https://www.natesilver.net/p/so-how-did-the-polls-do-in-2024-its)
- 538's 2018 midterm forecasts called 482 (Lite), 487 (Classic) and 490 (Deluxe) of 506 House, Senate and governor races correctly, against an expected 92-94 percent; favorites won more often than the probabilities implied. (as_of: 2018-12-04; source: https://www.goodreads.com/author_blog_posts/17660988-how-fivethirtyeight-s-2018-midterm-forecasts-did)
- In 2022, 538's published Deluxe forecast called 32 of 43 "toss-up" and "lean" races correctly (74 percent); the revised Deluxe went 30 of 53 (57 percent). (as_of: 2023-02-02; source: https://www.goodreads.com/author_blog_posts/23368444-how-our-2022-midterm-forecasts-performed)

## Base rates

- base_rate: poll_leader_win_rate_all = 0.80; window = 1998-2018; (as_of: 2018-05-30; source: https://www.goodreads.com/author_blog_posts/16871327-the-polls-are-all-right)
- base_rate: poll_leader_win_rate_senate = 0.83; window = 1998-2018; (as_of: 2018-05-30; source: https://www.goodreads.com/author_blog_posts/16871327-the-polls-are-all-right)
- base_rate: poll_leader_win_rate_governor = 0.83; window = 1998-2018; (as_of: 2018-05-30; source: https://www.goodreads.com/author_blog_posts/16871327-the-polls-are-all-right)
- base_rate: poll_leader_win_rate_house = 0.71; window = 1998-2018; (as_of: 2018-05-30; source: https://www.goodreads.com/author_blog_posts/16871327-the-polls-are-all-right)
- base_rate: poll_leader_win_rate_pres_general = 0.79; window = 2000-2018; (as_of: 2018-05-30; source: https://www.goodreads.com/author_blog_posts/16871327-the-polls-are-all-right)
- base_rate: poll_leader_win_rate_all = 0.79; window = 1998-2019; (as_of: 2019-11-05; source: https://www.goodreads.com/author_blog_posts/19102010-the-state-of-the-polls-2019)
- base_rate: poll_leader_win_rate_lead_0_3 = 0.58; window = 1998-2019; (as_of: 2019-11-05; source: https://www.goodreads.com/author_blog_posts/19102010-the-state-of-the-polls-2019)
- base_rate: poll_leader_win_rate_lead_3_6 = 0.72; window = 1998-2019; (as_of: 2019-11-05; source: https://www.goodreads.com/author_blog_posts/19102010-the-state-of-the-polls-2019)
- base_rate: poll_leader_win_rate_lead_6_10 = 0.86; window = 1998-2019; (as_of: 2019-11-05; source: https://www.goodreads.com/author_blog_posts/19102010-the-state-of-the-polls-2019)
- base_rate: poll_leader_win_rate_lead_10_15 = 0.94; window = 1998-2019; (as_of: 2019-11-05; source: https://www.goodreads.com/author_blog_posts/19102010-the-state-of-the-polls-2019)
- base_rate: poll_leader_win_rate_lead_15_20 = 0.98; window = 1998-2019; (as_of: 2019-11-05; source: https://www.goodreads.com/author_blog_posts/19102010-the-state-of-the-polls-2019)
- base_rate: poll_leader_win_rate_lead_20_plus = 0.99; window = 1998-2019; (as_of: 2019-11-05; source: https://www.goodreads.com/author_blog_posts/19102010-the-state-of-the-polls-2019)
- base_rate: poll_leader_win_rate_lead_0_3 = 0.560; window = 1998-2024; (as_of: 2025-02-17; source: https://datawrapper.dwcdn.net/FIKJW/4/)
- base_rate: poll_leader_win_rate_lead_3_6 = 0.691; window = 1998-2024; (as_of: 2025-02-17; source: https://datawrapper.dwcdn.net/FIKJW/4/)
- base_rate: poll_leader_win_rate_lead_6_10 = 0.858; window = 1998-2024; (as_of: 2025-02-17; source: https://datawrapper.dwcdn.net/FIKJW/4/)
- base_rate: poll_leader_win_rate_lead_10_15 = 0.938; window = 1998-2024; (as_of: 2025-02-17; source: https://datawrapper.dwcdn.net/FIKJW/4/)
- base_rate: poll_leader_win_rate_lead_15_20 = 0.969; window = 1998-2024; (as_of: 2025-02-17; source: https://datawrapper.dwcdn.net/FIKJW/4/)
- base_rate: poll_leader_win_rate_lead_20_plus = 0.995; window = 1998-2024; (as_of: 2025-02-17; source: https://datawrapper.dwcdn.net/FIKJW/4/)
- base_rate: poll_leader_win_rate_all_2024 = 0.70; window = 2024; (as_of: 2025-02-17; source: https://www.natesilver.net/p/so-how-did-the-polls-do-in-2024-its)
- base_rate: fte_lean_favorite_win_rate = 0.83; window = 2018; (as_of: 2018-12-04; source: https://www.goodreads.com/author_blog_posts/17660988-how-fivethirtyeight-s-2018-midterm-forecasts-did)
- base_rate: fte_likely_favorite_win_rate = 0.94; window = 2018; (as_of: 2018-12-04; source: https://www.goodreads.com/author_blog_posts/17660988-how-fivethirtyeight-s-2018-midterm-forecasts-did)
- base_rate: fte_likely_favorite_win_rate = 0.982; n = 56; window = 2022; (as_of: 2023-02-02; source: https://www.goodreads.com/author_blog_posts/23368444-how-our-2022-midterm-forecasts-performed)
- base_rate: fte_solid_favorite_win_rate = 0.997; n = 390; window = 2022; (as_of: 2023-02-02; source: https://www.goodreads.com/author_blog_posts/23368444-how-our-2022-midterm-forecasts-performed)

## Resolution notes

- These are per-poll call rates (each poll in the final 21 days counted separately), pooled across presidential, Senate, House and governor races; they are not poll-average call rates and not split by office within margin buckets. (as_of: 2019-11-05; source: https://www.goodreads.com/author_blog_posts/19102010-the-state-of-the-polls-2019)
- The 2025 margin buckets come from the Silver Bulletin chart "When polls are close, they aren't great at calling races" (presidential primary and presidential, Senate, House and gubernatorial general elections since 1998), published 2025-02-13 and embedded in the 2025-02-17 article. (as_of: 2025-02-17; source: https://datawrapper.dwcdn.net/FIKJW/4/)

## Related

- [[Base Rate: Polling Error]]
- [[Base Rate: Ratings Accuracy]]
- [[Base Rate: Incumbency]]
- [[Base Rate: Special Elections]]

## Timeline

- [2025-02-17] Analysis: Silver Bulletin 2024 polling review; margin-bucket call rates updated through 2024; 2024 call rate 70% (lowest on record). https://www.natesilver.net/p/so-how-did-the-polls-do-in-2024-its
- [2023-02-02] Analysis: 538 review of 2022 midterm forecasts (Silver); canonical https://fivethirtyeight.com/features/how-our-2022-midterm-forecasts-performed/ (mirror used). https://www.goodreads.com/author_blog_posts/23368444-how-our-2022-midterm-forecasts-performed
- [2019-11-05] Analysis: 538 "The State Of The Polls, 2019" with first margin-bucket table; canonical https://fivethirtyeight.com/features/the-state-of-the-polls-2019/ (mirror used). https://www.goodreads.com/author_blog_posts/19102010-the-state-of-the-polls-2019
- [2018-12-04] Analysis: 538 review of 2018 midterm forecasts; canonical https://fivethirtyeight.com/features/how-fivethirtyeights-2018-midterm-forecasts-did/ (mirror used). https://www.goodreads.com/author_blog_posts/17660988-how-fivethirtyeight-s-2018-midterm-forecasts-did
- [2018-05-30] Analysis: 538 "The Polls Are All Right" call rates by office and cycle; canonical https://fivethirtyeight.com/features/the-polls-are-all-right/ (mirror used). https://www.goodreads.com/author_blog_posts/16871327-the-polls-are-all-right
