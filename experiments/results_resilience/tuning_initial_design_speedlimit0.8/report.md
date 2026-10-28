# Resilience benchmark report — `tuning_default`

_Machine-generated from the measured per-run results; no value is edited by hand._

- seeds (5): [100, 101, 102, 103, 104]
- duration per run: 18.0 s, dt = 0.05 s
- arms: pidr, adaptive_legacy, adaptive_supervisor, sup_observe_only, sup_no_ff, sup_no_speedlimit, sup_no_avoid
- scenarios: nominal, blackout_3s, blackout_maneuver, random_loss_30
- runs: 140 (0 failed or halted)

## Scenario definitions

- **nominal** — no injected fault (default channel only)
- **blackout_3s** — 3 s total blackout at t=5 s (the original benchmark)
- **blackout_maneuver** — 3 s blackout at t=5 s while the leader stops and turns abruptly
- **random_loss_30** — independent 30 % extra packet loss, t=4-12 s

## Arm definitions

- **pidr** — PID + dead-reckoning of the leader (baseline)
- **adaptive_legacy** — adaptive_comm, no supervisor (quality-threshold feed-forward scaling only)
- **adaptive_supervisor** — adaptive_comm + resilience supervisor (default fallback)
- **sup_observe_only** — supervisor runs but all caution modifiers are neutral (ablation control)
- **sup_no_ff** — supervisor without feed-forward scaling
- **sup_no_speedlimit** — supervisor without speed limit
- **sup_no_avoid** — supervisor without avoidance boost

## Scenario `nominal` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| pidr | 1.493 ± 0.008 | 2.176 ± 0.010 | 1.086 ± 0.025 | 0.00 | n/a | 1.423 | n/a | n/a (n=0) | n/a | n/a |
| adaptive_legacy | 1.573 ± 0.019 | 2.346 ± 0.023 | 1.115 ± 0.018 | 0.00 | n/a | 1.470 | n/a | n/a (n=0) | n/a | n/a |
| adaptive_supervisor | 1.620 ± 0.043 | 2.417 ± 0.077 | 1.027 ± 0.103 | 0.00 | n/a | 1.487 | n/a | n/a (n=0) | 1.9 | 0.00 |
| sup_observe_only | 1.573 ± 0.019 | 2.346 ± 0.023 | 1.115 ± 0.018 | 0.00 | n/a | 1.469 | n/a | n/a (n=0) | 1.9 | 0.00 |
| sup_no_ff | 1.618 ± 0.045 | 2.414 ± 0.078 | 1.025 ± 0.106 | 0.00 | n/a | 1.491 | n/a | n/a (n=0) | 1.9 | 0.00 |
| sup_no_speedlimit | 1.575 ± 0.017 | 2.350 ± 0.020 | 1.121 ± 0.024 | 0.00 | n/a | 1.469 | n/a | n/a (n=0) | 1.9 | 0.00 |
| sup_no_avoid | 1.620 ± 0.043 | 2.417 ± 0.077 | 1.027 ± 0.103 | 0.00 | n/a | 1.487 | n/a | n/a (n=0) | 1.9 | 0.00 |

## Scenario `blackout_3s` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| pidr | 1.535 ± 0.007 | 2.251 ± 0.008 | 1.065 ± 0.022 | 0.00 | 1.357 | 1.427 | 0/5 | n/a (n=0) | n/a | n/a |
| adaptive_legacy | 1.659 ± 0.019 | 2.516 ± 0.024 | 1.150 ± 0.019 | 0.00 | 1.461 | 1.479 | 0/5 | n/a (n=0) | n/a | n/a |
| adaptive_supervisor | 1.805 ± 0.016 | 2.905 ± 0.022 | 0.781 ± 0.028 | 0.00 | 1.488 | 1.513 | 0/5 | n/a (n=0) | 4.3 | 2.14 |
| sup_observe_only | 1.642 ± 0.018 | 2.475 ± 0.023 | 1.106 ± 0.019 | 0.00 | 1.467 | 1.480 | 0/5 | n/a (n=0) | 4.3 | 2.14 |
| sup_no_ff | 1.805 ± 0.023 | 2.915 ± 0.058 | 0.758 ± 0.020 | 0.00 | 1.485 | 1.497 | 0/5 | n/a (n=0) | 4.3 | 2.14 |
| sup_no_speedlimit | 1.649 ± 0.019 | 2.496 ± 0.023 | 1.131 ± 0.017 | 0.00 | 1.459 | 1.471 | 0/5 | n/a (n=0) | 4.3 | 2.14 |
| sup_no_avoid | 1.805 ± 0.016 | 2.905 ± 0.022 | 0.781 ± 0.028 | 0.00 | 1.488 | 1.513 | 0/5 | n/a (n=0) | 4.3 | 2.14 |

