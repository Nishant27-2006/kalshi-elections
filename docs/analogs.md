# Race analogs and polling-miss patterns

`forecast/analogs.py` finds past Senate and governor races that look like a current one and asks how *their*
polls missed. It was built to test the operator's question: 2022 PA Senate (unpopular, outsider Republican vs a
well-known Democrat) beat its polls for the Democrat. Do races with that profile do so reliably, and which 2026
race looks like it?

```
python -m forecast.analogs validate                    # walk-forward by cycle
python -m forecast.analogs patterns [--control]        # which factors predict misses
python -m forecast.analogs explain 2026-senate-MI --mode literal
python -m forecast.analogs predict --year 2026 --mode literal
```

## Data

`knowledge/politics/data/races_*.csv` holds 218 rows (schema in `RACE_SCHEMA.md`): 188 races from 2016–2024 and
the 30 competitive 2026 Senate and governor races. 138 of the historical rows have a final polling average, so
they have a measured miss. Three research subagents compiled the data from RCP/538 archives, Wikipedia race pages,
FEC files and Ballotpedia, and every row cites URLs. **Caveats:** net favorability is almost empty for 2016–2022
(27 rows filled in total). The candidate flags (well-known, outsider, scandal) are hand-coded judgments explained in
each row's `notes`. Poll averages mix sources (538 > RCP > 270toWin), as noted per row.

## Method

A race's miss (actual − final poll average, D−R) is split into a **cycle part**, the mean miss of every race that
year, and a **race residual**. Candidate factors cannot explain the cycle part, since every race shares it, so
analogs are matched on the residual. Distance is Euclidean over standardized factors: midterm environment,
incumbency, state lean, statewide-win gap, name-recognition gap, outsider gap, scandal gap, Trump endorsement,
favorability gap, log fundraising ratio, closeness, and office. The prediction is the inverse-distance-weighted mean
residual of the 7 nearest earlier races.

Two encodings: **literal** (parties as-is) and **mirrored** (everything re-signed toward the party out of the White
House, so a D-president midterm can match an R-president one).

## Does it work? Walk-forward, each cycle predicted only from earlier cycles

118 out-of-sample races (2018 from 2016; 2020 from 2016–18; 2022 from 2016–20; 2024 from 2016–22):

| mode | MAE of residual | MAE of "no adjustment" | gain, 95% CI | corr | sign right when it commits (>1 pt) |
|---|---|---|---|---|---|
| literal | 3.05 | 3.26 | [+0.01, +0.41] | 0.37 | 71% of 63 |
| mirrored | 3.10 | 3.26 | [−0.03, +0.35] | 0.32 | 69% of 52 |
| state lean only (linear) | 3.06 | 3.26 | [−0.21, +0.63] | 0.43 | – |

Literal analogs beat no adjustment by a small margin that clears zero. Mirrored analogs do not clear it, so being in
the same position relative to the White House does not transfer across parties as cleanly as having similar
candidates and states. The gain is about 0.2 points of MAE: real but small next to the cycle-level miss.

## The biggest pattern is the cycle, not the candidate

| cycle | races with a poll avg | mean miss (D−R) |
|---|---|---|
| 2016 (Trump on ballot) | 20 | −2.8 |
| 2018 (midterm) | 33 | −0.1 |
| 2020 (Trump on ballot) | 18 | −5.3 |
| 2022 (midterm) | 42 | +0.2 |
| 2024 (Trump on ballot) | 25 | −3.1 |

Polls overstated Democrats in all three Trump-on-ballot years and were close to unbiased in both midterms. The
November playbook's section C bet ("2026 polls overstate Democrats here") rests on the presidential-year pattern.
In the two midterms on record it did not hold. n = 2 midterms is thin, but it is the opposite of the playbook's
assumption.

## Which factors predict a race's residual miss?

Raw: incumbents, prior statewide winners, better-known candidates and candidates in friendly states all beat their
polls. These are largely one effect, because those candidates sit in states that lean their way. With the state's
lean and the poll margin netted out first (`patterns --control`; fitted: residual ≈ +1.2 pts per 10 pts of
presidential lean):

