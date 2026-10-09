---
aliases:
  - "International: Polling Error and Runoff Base Rates"
tags:
  - politics
  - base-rate
  - international
  - polling
created: 2026-10-09
as_of: 2026-10-08
markets:
  - KXBRPRES-26
  - KXFRENCHPRES-27
  - KXISRAELPM-26OCT27
---

# International: Polling Error and Runoff Base Rates

Back to [[Politics Knowledge Index]]

Collects cross-national poll accuracy (Jennings & Wlezien 2018) and how often the first-round leader loses a two-round presidential runoff (Passarelli & Bergman 2022), plus the 2026 Brazil first-round miss as a recent case.

## Claims

- Jennings & Wlezien (Nature Human Behaviour, 2018) analysed 30,916 national polls covering 351 general elections in 45 countries from 1942 to 2017: presidential elections in 23 countries and legislative elections in 31. (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- They found poll error shrinks over the campaign. Mean absolute error per party is close to 4 points at 150-200 days out, about 3 points at 50 days, and under 2 points on the eve of the election. (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- At 200 days out, MAE was about 3.3 points in legislative elections and 5.9 points in presidential elections, a gap that narrows close to Election Day. (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- They found no rise in polling error over time: the mean was 2.1 points in the 1940s-50s, 2.1 in the 1960s-70s and 2.0 since 2000, with a year-error correlation of -0.11 (p = 0.40). (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- For 16 countries with sample-size data, random sampling alone implies a 0.7-point absolute error, against an observed 1.8 points. Most poll error is non-sampling. (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- The errors above are per-party vote-share errors (|poll − vote|), not errors on the lead margin, which run larger. (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- Passarelli & Bergman (Political Studies Review, 2022) built a dataset of 423 two-round presidential elections in 73 countries from 1945 to 2020. They found that no institutional, presidential-resource or first-round-structure variable predicted a runoff comeback. (as_of: 2022-10-28; source: https://iris.uniroma1.it/bitstream/11573/1673986/1/Passarelli_Runoff_2022.pdf)
- In Brazil 2026, Datafolha's final first-round poll (Oct 2-3) had Lula ahead 45-42 on valid votes. (as_of: 2026-10-03; source: https://sbtnews.sbt.com.br/noticia/eleicoes/datafolha-no-1-turno-lula-tem-45-de-validos-e-flavio-42)
- The Brazil 2026 count at 98.62% had Flávio Bolsonaro ahead 47.05-45.13, a swing of about 5 points on the margin from that final Datafolha poll. (as_of: 2026-10-04; source: https://www.congressoemfoco.com.br/noticia/122884/flavio-e-lula-vao-ao-segundo-turno-da-eleicao-presidencial)
- PoderData described Flávio's first-round edge as 1.87 points in the official count. Its first runoff poll had him at 53% of valid votes. (as_of: 2026-10-08; source: https://www.poder360.com.br/poderdata/flavio-tem-53-contra-47-de-lula-no-2o-turno-diz-pesquisa-poderdata-aya/)

## Base rates

- base_rate: intl_poll_mae_final_week_all = 2.03; n = 763; window = 1942-2017; (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- base_rate: intl_poll_mae_final_week_presidential = 2.70; n = 179; window = 1942-2017; (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- base_rate: intl_poll_mae_final_week_legislative = 1.83; n = 584; window = 1942-2017; (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- base_rate: intl_poll_mae_final_week_legislative_pr = 1.62; n = 396; window = 1942-2017; (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- base_rate: intl_poll_mae_final_week_legislative_smd = 2.28; n = 188; window = 1942-2017; (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- base_rate: intl_poll_mae_final_week_large_party_ge20 = 2.28; n = 321; window = 1942-2017; (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- base_rate: intl_poll_mae_final_week_small_party_lt20 = 1.29; n = 263; window = 1942-2017; (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- base_rate: intl_poll_mae_final_week_governing_party = 2.05; n = 216; window = 1942-2017; (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- base_rate: intl_poll_mae_final_week_enp_gt3 = 1.71; n = 424; window = 1942-2017; (as_of: 2018-03-12; source: https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf)
- base_rate: runoff_comeback_rate_all = 0.293; n = 181; window = 1945-2020; (as_of: 2022-10-28; source: https://iris.uniroma1.it/bitstream/11573/1673986/1/Passarelli_Runoff_2022.pdf)
- base_rate: runoff_comeback_rate_latin_america = 0.24; window = 1945-2020; (as_of: 2022-10-28; source: https://iris.uniroma1.it/bitstream/11573/1673986/1/Passarelli_Runoff_2022.pdf)
- base_rate: runoff_comeback_rate_europe = 0.316; window = 1945-2020; (as_of: 2022-10-28; source: https://iris.uniroma1.it/bitstream/11573/1673986/1/Passarelli_Runoff_2022.pdf)
- base_rate: runoff_comeback_rate_africa = 0.216; window = 1945-2020; (as_of: 2022-10-28; source: https://iris.uniroma1.it/bitstream/11573/1673986/1/Passarelli_Runoff_2022.pdf)
- base_rate: runoff_comeback_rate_asia = 0.54; window = 1945-2020; (as_of: 2022-10-28; source: https://iris.uniroma1.it/bitstream/11573/1673986/1/Passarelli_Runoff_2022.pdf)
- base_rate: first_round_decided_share_latin_america = 0.528; n = 106; window = 1945-2020; (as_of: 2022-10-28; source: https://iris.uniroma1.it/bitstream/11573/1673986/1/Passarelli_Runoff_2022.pdf)
- base_rate: first_round_decided_share_europe = 0.313; n = 115; window = 1945-2020; (as_of: 2022-10-28; source: https://iris.uniroma1.it/bitstream/11573/1673986/1/Passarelli_Runoff_2022.pdf)
- base_rate: first_round_decided_share_all = 0.572; n = 423; window = 1945-2020; (as_of: 2022-10-28; source: https://iris.uniroma1.it/bitstream/11573/1673986/1/Passarelli_Runoff_2022.pdf)

## Related

- [[Base Rate: Polling Error]]
- [[Mechanics: Runoffs, Ranked-Choice and Top-Two Systems]]
- [[International: Brazil 2026 Presidential Election]]
- [[International: France 2027 Presidential Election]]
- [[International: Israel 2026 Knesset Election]]

## Timeline

- [2026-10-04] Result: Brazil's first round has Flávio ahead after the final Datafolha poll showed Lula +3. https://www.congressoemfoco.com.br/noticia/122884/flavio-e-lula-vao-ao-segundo-turno-da-eleicao-presidencial
- [2022-10-28] Study: Passarelli & Bergman find runoff comebacks in 29.3% of runoffs. https://iris.uniroma1.it/bitstream/11573/1673986/1/Passarelli_Runoff_2022.pdf
- [2018-03-12] Study: Jennings & Wlezien find a final-week MAE of 2.03 points across 45 countries. https://eprints.soton.ac.uk/421260/1/JenningsWlezien_PollingErrors.pdf
