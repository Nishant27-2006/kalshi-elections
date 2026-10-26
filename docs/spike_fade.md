# Spike fade backtest

`python -m forecast.spike_fade`. Daily candles of resolved political markets. A spike = one-day mid move >= the threshold, spread <= 10c, mid 5-95c after the move, volume >= 2x its 14-day median (unless stated), first spike per market. Decision at the spike day's close. P&L per $1 contract, net of the taker fee 0.07*P*(1-P) and the spread; CI = event bootstrap. Train = events closing before the held-out cutoff; test = the locked most recent 30% (spikes on or after the cutoff). Variants were fixed before the test set was read.

| variant | train trades | train P&L/trade [CI95] | train hit | TEST trades | TEST P&L/trade [CI95] | TEST hit | notes |
|---|---|---|---|---|---|---|---|
| S0 fade, taker, hold to settlement | 3337 (1554 ev) | -3.1c [-4.7, -1.6] | 38% | 906 (448 ev) | -3.0c [-6.2, -0.2] | 34% | Base case. |
| S1 follow (momentum), taker, hold | 3337 (1554 ev) | -4.3c [-5.8, -2.7] | 62% | 906 (448 ev) | -3.6c [-6.4, -0.4] | 66% | The opposite bet. |
| S2 fade, exit after 7 days | 3337 (1554 ev) | -6.0c [-7.0, -5.0] | 28% | 906 (448 ev) | -4.8c [-7.0, -2.5] | 28% | Pays the spread and fee twice. |
| S3 fade, 15c spikes only | 2346 (1220 ev) | -1.2c [-2.9, +0.8] | 35% | 661 (363 ev) | -1.6c [-5.2, +2.2] | 32% |  |
| S4 fade, no volume condition | 4204 (1794 ev) | -3.5c [-4.7, -2.1] | 35% | 1173 (496 ev) | -3.5c [-6.0, -0.9] | 32% |  |
| S5 fade, maker limit order at the spike close | 1886 (1072 ev) | +1.4c [-0.7, +3.4] | 38% | 529 (315 ev) | +0.7c [-3.1, +4.4] | 32% | Rest a sell at the spiked side's ask; filled only if the next day trades through it. No maker fee on political series. |
| S6 fade longshot spikes (post-spike mid <= 30c) | 1319 (860 ev) | -2.2c [-4.4, -0.1] | 33% | 345 (245 ev) | -3.0c [-6.5, +0.5] | 27% |  |
| S7 fade favourite spikes (post-spike mid >= 70c) | 642 (516 ev) | -3.7c [-6.8, -0.2] | 24% | 209 (165 ev) | -1.8c [-7.3, +4.2] | 23% |  |
| S8 maker fade, no knowledge note in prior 7 days | 1409 (830 ev) | +1.4c [-0.7, +3.8] | 39% | 323 (218 ev) | +0.9c [-4.1, +6.2] | 34% | Code only: retrieval finds no note dated in the week before the spike. |
| S9 maker fade, knowledge note(s) in prior 7 days | 477 (324 ev) | +1.1c [-2.6, +5.1] | 34% | 206 (135 ev) | +0.2c [-4.6, +5.5] | 30% | Code only: at least one retrieved note is dated in the week before (may or may not be relevant). |
| J1 maker fade, Jev says notes do NOT explain the spike | n=0 (too few) |  |  | n=0 (too few) |  |  | Needs data_cache/spike_jev.jsonl. NOT RUN: no Jev answers yet. |
| J2 follow, taker, Jev says notes explain the spike | n=0 (too few) |  |  | n=0 (too few) |  |  | Needs data_cache/spike_jev.jsonl. NOT RUN: no Jev answers yet. |
