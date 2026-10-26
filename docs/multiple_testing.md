## Multiple-comparisons correction

`python -m forecast.multiple_testing`. p-values are approximated from the event-bootstrap CIs (normal approximation; P&L CIs are skewed, so treat as rough). Families are corrected separately.

- Brier: 7 of 37 survive Holm, 30 survive BH (5%).
- P&L: 0 of 31 survive Holm, 0 survive BH (5%).

### Brier family: model minus market (negative = model better) (37 tests)

| test | estimate | CI95 | p (approx) | Holm-adjusted | BH-adjusted | survives Holm 5%? | survives BH 5%? |
|---|---|---|---|---|---|---|---|
| V07 reversion term | -0.00051 | [-0.0007, -0.0003] | 0.0000 | 0.0000 | 0.0000 | yes | yes |
| V05 paper FLB prior (no fit) | -0.0003 | [-0.00046, -0.00016] | 0.0001 | 0.0032 | 0.0016 | yes | yes |
| V02 global Platt (no archetype) | -0.00036 | [-0.00055, -0.00018] | 0.0001 | 0.0048 | 0.0017 | yes | yes |
| V09 sum-to-one normalisation | -0.00034 | [-0.00052, -0.00016] | 0.0002 | 0.0073 | 0.0017 | yes | yes |
| V10 recency: last 365d of train | -0.00096 | [-0.00142, -0.0004] | 0.0002 | 0.0074 | 0.0017 | yes | yes |
| V22 mid-sophistication markets | -0.001 | [-0.00158, -0.00041] | 0.0008 | 0.0258 | 0.0043 | yes | yes |
| tercile composite/mid | -0.001 | [-0.00158, -0.00041] | 0.0008 | 0.0258 | 0.0043 | yes | yes |
| tercile efficiency/low | -0.00108 | [-0.00178, -0.00039] | 0.0023 | 0.0696 | 0.0045 | no | yes |
| B0 old plan Stage A | -0.0008 | [-0.00128, -0.00025] | 0.0023 | 0.0696 | 0.0045 | no | yes |
| V08 blend with market | -0.0008 | [-0.00128, -0.00025] | 0.0023 | 0.0696 | 0.0045 | no | yes |
| V11 min_edge 2c | -0.0008 | [-0.00128, -0.00025] | 0.0023 | 0.0696 | 0.0045 | no | yes |
| V12 min_edge 10c | -0.0008 | [-0.00128, -0.00025] | 0.0023 | 0.0696 | 0.0045 | no | yes |
| V13 edge in logit space | -0.0008 | [-0.00128, -0.00025] | 0.0023 | 0.0696 | 0.0045 | no | yes |
| V14 YES side only | -0.0008 | [-0.00128, -0.00025] | 0.0023 | 0.0696 | 0.0045 | no | yes |
| V15 NO side only | -0.0008 | [-0.00128, -0.00025] | 0.0023 | 0.0696 | 0.0045 | no | yes |
| V16 favourites only (>=50c) | -0.0008 | [-0.00128, -0.00025] | 0.0023 | 0.0696 | 0.0045 | no | yes |
| V17 tails excluded (15-85c) | -0.0008 | [-0.00128, -0.00025] | 0.0023 | 0.0696 | 0.0045 | no | yes |
| V20 maker execution | -0.0008 | [-0.00128, -0.00025] | 0.0023 | 0.0696 | 0.0045 | no | yes |
| V24 zero-fee counterfactual | -0.0008 | [-0.00128, -0.00025] | 0.0023 | 0.0696 | 0.0045 | no | yes |
| tercile efficiency/mid | -0.00106 | [-0.00177, -0.00037] | 0.0030 | 0.0696 | 0.0055 | no | yes |
| V19 mature markets (age>=30d) | -0.00081 | [-0.00135, -0.00025] | 0.0039 | 0.0696 | 0.0069 | no | yes |
| tercile activity/low | -0.00113 | [-0.00189, -0.00032] | 0.0048 | 0.0765 | 0.0080 | no | yes |
| V21 low-sophistication markets | -0.00123 | [-0.0021, -0.00031] | 0.0071 | 0.1060 | 0.0109 | no | yes |
| tercile composite/low | -0.00123 | [-0.0021, -0.00031] | 0.0071 | 0.1060 | 0.0109 | no | yes |
| tercile liquidity/low | -0.00134 | [-0.00235, -0.00028] | 0.0112 | 0.1451 | 0.0165 | no | yes |
| tercile liquidity/mid | -0.00075 | [-0.00138, -0.00019] | 0.0135 | 0.1619 | 0.0192 | no | yes |
| V18 tight books only (spread<=4c) | -0.00052 | [-0.00098, -7e-05] | 0.0251 | 0.2760 | 0.0332 | no | yes |
| V06 microstructure logistic | -0.0005 | [-0.00095, -7e-05] | 0.0259 | 0.2760 | 0.0332 | no | yes |
| tercile activity/high | -0.00088 | [-0.00171, -0.00016] | 0.0260 | 0.2760 | 0.0332 | no | yes |
| tercile liquidity/high | -0.0007 | [-0.00142, -0.00012] | 0.0348 | 0.2783 | 0.0429 | no | yes |
| V25 knowledge-file prior | -0.00026 | [-0.00052, 2e-05] | 0.0591 | 0.4137 | 0.0705 | no | no |
| V03 archetype slope too | -0.0004 | [-0.00105, 0.00034] | 0.2593 | 1.0000 | 0.2998 | no | no |
| V23 high-sophistication markets | -0.00033 | [-0.00105, 0.00037] | 0.3623 | 1.0000 | 0.3943 | no | no |
| tercile composite/high | -0.00033 | [-0.00105, 0.00037] | 0.3623 | 1.0000 | 0.3943 | no | no |
| tercile activity/mid | -0.00025 | [-0.00088, 0.00034] | 0.4218 | 1.0000 | 0.4459 | no | no |
| tercile efficiency/high | -0.00011 | [-0.00083, 0.00069] | 0.7767 | 1.0000 | 0.7982 | no | no |
| V04 isotonic recalibration | 4e-05 | [-0.00038, 0.00035] | 0.8299 | 1.0000 | 0.8299 | no | no |