| factor (controlled) | n | diff in residual (toward D) | 95% CI | clear? |
|---|---|---|---|---|
| R nominee hit by scandal | 6 | +3.7 | [+2.2, +5.1] | yes (n=6, hand-coded flag) |
| R outraised D 2:1+ | 10 | −3.0 | [−5.2, −0.9] | yes (n=10) |
| R nominee Trump-endorsed in primary | 62 | +1.1 | [−0.0, +2.3] | borderline |
| R nominee is an outsider (the PA-2022 profile) | 42 | +0.5 | [−0.9, +1.9] | no |
| D better known than R | 54 | +0.5 | [−0.7, +1.8] | no |
| everything else | | |≤ 0.8 | no |

19 factors were tested, so about one false positive at 95% is expected by chance; the two "clear" rows rest on 6 and
10 races. **The strongest robust pattern is that polls understate the state's partisan lean** (≈1.2 pts per 10 pts
of lean). On the PA-2022 profile specifically: outsider Republicans beat their polls *less* than the PA case
suggests once lean is accounted for, and the effect is not distinguishable from zero.

**PA 2022 itself:** Fetterman's actual miss was +5.4, of which +5.3 is race-specific (the 2022 cycle mean was +0.2).
Using only 2016–2020 races, the engine predicted +1.5: right direction, about a quarter of the size. Nearest analogs:
2020 MI/MN/MT/NH Senate and 2016 NV/NH/WI Senate.

## 2026 MI Senate, the operator's example

El-Sayed (D) vs Rogers (R), open seat, FiftyPlusOne average D+3.7 (2026-10-09). Rogers matches the "unpopular
Republican" half of the PA profile (net fav −12 vs El-Sayed +1). He is not an outsider, though, and El-Sayed is not
the well-known Democrat: he has never won statewide and is coded as an outsider. So MI 2026 is only half a PA-2022
mirror. The engine's nearest analogs are 2020 AZ-special, 2018 FL, 2024 MI, 2020 TX, 2018 AZ, 2020 IA and 2020 SC
Senate, with a predicted residual of **+0.4 toward D** (spread 2.1). That is no meaningful lean either way.
(Judgment call: the data codes Rogers `well_known = 0` despite his 2024 statewide run. Coding him 1 would move the
match.)

## 2026 vs Kalshi (2026-10-09)