## Scenario `blackout_maneuver` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| pidr | 1.208 ± 0.007 | 1.971 ± 0.008 | 0.322 ± 0.049 | 2.17 | 0.407 | 0.407 | 5/5 | 7.880 (n=5) | n/a | n/a |
| adaptive_legacy | 1.252 ± 0.016 | 2.012 ± 0.016 | 0.877 ± 0.010 | 0.00 | 0.286 | 0.286 | 5/5 | 7.900 (n=5) | n/a | n/a |
| adaptive_supervisor | 1.347 ± 0.014 | 2.231 ± 0.023 | 0.854 ± 0.012 | 0.00 | 0.295 | 0.295 | 5/5 | 7.780 (n=5) | 4.3 | 2.14 |
| sup_observe_only | 1.254 ± 0.015 | 2.007 ± 0.020 | 0.834 ± 0.019 | 0.00 | 0.307 | 0.307 | 5/5 | 7.970 (n=5) | 4.3 | 2.14 |
| sup_no_ff | 1.346 ± 0.014 | 2.238 ± 0.014 | 0.827 ± 0.021 | 0.00 | 0.302 | 0.302 | 5/5 | 7.810 (n=5) | 4.3 | 2.14 |
| sup_no_speedlimit | 1.251 ± 0.016 | 1.985 ± 0.019 | 0.860 ± 0.014 | 0.00 | 0.297 | 0.297 | 5/5 | 7.930 (n=5) | 4.3 | 2.14 |
| sup_no_avoid | 1.347 ± 0.014 | 2.231 ± 0.023 | 0.854 ± 0.012 | 0.00 | 0.295 | 0.295 | 5/5 | 7.780 (n=5) | 4.3 | 2.14 |

## Scenario `random_loss_30` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| pidr | 1.493 ± 0.008 | 2.177 ± 0.010 | 1.086 ± 0.026 | 0.00 | 1.310 | 1.419 | 0/5 | n/a (n=0) | n/a | n/a |
| adaptive_legacy | 1.574 ± 0.019 | 2.346 ± 0.021 | 1.118 ± 0.019 | 0.00 | 1.412 | 1.467 | 0/5 | n/a (n=0) | n/a | n/a |
| adaptive_supervisor | 1.691 ± 0.037 | 2.502 ± 0.074 | 0.945 ± 0.084 | 0.00 | 1.541 | 1.542 | 0/5 | n/a (n=0) | 1.7 | 0.00 |
| sup_observe_only | 1.573 ± 0.019 | 2.347 ± 0.023 | 1.115 ± 0.018 | 0.00 | 1.412 | 1.464 | 0/5 | n/a (n=0) | 1.7 | 0.00 |
| sup_no_ff | 1.686 ± 0.039 | 2.497 ± 0.075 | 0.924 ± 0.088 | 0.00 | 1.540 | 1.542 | 0/5 | n/a (n=0) | 1.7 | 0.00 |
| sup_no_speedlimit | 1.578 ± 0.017 | 2.353 ± 0.021 | 1.132 ± 0.013 | 0.00 | 1.415 | 1.473 | 0/5 | n/a (n=0) | 1.7 | 0.00 |
| sup_no_avoid | 1.691 ± 0.037 | 2.502 ± 0.074 | 0.945 ± 0.084 | 0.00 | 1.541 | 1.542 | 0/5 | n/a (n=0) | 1.7 | 0.00 |

`n/a` = metric not applicable (e.g. recovery without a finite fault window, supervisor statistics for controllers without a supervisor). Recovery time is averaged over recovered runs only; the recovered column shows how many runs satisfied the sustained-recovery criterion (unchanged from `simulation/metrics.py`).

## Strengths and weaknesses per arm (computed)