### P&L family: mean P&L per trade (31 tests)

| test | estimate | CI95 | p (approx) | Holm-adjusted | BH-adjusted | survives Holm 5%? | survives BH 5%? |
|---|---|---|---|---|---|---|---|
| tercile efficiency/low | 0.1775 | [0.0155, 0.3465] | 0.0355 | 1.0000 | 0.8238 | no | no |
| tercile activity/low | 0.184 | [-0.0302, 0.3428] | 0.0531 | 1.0000 | 0.8238 | no | no |
| V18 tight books only (spread<=4c) | 0.1041 | [-0.0275, 0.238] | 0.1243 | 1.0000 | 0.9277 | no | no |
| V21 low-sophistication markets | 0.1558 | [-0.1084, 0.3304] | 0.1640 | 1.0000 | 0.9277 | no | no |
| V09 sum-to-one normalisation | -0.1273 | [-0.2909, 0.1061] | 0.2088 | 1.0000 | 0.9277 | no | no |
| V19 mature markets (age>=30d) | 0.099 | [-0.0567, 0.2678] | 0.2317 | 1.0000 | 0.9277 | no | no |
| V20 maker execution | -0.0162 | [-0.0423, 0.0149] | 0.2669 | 1.0000 | 0.9277 | no | no |
| tercile liquidity/high | 0.0942 | [-0.0599, 0.2747] | 0.2698 | 1.0000 | 0.9277 | no | no |
| V16 favourites only (>=50c) | 0.0585 | [-0.0725, 0.1843] | 0.3719 | 1.0000 | 0.9277 | no | no |
| tercile activity/mid | -0.0644 | [-0.2194, 0.0972] | 0.4252 | 1.0000 | 0.9277 | no | no |
| V15 NO side only | 0.1152 | [-0.1703, 0.3976] | 0.4265 | 1.0000 | 0.9277 | no | no |
| tercile activity/high | 0.0726 | [-0.1122, 0.2529] | 0.4357 | 1.0000 | 0.9277 | no | no |
| V24 zero-fee counterfactual | 0.0361 | [-0.0567, 0.1253] | 0.4368 | 1.0000 | 0.9277 | no | no |
| V22 mid-sophistication markets | 0.0472 | [-0.0836, 0.1877] | 0.4952 | 1.0000 | 0.9277 | no | no |
| tercile composite/low | 0.0859 | [-0.2373, 0.3132] | 0.5408 | 1.0000 | 0.9277 | no | no |
| B0 old plan Stage A | 0.0347 | [-0.0806, 0.1527] | 0.5599 | 1.0000 | 0.9277 | no | no |
| V08 blend with market | 0.0347 | [-0.0806, 0.1527] | 0.5599 | 1.0000 | 0.9277 | no | no |
| V17 tails excluded (15-85c) | 0.0347 | [-0.0806, 0.1527] | 0.5599 | 1.0000 | 0.9277 | no | no |
| V10 recency: last 365d of train | 0.0294 | [-0.0747, 0.1347] | 0.5821 | 1.0000 | 0.9277 | no | no |
| tercile composite/mid | 0.0306 | [-0.1352, 0.1827] | 0.7059 | 1.0000 | 0.9277 | no | no |
| V14 YES side only | 0.0246 | [-0.1056, 0.152] | 0.7081 | 1.0000 | 0.9277 | no | no |
| tercile liquidity/mid | -0.0311 | [-0.1952, 0.1436] | 0.7190 | 1.0000 | 0.9277 | no | no |
| V23 high-sophistication markets | 0.0241 | [-0.1137, 0.1581] | 0.7282 | 1.0000 | 0.9277 | no | no |
| V13 edge in logit space | 0.0117 | [-0.0595, 0.0889] | 0.7573 | 1.0000 | 0.9277 | no | no |
| tercile composite/high | 0.0259 | [-0.1324, 0.2058] | 0.7640 | 1.0000 | 0.9277 | no | no |
| tercile liquidity/low | 0.0377 | [-0.2752, 0.2492] | 0.7781 | 1.0000 | 0.9277 | no | no |
| V11 min_edge 2c | -0.0045 | [-0.0564, 0.0548] | 0.8740 | 1.0000 | 0.9815 | no | no |
| tercile efficiency/mid | 0.0121 | [-0.1475, 0.1849] | 0.8865 | 1.0000 | 0.9815 | no | no |
| V04 isotonic recalibration | 0.0046 | [-0.1208, 0.1404] | 0.9450 | 1.0000 | 0.9839 | no | no |
| V03 archetype slope too | 0.0016 | [-0.072, 0.0698] | 0.9647 | 1.0000 | 0.9839 | no | no |
| tercile efficiency/high | 0.002 | [-0.1764, 0.2131] | 0.9839 | 1.0000 | 0.9839 | no | no |