P(D wins) = Φ((poll margin + adjustment + midterm cycle mean 0.05) / σ). σ = 4.56 × 1.25, where 4.56 is the measured
SD of final-poll misses in 2018 + 2022 and **×1.25 is an unmeasured allowance** for the averages being 25 days out.
"Kalshi" is the mid of the D leg (Osborn's leg for NE).

| race | poll D−R | analog adj | lean adj | P polls only | P + analogs | P + lean | Kalshi |
|---|---|---|---|---|---|---|---|
| 2026-senate-AK | +2.9 | +1.1 | -1.6 | 0.70 | 0.76 | 0.60 | 0.735 |
| 2026-senate-FL-special | -5.0 | -1.2 | -1.6 | 0.19 | 0.14 | 0.13 | 0.092 |
| 2026-senate-GA | +9.1 | +1.1 | -0.2 | 0.95 | 0.96 | 0.94 | 0.954 |
| 2026-senate-IA | +1.1 | -0.6 | -1.6 | 0.58 | 0.54 | 0.47 | 0.435 |
| 2026-senate-KS | +1.4 | +0.7 | -1.9 | 0.60 | 0.65 | 0.47 | 0.375 |
| 2026-senate-ME | +2.0 | -2.0 | +0.8 | 0.64 | 0.50 | 0.69 | 0.565 |
| 2026-senate-MI | +3.7 | +0.4 | -0.2 | 0.74 | 0.77 | 0.74 | 0.685 |
| 2026-senate-MN | +2.1 | +1.8 | +0.5 | 0.65 | 0.75 | 0.68 | 0.865 |
| 2026-senate-MT | -24.7 | -3.9 | -2.4 | 0.00 | 0.00 | 0.00 | 0.009 |
| 2026-senate-NC | +9.8 | +0.8 | -0.4 | 0.96 | 0.97 | 0.95 | 0.967 |
| 2026-senate-NE | -0.6 | -0.7 | -2.4 | 0.46 | 0.41 | 0.30 | 0.275 |
| 2026-senate-NH | +6.6 | -0.0 | +0.3 | 0.88 | 0.88 | 0.89 | 0.890 |
| 2026-senate-OH-special | +3.7 | -0.1 | -1.3 | 0.74 | 0.74 | 0.66 | 0.615 |
| 2026-senate-SC | -1.6 | -0.7 | -2.1 | 0.39 | 0.35 | 0.26 | 0.145 |
| 2026-senate-TX | +3.3 | +2.5 | -1.6 | 0.72 | 0.85 | 0.62 | 0.655 |
| 2026-governor-AZ | +6.4 | -0.7 | -0.7 | 0.87 | 0.84 | 0.85 | 0.875 |
| 2026-governor-FL | -2.3 | +1.6 | -1.6 | 0.35 | 0.45 | 0.25 | 0.235 |
| 2026-governor-GA | -1.4 | -0.8 | -0.2 | 0.41 | 0.35 | 0.39 | 0.455 |
| 2026-governor-IA | +9.3 | +1.0 | -1.6 | 0.95 | 0.96 | 0.91 | 0.875 |
| 2026-governor-KS | -3.6 | +0.3 | -1.9 | 0.27 | 0.28 | 0.17 | – |
| 2026-governor-ME | +11.6 | +1.7 | +0.8 | 0.98 | 0.99 | 0.99 | 0.944 |
| 2026-governor-MI | +7.5 | +0.9 | -0.2 | 0.91 | 0.93 | 0.90 | 0.921 |
| 2026-governor-MN | +9.6 | +1.5 | +0.5 | 0.95 | 0.97 | 0.96 | 0.952 |
| 2026-governor-NH | -9.3 | -0.1 | +0.3 | 0.05 | 0.05 | 0.06 | – |
| 2026-governor-NV | -0.8 | +1.8 | -0.4 | 0.45 | 0.57 | 0.42 | 0.505 |
| 2026-governor-NY | +11.9 | +1.3 | +1.5 | 0.98 | 0.99 | 0.99 | 0.952 |
| 2026-governor-OH | +4.0 | -0.9 | -1.3 | 0.76 | 0.71 | 0.68 | 0.705 |
| 2026-governor-PA | +21.6 | +0.9 | -0.2 | 1.00 | 1.00 | 1.00 | 0.977 |
| 2026-governor-TX | -2.4 | +0.5 | -1.6 | 0.34 | 0.37 | 0.24 | 0.255 |
| 2026-governor-WI | +2.9 | +1.9 | -0.1 | 0.70 | 0.80 | 0.69 | 0.805 |

Mean absolute gap to Kalshi: polls only 7.8c, polls + analogs 7.7c, polls + lean 5.2c (mean signed gap −0.1c).
**The market already prices the "polls understate the state's lean" effect.** Most of the large disagreements
between a polls-based model and Kalshi (KS, SC, NE Senate; TX and FL governor) shrink once lean is included, so they
are not edges. The lean-adjusted model still differs from the market by 10c+ in a few races; those are leads to
check, not trades. Nothing here has been backtested against market prices: the analog model has 2016–2024 outcome
history but no matching Kalshi price history, since Kalshi political markets were thin before 2024.

Races where the lean-adjusted model and Kalshi differ by ≥10c: AK Senate (model 0.60 vs 0.735), ME Senate (0.69
vs 0.565), MN Senate (0.68 vs 0.865), SC Senate (0.26 vs 0.145), WI governor (0.69 vs 0.805). In four of the five,
the market is more confident than polls plus lean. A wider σ than the market's implied one is the likeliest single
explanation, so read these as "the model is less sure", not as directional edges.