- **pidr** — strengths: formation RMSE [m] (rank 1/7), peak formation error [m] (rank 1/7), mean |dv_cmd| per step [m/s] (rank 1/7), mean |dw_cmd| per step [rad/s] (rank 1/7); weaknesses: minimum separation [m] (rank 6/7), collision samples [%] (rank 7/7).
- **adaptive_legacy** — strengths: minimum separation [m] (rank 1/7), collision samples [%] (rank 1/7); weaknesses: mean |dv_cmd| per step [m/s] (rank 6/7), mean control effort (rank 6/7).
- **adaptive_supervisor** — strengths: collision samples [%] (rank 2/7), mean control effort (rank 1/7); weaknesses: formation RMSE [m] (rank 6/7).
- **sup_observe_only** — strengths: formation RMSE [m] (rank 2/7), peak formation error [m] (rank 2/7); weaknesses: mean |dw_cmd| per step [rad/s] (rank 6/7), mean control effort (rank 7/7).
- **sup_no_ff** — strengths: mean |dv_cmd| per step [m/s] (rank 2/7), mean |dw_cmd| per step [rad/s] (rank 2/7); weaknesses: peak formation error [m] (rank 7/7), minimum separation [m] (rank 7/7).
- **sup_no_speedlimit** — strengths: minimum separation [m] (rank 2/7); weaknesses: mean |dv_cmd| per step [m/s] (rank 7/7), mean |dw_cmd| per step [rad/s] (rank 7/7).
- **sup_no_avoid** — strengths: mean control effort (rank 2/7); weaknesses: formation RMSE [m] (rank 7/7), peak formation error [m] (rank 6/7), collision samples [%] (rank 6/7).

_Ranks are by the mean over scenarios of each scenario's seed-mean; they are descriptive, not significance tests._

## Paired comparisons (same seeds, other − reference)

Verdict rules: `*_significant` needs paired-t p < 0.05 and ≥ 80 % of seeds moving in the same direction; otherwise `*_inconclusive`. p-values are uncorrected for the 140 comparisons shown, and n is small — treat them as indicative.

| scenario | metric | reference → other | mean diff | improved/worsened seeds | p (t) | p (Wilcoxon) | verdict |
|---|---|---|---|---|---|---|---|
| nominal | RMSE | adaptive_legacy → adaptive_supervisor | 0.0472 | 0/5 of 5 | 0.0608 | 0.0625 | worse_inconclusive |
| nominal | Peak | adaptive_legacy → adaptive_supervisor | 0.0707 | 0/5 of 5 | 0.0960 | 0.0625 | worse_inconclusive |
| nominal | MinSep | adaptive_legacy → adaptive_supervisor | -0.0885 | 1/4 of 5 | 0.1052 | 0.1875 | worse_inconclusive |
| nominal | final_error_m | adaptive_legacy → adaptive_supervisor | 0.0177 | 0/5 of 5 | 0.1209 | 0.0625 | worse_inconclusive |
| nominal | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | -0.0065 | 3/2 of 5 | 0.1872 | 0.3125 | better_inconclusive |
| nominal | RMSE | pidr → adaptive_supervisor | 0.1276 | 0/5 of 5 | 0.0024 | 0.0625 | worse_significant |
| nominal | Peak | pidr → adaptive_supervisor | 0.2406 | 0/5 of 5 | 0.0021 | 0.0625 | worse_significant |
| nominal | MinSep | pidr → adaptive_supervisor | -0.0595 | 2/3 of 5 | 0.2692 | 0.4375 | worse_inconclusive |
| nominal | final_error_m | pidr → adaptive_supervisor | 0.0641 | 0/5 of 5 | 0.0063 | 0.0625 | worse_significant |
| nominal | cmd_dv_mean | pidr → adaptive_supervisor | 0.0801 | 0/5 of 5 | 0.0001 | 0.0625 | worse_significant |
| nominal | RMSE | sup_observe_only → adaptive_supervisor | 0.0471 | 0/5 of 5 | 0.0615 | 0.0625 | worse_inconclusive |
| nominal | Peak | sup_observe_only → adaptive_supervisor | 0.0706 | 0/5 of 5 | 0.0967 | 0.0625 | worse_inconclusive |
| nominal | MinSep | sup_observe_only → adaptive_supervisor | -0.0886 | 1/4 of 5 | 0.1053 | 0.1875 | worse_inconclusive |
| nominal | final_error_m | sup_observe_only → adaptive_supervisor | 0.0179 | 1/4 of 5 | 0.1849 | 0.1875 | worse_inconclusive |
| nominal | cmd_dv_mean | sup_observe_only → adaptive_supervisor | -0.0065 | 3/2 of 5 | 0.1901 | 0.3125 | better_inconclusive |
| nominal | RMSE | adaptive_supervisor → sup_no_ff | -0.0021 | 3/2 of 5 | 0.1733 | 0.3125 | better_inconclusive |
| nominal | Peak | adaptive_supervisor → sup_no_ff | -0.0029 | 4/1 of 5 | 0.1959 | 0.1875 | better_inconclusive |
| nominal | MinSep | adaptive_supervisor → sup_no_ff | -0.0015 | 2/2 of 5 | 0.7549 | 1.0000 | worse_inconclusive |
| nominal | final_error_m | adaptive_supervisor → sup_no_ff | 0.0039 | 3/2 of 5 | 0.4835 | 0.8125 | worse_inconclusive |
| nominal | cmd_dv_mean | adaptive_supervisor → sup_no_ff | -0.0001 | 2/3 of 5 | 0.8786 | 1.0000 | better_inconclusive |
| nominal | RMSE | adaptive_supervisor → sup_no_speedlimit | -0.0456 | 5/0 of 5 | 0.0672 | 0.0625 | better_inconclusive |
| nominal | Peak | adaptive_supervisor → sup_no_speedlimit | -0.0670 | 5/0 of 5 | 0.1113 | 0.0625 | better_inconclusive |
| nominal | MinSep | adaptive_supervisor → sup_no_speedlimit | 0.0944 | 4/0 of 5 | 0.1084 | 0.1250 | better_inconclusive |
| nominal | final_error_m | adaptive_supervisor → sup_no_speedlimit | -0.0182 | 4/1 of 5 | 0.1187 | 0.1875 | better_inconclusive |
| nominal | cmd_dv_mean | adaptive_supervisor → sup_no_speedlimit | 0.0065 | 2/3 of 5 | 0.1888 | 0.4375 | worse_inconclusive |
| nominal | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| nominal | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| nominal | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| nominal | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| nominal | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| nominal | RMSE | pidr → adaptive_legacy | 0.0804 | 0/5 of 5 | 0.0001 | 0.0625 | worse_significant |
| nominal | Peak | pidr → adaptive_legacy | 0.1699 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| nominal | MinSep | pidr → adaptive_legacy | 0.0291 | 4/1 of 5 | 0.1433 | 0.1875 | better_inconclusive |
| nominal | final_error_m | pidr → adaptive_legacy | 0.0463 | 0/5 of 5 | 0.0006 | 0.0625 | worse_significant |
| nominal | cmd_dv_mean | pidr → adaptive_legacy | 0.0866 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_3s | RMSE | adaptive_legacy → adaptive_supervisor | 0.1457 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_3s | Peak | adaptive_legacy → adaptive_supervisor | 0.3893 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_3s | MinSep | adaptive_legacy → adaptive_supervisor | -0.3690 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_3s | final_error_m | adaptive_legacy → adaptive_supervisor | 0.0338 | 1/4 of 5 | 0.1541 | 0.1250 | worse_inconclusive |
| blackout_3s | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | -0.0174 | 5/0 of 5 | 0.0005 | 0.0625 | better_significant |
| blackout_3s | RMSE | pidr → adaptive_supervisor | 0.2701 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_3s | Peak | pidr → adaptive_supervisor | 0.6543 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_3s | MinSep | pidr → adaptive_supervisor | -0.2841 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_3s | final_error_m | pidr → adaptive_supervisor | 0.0859 | 0/5 of 5 | 0.0204 | 0.0625 | worse_significant |
| blackout_3s | cmd_dv_mean | pidr → adaptive_supervisor | 0.0632 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_3s | RMSE | sup_observe_only → adaptive_supervisor | 0.1630 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_3s | Peak | sup_observe_only → adaptive_supervisor | 0.4303 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_3s | MinSep | sup_observe_only → adaptive_supervisor | -0.3245 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_3s | final_error_m | sup_observe_only → adaptive_supervisor | 0.0328 | 2/3 of 5 | 0.2629 | 0.3125 | worse_inconclusive |
| blackout_3s | cmd_dv_mean | sup_observe_only → adaptive_supervisor | -0.0202 | 5/0 of 5 | 0.0003 | 0.0625 | better_significant |
| blackout_3s | RMSE | adaptive_supervisor → sup_no_ff | 0.0000 | 4/1 of 5 | 0.9972 | 0.6250 | worse_inconclusive |
| blackout_3s | Peak | adaptive_supervisor → sup_no_ff | 0.0102 | 4/1 of 5 | 0.7179 | 0.6250 | worse_inconclusive |
| blackout_3s | MinSep | adaptive_supervisor → sup_no_ff | -0.0233 | 0/5 of 5 | 0.0108 | 0.0625 | worse_significant |
| blackout_3s | final_error_m | adaptive_supervisor → sup_no_ff | -0.0156 | 5/0 of 5 | 0.0170 | 0.0625 | better_significant |
| blackout_3s | cmd_dv_mean | adaptive_supervisor → sup_no_ff | -0.0082 | 5/0 of 5 | 0.1734 | 0.0625 | better_inconclusive |
| blackout_3s | RMSE | adaptive_supervisor → sup_no_speedlimit | -0.1563 | 5/0 of 5 | 0.0000 | 0.0625 | better_significant |
| blackout_3s | Peak | adaptive_supervisor → sup_no_speedlimit | -0.4090 | 5/0 of 5 | 0.0000 | 0.0625 | better_significant |
| blackout_3s | MinSep | adaptive_supervisor → sup_no_speedlimit | 0.3500 | 5/0 of 5 | 0.0000 | 0.0625 | better_significant |
| blackout_3s | final_error_m | adaptive_supervisor → sup_no_speedlimit | -0.0423 | 4/1 of 5 | 0.1904 | 0.1250 | better_inconclusive |
| blackout_3s | cmd_dv_mean | adaptive_supervisor → sup_no_speedlimit | 0.0200 | 0/5 of 5 | 0.0006 | 0.0625 | worse_significant |
| blackout_3s | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| blackout_3s | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| blackout_3s | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| blackout_3s | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| blackout_3s | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| blackout_3s | RMSE | pidr → adaptive_legacy | 0.1244 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_3s | Peak | pidr → adaptive_legacy | 0.2650 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_3s | MinSep | pidr → adaptive_legacy | 0.0848 | 5/0 of 5 | 0.0054 | 0.0625 | better_significant |
| blackout_3s | final_error_m | pidr → adaptive_legacy | 0.0521 | 0/5 of 5 | 0.0084 | 0.0625 | worse_significant |
| blackout_3s | cmd_dv_mean | pidr → adaptive_legacy | 0.0806 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_maneuver | RMSE | adaptive_legacy → adaptive_supervisor | 0.0951 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_maneuver | Peak | adaptive_legacy → adaptive_supervisor | 0.2191 | 0/5 of 5 | 0.0001 | 0.0625 | worse_significant |
| blackout_maneuver | MinSep | adaptive_legacy → adaptive_supervisor | -0.0228 | 0/5 of 5 | 0.0260 | 0.0625 | worse_significant |
| blackout_maneuver | final_error_m | adaptive_legacy → adaptive_supervisor | 0.0089 | 3/2 of 5 | 0.7227 | 1.0000 | worse_inconclusive |
| blackout_maneuver | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | -0.0177 | 5/0 of 5 | 0.0028 | 0.0625 | better_significant |
| blackout_maneuver | RMSE | pidr → adaptive_supervisor | 0.1393 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_maneuver | Peak | pidr → adaptive_supervisor | 0.2608 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_maneuver | MinSep | pidr → adaptive_supervisor | 0.5328 | 5/0 of 5 | 0.0000 | 0.0625 | better_significant |
| blackout_maneuver | final_error_m | pidr → adaptive_supervisor | -0.1118 | 4/1 of 5 | 0.0386 | 0.1250 | better_significant |
| blackout_maneuver | cmd_dv_mean | pidr → adaptive_supervisor | 0.0603 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_maneuver | RMSE | sup_observe_only → adaptive_supervisor | 0.0925 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| blackout_maneuver | Peak | sup_observe_only → adaptive_supervisor | 0.2249 | 0/5 of 5 | 0.0001 | 0.0625 | worse_significant |
| blackout_maneuver | MinSep | sup_observe_only → adaptive_supervisor | 0.0201 | 5/0 of 5 | 0.0097 | 0.0625 | better_significant |
| blackout_maneuver | final_error_m | sup_observe_only → adaptive_supervisor | -0.0124 | 4/1 of 5 | 0.5998 | 0.6250 | better_inconclusive |
| blackout_maneuver | cmd_dv_mean | sup_observe_only → adaptive_supervisor | -0.0134 | 5/0 of 5 | 0.0011 | 0.0625 | better_significant |
| blackout_maneuver | RMSE | adaptive_supervisor → sup_no_ff | -0.0013 | 5/0 of 5 | 0.0023 | 0.0625 | better_significant |
| blackout_maneuver | Peak | adaptive_supervisor → sup_no_ff | 0.0064 | 2/3 of 5 | 0.3476 | 0.3125 | worse_inconclusive |
| blackout_maneuver | MinSep | adaptive_supervisor → sup_no_ff | -0.0278 | 0/5 of 5 | 0.0109 | 0.0625 | worse_significant |
| blackout_maneuver | final_error_m | adaptive_supervisor → sup_no_ff | 0.0068 | 1/4 of 5 | 0.0539 | 0.1250 | worse_inconclusive |
| blackout_maneuver | cmd_dv_mean | adaptive_supervisor → sup_no_ff | -0.0040 | 5/0 of 5 | 0.0130 | 0.0625 | better_significant |
| blackout_maneuver | RMSE | adaptive_supervisor → sup_no_speedlimit | -0.0963 | 5/0 of 5 | 0.0000 | 0.0625 | better_significant |
| blackout_maneuver | Peak | adaptive_supervisor → sup_no_speedlimit | -0.2460 | 5/0 of 5 | 0.0000 | 0.0625 | better_significant |
| blackout_maneuver | MinSep | adaptive_supervisor → sup_no_speedlimit | 0.0054 | 4/1 of 5 | 0.0987 | 0.1875 | better_inconclusive |
| blackout_maneuver | final_error_m | adaptive_supervisor → sup_no_speedlimit | 0.0014 | 1/4 of 5 | 0.9523 | 0.6250 | worse_inconclusive |
| blackout_maneuver | cmd_dv_mean | adaptive_supervisor → sup_no_speedlimit | 0.0182 | 0/5 of 5 | 0.0016 | 0.0625 | worse_significant |
| blackout_maneuver | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| blackout_maneuver | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| blackout_maneuver | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| blackout_maneuver | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| blackout_maneuver | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| blackout_maneuver | RMSE | pidr → adaptive_legacy | 0.0442 | 0/5 of 5 | 0.0006 | 0.0625 | worse_significant |
| blackout_maneuver | Peak | pidr → adaptive_legacy | 0.0418 | 0/5 of 5 | 0.0033 | 0.0625 | worse_significant |
| blackout_maneuver | MinSep | pidr → adaptive_legacy | 0.5557 | 5/0 of 5 | 0.0000 | 0.0625 | better_significant |
| blackout_maneuver | final_error_m | pidr → adaptive_legacy | -0.1208 | 5/0 of 5 | 0.0056 | 0.0625 | better_significant |
| blackout_maneuver | cmd_dv_mean | pidr → adaptive_legacy | 0.0780 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| random_loss_30 | RMSE | adaptive_legacy → adaptive_supervisor | 0.1170 | 0/5 of 5 | 0.0005 | 0.0625 | worse_significant |
| random_loss_30 | Peak | adaptive_legacy → adaptive_supervisor | 0.1566 | 0/5 of 5 | 0.0050 | 0.0625 | worse_significant |
| random_loss_30 | MinSep | adaptive_legacy → adaptive_supervisor | -0.1727 | 0/5 of 5 | 0.0072 | 0.0625 | worse_significant |
| random_loss_30 | final_error_m | adaptive_legacy → adaptive_supervisor | 0.0754 | 0/5 of 5 | 0.0732 | 0.0625 | worse_inconclusive |
| random_loss_30 | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | -0.0119 | 5/0 of 5 | 0.0142 | 0.0625 | better_significant |
| random_loss_30 | RMSE | pidr → adaptive_supervisor | 0.1979 | 0/5 of 5 | 0.0002 | 0.0625 | worse_significant |
| random_loss_30 | Peak | pidr → adaptive_supervisor | 0.3258 | 0/5 of 5 | 0.0005 | 0.0625 | worse_significant |
| random_loss_30 | MinSep | pidr → adaptive_supervisor | -0.1402 | 1/4 of 5 | 0.0267 | 0.1250 | worse_significant |
| random_loss_30 | final_error_m | pidr → adaptive_supervisor | 0.1237 | 0/5 of 5 | 0.0167 | 0.0625 | worse_significant |
| random_loss_30 | cmd_dv_mean | pidr → adaptive_supervisor | 0.0747 | 0/5 of 5 | 0.0001 | 0.0625 | worse_significant |
| random_loss_30 | RMSE | sup_observe_only → adaptive_supervisor | 0.1173 | 0/5 of 5 | 0.0005 | 0.0625 | worse_significant |
| random_loss_30 | Peak | sup_observe_only → adaptive_supervisor | 0.1556 | 0/5 of 5 | 0.0050 | 0.0625 | worse_significant |
| random_loss_30 | MinSep | sup_observe_only → adaptive_supervisor | -0.1697 | 0/5 of 5 | 0.0067 | 0.0625 | worse_significant |
| random_loss_30 | final_error_m | sup_observe_only → adaptive_supervisor | 0.0782 | 0/5 of 5 | 0.0613 | 0.0625 | worse_inconclusive |
| random_loss_30 | cmd_dv_mean | sup_observe_only → adaptive_supervisor | -0.0117 | 5/0 of 5 | 0.0145 | 0.0625 | better_significant |
| random_loss_30 | RMSE | adaptive_supervisor → sup_no_ff | -0.0050 | 5/0 of 5 | 0.0276 | 0.0625 | better_significant |
| random_loss_30 | Peak | adaptive_supervisor → sup_no_ff | -0.0053 | 5/0 of 5 | 0.0702 | 0.0625 | better_inconclusive |
| random_loss_30 | MinSep | adaptive_supervisor → sup_no_ff | -0.0218 | 0/5 of 5 | 0.0027 | 0.0625 | worse_significant |
| random_loss_30 | final_error_m | adaptive_supervisor → sup_no_ff | -0.0004 | 2/3 of 5 | 0.9636 | 1.0000 | better_inconclusive |
| random_loss_30 | cmd_dv_mean | adaptive_supervisor → sup_no_ff | -0.0014 | 5/0 of 5 | 0.0109 | 0.0625 | better_significant |
| random_loss_30 | RMSE | adaptive_supervisor → sup_no_speedlimit | -0.1123 | 5/0 of 5 | 0.0006 | 0.0625 | better_significant |
| random_loss_30 | Peak | adaptive_supervisor → sup_no_speedlimit | -0.1496 | 5/0 of 5 | 0.0051 | 0.0625 | better_significant |
| random_loss_30 | MinSep | adaptive_supervisor → sup_no_speedlimit | 0.1868 | 5/0 of 5 | 0.0068 | 0.0625 | better_significant |
| random_loss_30 | final_error_m | adaptive_supervisor → sup_no_speedlimit | -0.0698 | 5/0 of 5 | 0.0778 | 0.0625 | better_inconclusive |
| random_loss_30 | cmd_dv_mean | adaptive_supervisor → sup_no_speedlimit | 0.0124 | 0/5 of 5 | 0.0100 | 0.0625 | worse_significant |
| random_loss_30 | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| random_loss_30 | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| random_loss_30 | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| random_loss_30 | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| random_loss_30 | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 5 | n/a | n/a | identical |
| random_loss_30 | RMSE | pidr → adaptive_legacy | 0.0809 | 0/5 of 5 | 0.0001 | 0.0625 | worse_significant |
| random_loss_30 | Peak | pidr → adaptive_legacy | 0.1692 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| random_loss_30 | MinSep | pidr → adaptive_legacy | 0.0325 | 4/1 of 5 | 0.1282 | 0.1250 | better_inconclusive |
| random_loss_30 | final_error_m | pidr → adaptive_legacy | 0.0483 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
| random_loss_30 | cmd_dv_mean | pidr → adaptive_legacy | 0.0866 | 0/5 of 5 | 0.0000 | 0.0625 | worse_significant |
