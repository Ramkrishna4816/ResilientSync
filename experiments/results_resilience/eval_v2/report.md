# Resilience benchmark report — `eval_v2`

_Machine-generated from the measured per-run results; no value is edited by hand._

- seeds (10): [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
- duration per run: 18.0 s, dt = 0.05 s
- arms: zoh, pidr, advanced, adaptive_legacy, adaptive_capped, adaptive_supervisor, sup_observe_only, sup_no_ff, sup_speedlimit, sup_no_avoid
- scenarios: nominal, blackout_3s, blackout_6s, blackout_maneuver, random_loss_30, burst_loss, latency_jitter, latency_then_blackout, nominal_gentle, blackout_gentle
- runs: 1000 (0 failed or halted)

## Scenario definitions

- **nominal** — no injected fault (default channel only)
- **blackout_3s** — 3 s total blackout at t=5 s (the original benchmark)
- **blackout_6s** — 6 s total blackout at t=4 s
- **blackout_maneuver** — 3 s blackout at t=5 s while the leader stops and turns abruptly
- **random_loss_30** — independent 30 % extra packet loss, t=4-12 s
- **burst_loss** — correlated burst loss (mean ~50 %, mean burst ~6.7 packets), t=4-12 s
- **latency_jitter** — +0.4 s latency with +-0.2 s jitter, t=4-12 s
- **latency_then_blackout** — +0.3 s latency/jitter for 3 s then a 3 s blackout (t=3-9 s)
- **nominal_gentle** — no fault, low-curvature leader path (feasibility control)
- **blackout_gentle** — 3 s blackout at t=5 s, low-curvature leader path (feasibility control)

## Arm definitions

- **zoh** — zero-order hold of the last leader packet (baseline)
- **pidr** — PID + dead-reckoning of the leader (baseline)
- **advanced** — PIDR + neighbour coupling + avoidance + gain scheduling (baseline)
- **adaptive_legacy** — adaptive_comm, no supervisor (quality-threshold feed-forward scaling only)
- **adaptive_capped** — adaptive_comm, no supervisor, TOTAL speed cap (the earlier prototype, kept for the discrepancy record)
- **adaptive_supervisor** — adaptive_comm + resilience supervisor (default fallback)
- **sup_observe_only** — supervisor runs but all caution modifiers are neutral (ablation control)
- **sup_no_ff** — supervisor without feed-forward scaling
- **sup_speedlimit** — supervisor + HOLD speed limit of 0.8 x max speed (the first design; measured harmful)
- **sup_no_avoid** — supervisor without avoidance boost

## Scenario `nominal` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| zoh | 1.658 ± 0.014 | 2.359 ± 0.015 | 1.137 ± 0.163 | 0.00 | n/a | 1.471 | n/a | n/a (n=0) | n/a | n/a |
| pidr | 1.494 ± 0.009 | 2.177 ± 0.009 | 1.103 ± 0.016 | 0.00 | n/a | 1.420 | n/a | n/a (n=0) | n/a | n/a |
| advanced | 1.580 ± 0.012 | 2.352 ± 0.017 | 1.109 ± 0.024 | 0.00 | n/a | 1.466 | n/a | n/a (n=0) | n/a | n/a |
| adaptive_capped | 1.596 ± 0.025 | 2.373 ± 0.030 | 1.074 ± 0.053 | 0.00 | n/a | 1.468 | n/a | n/a (n=0) | n/a | n/a |
| adaptive_legacy | 1.580 ± 0.012 | 2.351 ± 0.017 | 1.110 ± 0.023 | 0.00 | n/a | 1.467 | n/a | n/a (n=0) | n/a | n/a |
| adaptive_supervisor | 1.582 ± 0.013 | 2.352 ± 0.015 | 1.110 ± 0.024 | 0.00 | n/a | 1.471 | n/a | n/a (n=0) | 1.4 | 0.00 |
| sup_observe_only | 1.580 ± 0.012 | 2.352 ± 0.017 | 1.109 ± 0.024 | 0.00 | n/a | 1.466 | n/a | n/a (n=0) | 1.4 | 0.00 |
| sup_no_ff | 1.580 ± 0.012 | 2.352 ± 0.017 | 1.109 ± 0.024 | 0.00 | n/a | 1.466 | n/a | n/a (n=0) | 1.4 | 0.00 |
| sup_speedlimit | 1.631 ± 0.031 | 2.433 ± 0.070 | 1.005 ± 0.102 | 0.00 | n/a | 1.482 | n/a | n/a (n=0) | 1.4 | 0.00 |
| sup_no_avoid | 1.582 ± 0.013 | 2.352 ± 0.015 | 1.110 ± 0.024 | 0.00 | n/a | 1.471 | n/a | n/a (n=0) | 1.4 | 0.00 |

## Scenario `blackout_3s` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| zoh | 2.669 ± 0.108 | 4.580 ± 0.060 | 0.462 ± 0.099 | 0.25 | 1.569 | 1.575 | 0/10 | n/a (n=0) | n/a | n/a |
| pidr | 1.537 ± 0.008 | 2.252 ± 0.010 | 1.080 ± 0.016 | 0.00 | 1.351 | 1.429 | 0/10 | n/a (n=0) | n/a | n/a |
| advanced | 1.651 ± 0.014 | 2.492 ± 0.020 | 1.100 ± 0.026 | 0.00 | 1.472 | 1.489 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_capped | 2.258 ± 0.058 | 4.012 ± 0.123 | 0.766 ± 0.149 | 0.00 | 1.421 | 1.435 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_legacy | 1.668 ± 0.012 | 2.528 ± 0.021 | 1.143 ± 0.022 | 0.00 | 1.456 | 1.469 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_supervisor | 1.657 ± 0.013 | 2.506 ± 0.019 | 1.122 ± 0.031 | 0.00 | 1.464 | 1.488 | 0/10 | n/a (n=0) | 5.0 | 2.17 |
| sup_observe_only | 1.651 ± 0.014 | 2.492 ± 0.020 | 1.100 ± 0.026 | 0.00 | 1.472 | 1.489 | 0/10 | n/a (n=0) | 5.0 | 2.17 |
| sup_no_ff | 1.651 ± 0.014 | 2.492 ± 0.020 | 1.100 ± 0.026 | 0.00 | 1.472 | 1.489 | 0/10 | n/a (n=0) | 5.0 | 2.17 |
| sup_speedlimit | 1.828 ± 0.017 | 2.931 ± 0.036 | 0.750 ± 0.048 | 0.00 | 1.490 | 1.503 | 0/10 | n/a (n=0) | 5.0 | 2.17 |
| sup_no_avoid | 1.657 ± 0.013 | 2.506 ± 0.019 | 1.122 ± 0.031 | 0.00 | 1.464 | 1.488 | 0/10 | n/a (n=0) | 5.0 | 2.17 |

## Scenario `blackout_6s` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| zoh | 3.452 ± 0.042 | 6.398 ± 0.061 | 0.160 ± 0.114 | 5.86 | 1.310 | 1.310 | 0/10 | n/a (n=0) | n/a | n/a |
| pidr | 2.000 ± 0.038 | 3.217 ± 0.097 | 0.828 ± 0.377 | 0.61 | 1.650 | 1.650 | 0/10 | n/a (n=0) | n/a | n/a |
| advanced | 2.157 ± 0.073 | 3.411 ± 0.112 | 1.182 ± 0.096 | 0.00 | 1.948 | 1.948 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_capped | 3.235 ± 0.083 | 5.603 ± 0.087 | 0.453 ± 0.063 | 0.08 | 1.827 | 1.827 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_legacy | 2.168 ± 0.074 | 3.355 ± 0.140 | 1.213 ± 0.071 | 0.00 | 1.904 | 1.904 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_supervisor | 2.153 ± 0.071 | 3.345 ± 0.135 | 1.235 ± 0.078 | 0.00 | 1.940 | 1.940 | 0/10 | n/a (n=0) | 4.7 | 5.25 |
| sup_observe_only | 2.157 ± 0.073 | 3.411 ± 0.112 | 1.182 ± 0.096 | 0.00 | 1.948 | 1.948 | 0/10 | n/a (n=0) | 4.7 | 5.25 |
| sup_no_ff | 2.157 ± 0.073 | 3.411 ± 0.112 | 1.182 ± 0.096 | 0.00 | 1.948 | 1.948 | 0/10 | n/a (n=0) | 4.7 | 5.25 |
| sup_speedlimit | 2.402 ± 0.068 | 3.833 ± 0.123 | 0.834 ± 0.080 | 0.00 | 1.969 | 1.969 | 0/10 | n/a (n=0) | 4.7 | 5.25 |
| sup_no_avoid | 2.153 ± 0.071 | 3.345 ± 0.135 | 1.235 ± 0.078 | 0.00 | 1.940 | 1.940 | 0/10 | n/a (n=0) | 4.7 | 5.25 |

## Scenario `blackout_maneuver` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| zoh | 2.101 ± 0.095 | 4.013 ± 0.059 | 0.106 ± 0.041 | 4.44 | 0.443 | 0.443 | 10/10 | 7.320 (n=10) | n/a | n/a |
| pidr | 1.210 ± 0.007 | 1.979 ± 0.023 | 0.320 ± 0.031 | 2.39 | 0.389 | 0.389 | 10/10 | 7.795 (n=10) | n/a | n/a |
| advanced | 1.261 ± 0.011 | 2.007 ± 0.027 | 0.843 ± 0.036 | 0.00 | 0.310 | 0.310 | 10/10 | 7.885 (n=10) | n/a | n/a |
| adaptive_capped | 1.673 ± 0.047 | 3.240 ± 0.127 | 0.902 ± 0.087 | 0.00 | 0.157 | 0.157 | 10/10 | 6.940 (n=10) | n/a | n/a |
| adaptive_legacy | 1.259 ± 0.010 | 2.031 ± 0.023 | 0.876 ± 0.026 | 0.00 | 0.289 | 0.289 | 10/10 | 7.805 (n=10) | n/a | n/a |
| adaptive_supervisor | 1.259 ± 0.011 | 2.003 ± 0.021 | 0.857 ± 0.024 | 0.00 | 0.298 | 0.298 | 10/10 | 7.850 (n=10) | 5.0 | 2.17 |
| sup_observe_only | 1.261 ± 0.011 | 2.007 ± 0.027 | 0.843 ± 0.036 | 0.00 | 0.310 | 0.310 | 10/10 | 7.885 (n=10) | 5.0 | 2.17 |
| sup_no_ff | 1.261 ± 0.011 | 2.007 ± 0.027 | 0.843 ± 0.036 | 0.00 | 0.310 | 0.310 | 10/10 | 7.885 (n=10) | 5.0 | 2.17 |
| sup_speedlimit | 1.366 ± 0.014 | 2.256 ± 0.038 | 0.850 ± 0.028 | 0.00 | 0.289 | 0.289 | 10/10 | 7.665 (n=10) | 5.0 | 2.17 |
| sup_no_avoid | 1.259 ± 0.011 | 2.003 ± 0.021 | 0.857 ± 0.024 | 0.00 | 0.298 | 0.298 | 10/10 | 7.850 (n=10) | 5.0 | 2.17 |

## Scenario `random_loss_30` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| zoh | 1.676 ± 0.012 | 2.382 ± 0.015 | 1.176 ± 0.074 | 0.00 | 1.395 | 1.494 | 0/10 | n/a (n=0) | n/a | n/a |
| pidr | 1.494 ± 0.009 | 2.177 ± 0.009 | 1.103 ± 0.016 | 0.00 | 1.304 | 1.419 | 0/10 | n/a (n=0) | n/a | n/a |
| advanced | 1.581 ± 0.012 | 2.353 ± 0.018 | 1.112 ± 0.025 | 0.00 | 1.411 | 1.468 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_capped | 1.618 ± 0.028 | 2.401 ± 0.041 | 1.038 ± 0.067 | 0.00 | 1.426 | 1.474 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_legacy | 1.581 ± 0.012 | 2.353 ± 0.018 | 1.111 ± 0.022 | 0.00 | 1.413 | 1.470 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_supervisor | 1.586 ± 0.012 | 2.363 ± 0.017 | 1.132 ± 0.022 | 0.00 | 1.410 | 1.468 | 0/10 | n/a (n=0) | 1.9 | 0.00 |
| sup_observe_only | 1.581 ± 0.012 | 2.353 ± 0.018 | 1.112 ± 0.025 | 0.00 | 1.411 | 1.468 | 0/10 | n/a (n=0) | 1.9 | 0.00 |
| sup_no_ff | 1.581 ± 0.012 | 2.353 ± 0.018 | 1.112 ± 0.025 | 0.00 | 1.411 | 1.468 | 0/10 | n/a (n=0) | 1.9 | 0.00 |
| sup_speedlimit | 1.700 ± 0.055 | 2.509 ± 0.098 | 0.940 ± 0.148 | 0.00 | 1.526 | 1.527 | 0/10 | n/a (n=0) | 1.9 | 0.00 |
| sup_no_avoid | 1.586 ± 0.012 | 2.363 ± 0.017 | 1.132 ± 0.022 | 0.00 | 1.410 | 1.468 | 0/10 | n/a (n=0) | 1.9 | 0.00 |

## Scenario `burst_loss` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| zoh | 1.826 ± 0.066 | 2.623 ± 0.120 | 0.706 ± 0.360 | 1.56 | 1.500 | 1.549 | 0/10 | n/a (n=0) | n/a | n/a |
| pidr | 1.497 ± 0.009 | 2.180 ± 0.010 | 1.101 ± 0.017 | 0.00 | 1.307 | 1.422 | 0/10 | n/a (n=0) | n/a | n/a |
| advanced | 1.584 ± 0.014 | 2.355 ± 0.020 | 1.093 ± 0.030 | 0.00 | 1.413 | 1.467 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_capped | 2.041 ± 0.169 | 3.248 ± 0.316 | 0.844 ± 0.191 | 0.00 | 1.577 | 1.584 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_legacy | 1.598 ± 0.016 | 2.381 ± 0.028 | 1.140 ± 0.053 | 0.00 | 1.407 | 1.463 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_supervisor | 1.591 ± 0.014 | 2.367 ± 0.023 | 1.120 ± 0.020 | 0.00 | 1.410 | 1.460 | 0/10 | n/a (n=0) | 3.2 | 0.38 |
| sup_observe_only | 1.584 ± 0.014 | 2.355 ± 0.020 | 1.093 ± 0.030 | 0.00 | 1.413 | 1.467 | 0/10 | n/a (n=0) | 3.2 | 0.38 |
| sup_no_ff | 1.584 ± 0.014 | 2.355 ± 0.020 | 1.093 ± 0.030 | 0.00 | 1.413 | 1.467 | 0/10 | n/a (n=0) | 3.2 | 0.38 |
| sup_speedlimit | 1.738 ± 0.023 | 2.587 ± 0.031 | 0.838 ± 0.039 | 0.00 | 1.525 | 1.527 | 0/10 | n/a (n=0) | 3.2 | 0.38 |
| sup_no_avoid | 1.591 ± 0.014 | 2.367 ± 0.023 | 1.120 ± 0.020 | 0.00 | 1.410 | 1.460 | 0/10 | n/a (n=0) | 3.2 | 0.38 |

## Scenario `latency_jitter` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| zoh | 1.835 ± 0.022 | 2.603 ± 0.020 | 1.200 ± 0.186 | 0.00 | 1.533 | 1.575 | 0/10 | n/a (n=0) | n/a | n/a |
| pidr | 1.498 ± 0.009 | 2.183 ± 0.009 | 1.103 ± 0.017 | 0.00 | 1.310 | 1.418 | 0/10 | n/a (n=0) | n/a | n/a |
| advanced | 1.585 ± 0.012 | 2.359 ± 0.017 | 1.099 ± 0.028 | 0.00 | 1.416 | 1.467 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_capped | 2.033 ± 0.114 | 3.173 ± 0.217 | 0.736 ± 0.210 | 0.00 | 1.577 | 1.578 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_legacy | 1.596 ± 0.013 | 2.381 ± 0.015 | 1.142 ± 0.023 | 0.00 | 1.414 | 1.465 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_supervisor | 1.593 ± 0.012 | 2.370 ± 0.015 | 1.122 ± 0.021 | 0.00 | 1.418 | 1.474 | 0/10 | n/a (n=0) | 2.0 | 0.00 |
| sup_observe_only | 1.585 ± 0.012 | 2.359 ± 0.017 | 1.099 ± 0.028 | 0.00 | 1.416 | 1.467 | 0/10 | n/a (n=0) | 2.0 | 0.00 |
| sup_no_ff | 1.585 ± 0.012 | 2.359 ± 0.017 | 1.099 ± 0.028 | 0.00 | 1.416 | 1.467 | 0/10 | n/a (n=0) | 2.0 | 0.00 |
| sup_speedlimit | 1.747 ± 0.017 | 2.580 ± 0.018 | 0.845 ± 0.032 | 0.00 | 1.551 | 1.554 | 0/10 | n/a (n=0) | 2.0 | 0.00 |
| sup_no_avoid | 1.593 ± 0.012 | 2.370 ± 0.015 | 1.122 ± 0.021 | 0.00 | 1.418 | 1.474 | 0/10 | n/a (n=0) | 2.0 | 0.00 |

## Scenario `latency_then_blackout` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| zoh | 2.616 ± 0.038 | 4.505 ± 0.057 | 0.176 ± 0.139 | 4.58 | 1.797 | 1.797 | 0/10 | n/a (n=0) | n/a | n/a |
| pidr | 1.534 ± 0.008 | 2.245 ± 0.009 | 1.086 ± 0.016 | 0.00 | 1.361 | 1.435 | 0/10 | n/a (n=0) | n/a | n/a |
| advanced | 1.652 ± 0.012 | 2.486 ± 0.019 | 1.163 ± 0.023 | 0.00 | 1.496 | 1.505 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_capped | 2.371 ± 0.112 | 4.261 ± 0.209 | 0.669 ± 0.122 | 0.00 | 1.490 | 1.492 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_legacy | 1.673 ± 0.013 | 2.547 ± 0.019 | 1.187 ± 0.019 | 0.00 | 1.480 | 1.502 | 0/10 | n/a (n=0) | n/a | n/a |
| adaptive_supervisor | 1.662 ± 0.012 | 2.518 ± 0.017 | 1.182 ± 0.021 | 0.00 | 1.487 | 1.495 | 0/10 | n/a (n=0) | 4.8 | 2.15 |
| sup_observe_only | 1.652 ± 0.012 | 2.486 ± 0.019 | 1.163 ± 0.023 | 0.00 | 1.496 | 1.505 | 0/10 | n/a (n=0) | 4.8 | 2.15 |
| sup_no_ff | 1.652 ± 0.012 | 2.486 ± 0.019 | 1.163 ± 0.023 | 0.00 | 1.496 | 1.505 | 0/10 | n/a (n=0) | 4.8 | 2.15 |
| sup_speedlimit | 1.860 ± 0.016 | 2.964 ± 0.018 | 0.692 ± 0.018 | 0.00 | 1.528 | 1.534 | 0/10 | n/a (n=0) | 4.8 | 2.15 |
| sup_no_avoid | 1.662 ± 0.012 | 2.518 ± 0.017 | 1.182 ± 0.021 | 0.00 | 1.487 | 1.495 | 0/10 | n/a (n=0) | 4.8 | 2.15 |

## Scenario `nominal_gentle` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| zoh | 0.218 ± 0.012 | 0.331 ± 0.043 | 1.258 ± 0.103 | 0.00 | n/a | 0.223 | n/a | n/a (n=0) | n/a | n/a |
| pidr | 0.070 ± 0.005 | 0.145 ± 0.026 | 1.350 ± 0.071 | 0.00 | n/a | 0.105 | n/a | n/a (n=0) | n/a | n/a |
| advanced | 0.060 ± 0.005 | 0.133 ± 0.029 | 1.369 ± 0.072 | 0.00 | n/a | 0.072 | n/a | n/a (n=0) | n/a | n/a |
| adaptive_capped | 0.062 ± 0.006 | 0.136 ± 0.028 | 1.370 ± 0.073 | 0.00 | n/a | 0.073 | n/a | n/a (n=0) | n/a | n/a |
| adaptive_legacy | 0.060 ± 0.005 | 0.133 ± 0.029 | 1.369 ± 0.073 | 0.00 | n/a | 0.072 | n/a | n/a (n=0) | n/a | n/a |
| adaptive_supervisor | 0.059 ± 0.006 | 0.133 ± 0.028 | 1.367 ± 0.071 | 0.00 | n/a | 0.079 | n/a | n/a (n=0) | 1.4 | 0.00 |
| sup_observe_only | 0.060 ± 0.005 | 0.133 ± 0.029 | 1.369 ± 0.072 | 0.00 | n/a | 0.072 | n/a | n/a (n=0) | 1.4 | 0.00 |
| sup_no_ff | 0.060 ± 0.005 | 0.133 ± 0.029 | 1.369 ± 0.072 | 0.00 | n/a | 0.072 | n/a | n/a (n=0) | 1.4 | 0.00 |
| sup_speedlimit | 0.059 ± 0.007 | 0.133 ± 0.028 | 1.368 ± 0.072 | 0.00 | n/a | 0.083 | n/a | n/a (n=0) | 1.4 | 0.00 |
| sup_no_avoid | 0.059 ± 0.006 | 0.133 ± 0.028 | 1.367 ± 0.071 | 0.00 | n/a | 0.079 | n/a | n/a (n=0) | 1.4 | 0.00 |

## Scenario `blackout_gentle` (mean ± std over seeds)

| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] | final [m] | recovered | recovery time [s] | transitions | s in HOLD |
|---|---|---|---|---|---|---|---|---|---|---|
| zoh | 1.264 ± 0.039 | 2.789 ± 0.047 | 1.157 ± 0.198 | 0.00 | 0.135 | 0.144 | 10/10 | 6.800 (n=10) | n/a | n/a |
| pidr | 0.117 ± 0.005 | 0.333 ± 0.013 | 1.347 ± 0.069 | 0.00 | 0.030 | 0.116 | 10/10 | 0.050 (n=10) | n/a | n/a |
| advanced | 0.097 ± 0.005 | 0.297 ± 0.013 | 1.365 ± 0.069 | 0.00 | 0.018 | 0.084 | 10/10 | 0.050 (n=10) | n/a | n/a |
| adaptive_capped | 0.545 ± 0.045 | 1.374 ± 0.081 | 1.318 ± 0.060 | 0.00 | 0.022 | 0.144 | 10/10 | 3.935 (n=10) | n/a | n/a |
| adaptive_legacy | 0.188 ± 0.005 | 0.567 ± 0.015 | 1.344 ± 0.057 | 0.00 | 0.016 | 0.113 | 10/10 | 0.550 (n=10) | n/a | n/a |
| adaptive_supervisor | 0.143 ± 0.005 | 0.429 ± 0.014 | 1.355 ± 0.063 | 0.00 | 0.015 | 0.102 | 10/10 | 0.050 (n=10) | 5.0 | 2.17 |
| sup_observe_only | 0.097 ± 0.005 | 0.297 ± 0.013 | 1.365 ± 0.069 | 0.00 | 0.018 | 0.084 | 10/10 | 0.050 (n=10) | 5.0 | 2.17 |
| sup_no_ff | 0.097 ± 0.005 | 0.297 ± 0.013 | 1.365 ± 0.069 | 0.00 | 0.018 | 0.084 | 10/10 | 0.050 (n=10) | 5.0 | 2.17 |
| sup_speedlimit | 0.174 ± 0.006 | 0.465 ± 0.015 | 1.348 ± 0.060 | 0.00 | 0.015 | 0.113 | 10/10 | 0.050 (n=10) | 5.0 | 2.17 |
| sup_no_avoid | 0.143 ± 0.005 | 0.429 ± 0.014 | 1.355 ± 0.063 | 0.00 | 0.015 | 0.102 | 10/10 | 0.050 (n=10) | 5.0 | 2.17 |

### Connectivity, consensus and saturation (global diagnostics)

Separate from formation tracking: connectivity = leader->follower links alive; consensus = RMS heading disagreement <= 0.25 rad sustained 1.0 s (measured from fault end, or t=0 without a fault).


**`nominal`**

| arm | conn. interruption [s] | max isolated [s] | restore lag [s] | min lambda2 | heading RMS mean [rad] | in consensus [% time] | consensus reached | commands at speed limit [%] |
|---|---|---|---|---|---|---|---|---|
| zoh | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.429 | 7.8 | 8/10 | 56.5 |
| pidr | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.395 | 9.0 | 9/10 | 50.1 |
| advanced | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 18.1 | 9/10 | 43.9 |
| adaptive_capped | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.429 | 17.3 | 10/10 | 42.9 |
| adaptive_legacy | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 17.7 | 9/10 | 44.0 |
| adaptive_supervisor | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.425 | 18.0 | 9/10 | 44.0 |
| sup_observe_only | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 18.1 | 9/10 | 43.9 |
| sup_no_ff | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 18.1 | 9/10 | 43.9 |
| sup_speedlimit | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.432 | 16.2 | 9/10 | 34.2 |
| sup_no_avoid | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.425 | 18.0 | 9/10 | 44.0 |

**`blackout_3s`**

| arm | conn. interruption [s] | max isolated [s] | restore lag [s] | min lambda2 | heading RMS mean [rad] | in consensus [% time] | consensus reached | commands at speed limit [%] |
|---|---|---|---|---|---|---|---|---|
| zoh | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.671 | 7.1 | 0/10 | 58.2 |
| pidr | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.413 | 7.8 | 0/10 | 51.3 |
| advanced | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.438 | 13.8 | 4/10 | 45.7 |
| adaptive_capped | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.539 | 9.0 | 1/10 | 36.7 |
| adaptive_legacy | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.445 | 12.3 | 2/10 | 46.3 |
| adaptive_supervisor | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.439 | 14.2 | 4/10 | 45.8 |
| sup_observe_only | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.438 | 13.8 | 4/10 | 45.7 |
| sup_no_ff | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.438 | 13.8 | 4/10 | 45.7 |
| sup_speedlimit | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.462 | 11.2 | 4/10 | 27.7 |
| sup_no_avoid | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.439 | 14.2 | 4/10 | 45.8 |

**`blackout_6s`**

| arm | conn. interruption [s] | max isolated [s] | restore lag [s] | min lambda2 | heading RMS mean [rad] | in consensus [% time] | consensus reached | commands at speed limit [%] |
|---|---|---|---|---|---|---|---|---|
| zoh | 5.32 | 5.25 | 0.15 (n=10) | 0.00 | 0.833 | 7.1 | 0/10 | 52.9 |
| pidr | 5.32 | 5.25 | 0.15 (n=10) | 0.00 | 0.488 | 6.6 | 0/10 | 53.3 |
| advanced | 5.32 | 5.25 | 0.15 (n=10) | 0.00 | 0.490 | 11.4 | 4/10 | 52.2 |
| adaptive_capped | 5.32 | 5.25 | 0.15 (n=10) | 0.00 | 0.730 | 5.1 | 0/10 | 30.9 |
| adaptive_legacy | 5.32 | 5.25 | 0.15 (n=10) | 0.00 | 0.487 | 8.4 | 0/10 | 51.5 |
| adaptive_supervisor | 5.32 | 5.25 | 0.15 (n=10) | 0.00 | 0.477 | 10.9 | 3/10 | 51.4 |
| sup_observe_only | 5.32 | 5.25 | 0.15 (n=10) | 0.00 | 0.490 | 11.4 | 4/10 | 52.2 |
| sup_no_ff | 5.32 | 5.25 | 0.15 (n=10) | 0.00 | 0.490 | 11.4 | 4/10 | 52.2 |
| sup_speedlimit | 5.32 | 5.25 | 0.15 (n=10) | 0.00 | 0.520 | 7.8 | 0/10 | 26.9 |
| sup_no_avoid | 5.32 | 5.25 | 0.15 (n=10) | 0.00 | 0.477 | 10.9 | 3/10 | 51.4 |

**`blackout_maneuver`**

| arm | conn. interruption [s] | max isolated [s] | restore lag [s] | min lambda2 | heading RMS mean [rad] | in consensus [% time] | consensus reached | commands at speed limit [%] |
|---|---|---|---|---|---|---|---|---|
| zoh | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.651 | 12.9 | 5/10 | 60.7 |
| pidr | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.466 | 15.3 | 4/10 | 61.3 |
| advanced | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.485 | 23.6 | 10/10 | 54.6 |
| adaptive_capped | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.577 | 21.6 | 10/10 | 42.6 |
| adaptive_legacy | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.490 | 22.4 | 10/10 | 54.3 |
| adaptive_supervisor | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.486 | 23.1 | 10/10 | 54.3 |
| sup_observe_only | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.485 | 23.6 | 10/10 | 54.6 |
| sup_no_ff | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.485 | 23.6 | 10/10 | 54.6 |
| sup_speedlimit | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.509 | 22.1 | 10/10 | 34.5 |
| sup_no_avoid | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.486 | 23.1 | 10/10 | 54.3 |

**`random_loss_30`**

| arm | conn. interruption [s] | max isolated [s] | restore lag [s] | min lambda2 | heading RMS mean [rad] | in consensus [% time] | consensus reached | commands at speed limit [%] |
|---|---|---|---|---|---|---|---|---|
| zoh | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.434 | 7.9 | 0/10 | 56.3 |
| pidr | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.395 | 9.1 | 0/10 | 50.0 |
| advanced | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 17.3 | 10/10 | 44.0 |
| adaptive_capped | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.431 | 16.1 | 9/10 | 40.8 |
| adaptive_legacy | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 17.5 | 10/10 | 44.0 |
| adaptive_supervisor | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 16.7 | 5/10 | 43.8 |
| sup_observe_only | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 17.3 | 10/10 | 44.0 |
| sup_no_ff | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 17.3 | 10/10 | 44.0 |
| sup_speedlimit | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.440 | 11.9 | 2/10 | 22.0 |
| sup_no_avoid | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 16.7 | 5/10 | 43.8 |

**`burst_loss`**

| arm | conn. interruption [s] | max isolated [s] | restore lag [s] | min lambda2 | heading RMS mean [rad] | in consensus [% time] | consensus reached | commands at speed limit [%] |
|---|---|---|---|---|---|---|---|---|
| zoh | 0.76 | 0.55 | -0.79 (n=9) | 0.10 | 0.489 | 7.5 | 0/10 | 59.2 |
| pidr | 0.76 | 0.55 | -0.79 (n=9) | 0.10 | 0.396 | 8.4 | 0/10 | 50.3 |
| advanced | 0.76 | 0.55 | -0.79 (n=9) | 0.10 | 0.427 | 17.6 | 8/10 | 44.2 |
| adaptive_capped | 0.76 | 0.55 | -0.79 (n=9) | 0.10 | 0.504 | 11.0 | 2/10 | 33.2 |
| adaptive_legacy | 0.76 | 0.55 | -0.79 (n=9) | 0.10 | 0.434 | 13.6 | 3/10 | 44.5 |
| adaptive_supervisor | 0.76 | 0.55 | -0.79 (n=9) | 0.10 | 0.428 | 15.3 | 1/10 | 44.2 |
| sup_observe_only | 0.76 | 0.55 | -0.79 (n=9) | 0.10 | 0.427 | 17.6 | 8/10 | 44.2 |
| sup_no_ff | 0.76 | 0.55 | -0.79 (n=9) | 0.10 | 0.427 | 17.6 | 8/10 | 44.2 |
| sup_speedlimit | 0.76 | 0.55 | -0.79 (n=9) | 0.10 | 0.447 | 10.2 | 2/10 | 18.7 |
| sup_no_avoid | 0.76 | 0.55 | -0.79 (n=9) | 0.10 | 0.428 | 15.3 | 1/10 | 44.2 |

**`latency_jitter`**

| arm | conn. interruption [s] | max isolated [s] | restore lag [s] | min lambda2 | heading RMS mean [rad] | in consensus [% time] | consensus reached | commands at speed limit [%] |
|---|---|---|---|---|---|---|---|---|
| zoh | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.467 | 7.1 | 0/10 | 56.7 |
| pidr | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.396 | 8.6 | 0/10 | 50.2 |
| advanced | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 17.4 | 9/10 | 44.1 |
| adaptive_capped | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.498 | 7.1 | 0/10 | 25.0 |
| adaptive_legacy | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.431 | 13.9 | 2/10 | 44.1 |
| adaptive_supervisor | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 16.2 | 6/10 | 43.9 |
| sup_observe_only | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 17.4 | 9/10 | 44.1 |
| sup_no_ff | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 17.4 | 9/10 | 44.1 |
| sup_speedlimit | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.444 | 10.5 | 1/10 | 13.5 |
| sup_no_avoid | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.426 | 16.2 | 6/10 | 43.9 |

**`latency_then_blackout`**

| arm | conn. interruption [s] | max isolated [s] | restore lag [s] | min lambda2 | heading RMS mean [rad] | in consensus [% time] | consensus reached | commands at speed limit [%] |
|---|---|---|---|---|---|---|---|---|
| zoh | 1.63 | 1.62 | 0.02 (n=10) | 0.00 | 0.628 | 6.8 | 0/10 | 60.0 |
| pidr | 1.63 | 1.62 | 0.02 (n=10) | 0.00 | 0.408 | 7.7 | 0/10 | 51.1 |
| advanced | 1.63 | 1.62 | 0.02 (n=10) | 0.00 | 0.437 | 13.4 | 2/10 | 45.4 |
| adaptive_capped | 1.63 | 1.62 | 0.02 (n=10) | 0.00 | 0.554 | 7.2 | 0/10 | 32.7 |
| adaptive_legacy | 1.63 | 1.62 | 0.02 (n=10) | 0.00 | 0.446 | 11.6 | 0/10 | 46.2 |
| adaptive_supervisor | 1.63 | 1.62 | 0.02 (n=10) | 0.00 | 0.438 | 13.3 | 1/10 | 45.5 |
| sup_observe_only | 1.63 | 1.62 | 0.02 (n=10) | 0.00 | 0.437 | 13.4 | 2/10 | 45.4 |
| sup_no_ff | 1.63 | 1.62 | 0.02 (n=10) | 0.00 | 0.437 | 13.4 | 2/10 | 45.4 |
| sup_speedlimit | 1.63 | 1.62 | 0.02 (n=10) | 0.00 | 0.468 | 9.1 | 0/10 | 21.0 |
| sup_no_avoid | 1.63 | 1.62 | 0.02 (n=10) | 0.00 | 0.438 | 13.3 | 1/10 | 45.5 |

**`nominal_gentle`**

| arm | conn. interruption [s] | max isolated [s] | restore lag [s] | min lambda2 | heading RMS mean [rad] | in consensus [% time] | consensus reached | commands at speed limit [%] |
|---|---|---|---|---|---|---|---|---|
| zoh | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.128 | 93.1 | 10/10 | 37.4 |
| pidr | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.093 | 99.7 | 10/10 | 24.9 |
| advanced | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.092 | 99.6 | 10/10 | 27.7 |
| adaptive_capped | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.092 | 99.6 | 10/10 | 27.4 |
| adaptive_legacy | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.091 | 99.6 | 10/10 | 27.7 |
| adaptive_supervisor | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.093 | 99.6 | 10/10 | 27.8 |
| sup_observe_only | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.092 | 99.6 | 10/10 | 27.7 |
| sup_no_ff | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.092 | 99.6 | 10/10 | 27.7 |
| sup_speedlimit | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.093 | 99.5 | 10/10 | 22.6 |
| sup_no_avoid | 0.00 | 0.00 | n/a (n=0) | 1.00 | 0.093 | 99.6 | 10/10 | 27.8 |

**`blackout_gentle`**

| arm | conn. interruption [s] | max isolated [s] | restore lag [s] | min lambda2 | heading RMS mean [rad] | in consensus [% time] | consensus reached | commands at speed limit [%] |
|---|---|---|---|---|---|---|---|---|
| zoh | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.253 | 81.1 | 10/10 | 51.6 |
| pidr | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.108 | 96.6 | 10/10 | 25.7 |
| advanced | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.100 | 98.7 | 10/10 | 28.4 |
| adaptive_capped | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.112 | 96.0 | 10/10 | 31.6 |
| adaptive_legacy | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.111 | 97.6 | 10/10 | 30.1 |
| adaptive_supervisor | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.104 | 98.4 | 10/10 | 29.1 |
| sup_observe_only | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.100 | 98.7 | 10/10 | 28.4 |
| sup_no_ff | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.100 | 98.7 | 10/10 | 28.4 |
| sup_speedlimit | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.105 | 98.3 | 10/10 | 19.6 |
| sup_no_avoid | 2.00 | 1.96 | 0.04 (n=10) | 0.00 | 0.104 | 98.4 | 10/10 | 29.1 |

_Commands at the speed limit_ counts follower ticks with |v_cmd| = max_v. It mixes two causes: genuine infeasibility (outer wedge slots need more than max_v on the default curved path) and chatter from the derivative term on noisy error measurements (sensor sigma 0.025 m). See docs/EXPERIMENT_PROTOCOL.md, section 'Audit findings'.


`n/a` = metric not applicable (e.g. recovery without a finite fault window, supervisor statistics for controllers without a supervisor). Recovery time is averaged over recovered runs only; the recovered column shows how many runs satisfied the sustained-recovery criterion (unchanged from `simulation/metrics.py`).

## Strengths and weaknesses per arm (computed)

- **zoh** — strengths: mean |dv_cmd| per step [m/s] (rank 2/10), mean |dw_cmd| per step [rad/s] (rank 2/10); weaknesses: formation RMSE [m] (rank 10/10), peak formation error [m] (rank 10/10), minimum separation [m] (rank 10/10), collision samples [%] (rank 10/10), mean control effort (rank 10/10).
- **pidr** — strengths: formation RMSE [m] (rank 1/10), peak formation error [m] (rank 1/10), mean |dv_cmd| per step [m/s] (rank 1/10); weaknesses: collision samples [%] (rank 9/10).
- **advanced** — strengths: formation RMSE [m] (rank 2/10), peak formation error [m] (rank 2/10), collision samples [%] (rank 1/10); weaknesses: none in the bottom two.
- **adaptive_legacy** — strengths: minimum separation [m] (rank 1/10), collision samples [%] (rank 2/10); weaknesses: none in the bottom two.
- **adaptive_capped** — strengths: mean |dw_cmd| per step [rad/s] (rank 1/10), mean control effort (rank 1/10); weaknesses: formation RMSE [m] (rank 9/10), peak formation error [m] (rank 9/10), minimum separation [m] (rank 9/10).
- **adaptive_supervisor** — strengths: minimum separation [m] (rank 2/10); weaknesses: mean |dv_cmd| per step [m/s] (rank 9/10), mean |dw_cmd| per step [rad/s] (rank 9/10).
- **sup_observe_only** — strengths: none in the top two; weaknesses: none in the bottom two.
- **sup_no_ff** — strengths: none in the top two; weaknesses: mean control effort (rank 9/10).
- **sup_speedlimit** — strengths: mean control effort (rank 2/10); weaknesses: none in the bottom two.
- **sup_no_avoid** — strengths: none in the top two; weaknesses: mean |dv_cmd| per step [m/s] (rank 10/10), mean |dw_cmd| per step [rad/s] (rank 10/10).

_Ranks are by the mean over scenarios of each scenario's seed-mean; they are descriptive, not significance tests._

## Paired comparisons (same seeds, other − reference)

Verdict rules: `*_significant` needs paired-t p < 0.05 and ≥ 80 % of seeds moving in the same direction; otherwise `*_inconclusive`. p-values are uncorrected for the 350 comparisons shown, and n is small — treat them as indicative.

| scenario | metric | reference → other | mean diff | improved/worsened seeds | p (t) | p (Wilcoxon) | verdict |
|---|---|---|---|---|---|---|---|
| nominal | RMSE | adaptive_legacy → adaptive_supervisor | 0.0013 | 3/7 of 10 | 0.0505 | 0.0645 | worse_inconclusive |
| nominal | Peak | adaptive_legacy → adaptive_supervisor | 0.0008 | 4/5 of 10 | 0.7186 | 0.8203 | worse_inconclusive |
| nominal | MinSep | adaptive_legacy → adaptive_supervisor | 0.0003 | 4/6 of 10 | 0.9211 | 1.0000 | better_inconclusive |
| nominal | final_error_m | adaptive_legacy → adaptive_supervisor | 0.0044 | 3/7 of 10 | 0.3026 | 0.2324 | worse_inconclusive |
| nominal | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | -0.0001 | 4/6 of 10 | 0.7796 | 1.0000 | better_inconclusive |
| nominal | RMSE | pidr → adaptive_supervisor | 0.0877 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| nominal | Peak | pidr → adaptive_supervisor | 0.1753 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| nominal | MinSep | pidr → adaptive_supervisor | 0.0071 | 7/3 of 10 | 0.4493 | 0.3223 | better_inconclusive |
| nominal | final_error_m | pidr → adaptive_supervisor | 0.0511 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| nominal | cmd_dv_mean | pidr → adaptive_supervisor | 0.0884 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| nominal | RMSE | sup_observe_only → adaptive_supervisor | 0.0014 | 4/6 of 10 | 0.0558 | 0.0840 | worse_inconclusive |
| nominal | Peak | sup_observe_only → adaptive_supervisor | 0.0003 | 5/4 of 10 | 0.8881 | 0.9102 | worse_inconclusive |
| nominal | MinSep | sup_observe_only → adaptive_supervisor | 0.0006 | 5/5 of 10 | 0.8450 | 0.8457 | better_inconclusive |
| nominal | final_error_m | sup_observe_only → adaptive_supervisor | 0.0054 | 3/7 of 10 | 0.1023 | 0.1934 | worse_inconclusive |
| nominal | cmd_dv_mean | sup_observe_only → adaptive_supervisor | 0.0000 | 5/5 of 10 | 0.8396 | 0.9219 | worse_inconclusive |
| nominal | RMSE | adaptive_supervisor → sup_no_ff | -0.0014 | 6/4 of 10 | 0.0558 | 0.0840 | better_inconclusive |
| nominal | Peak | adaptive_supervisor → sup_no_ff | -0.0003 | 4/5 of 10 | 0.8881 | 0.9102 | better_inconclusive |
| nominal | MinSep | adaptive_supervisor → sup_no_ff | -0.0006 | 5/5 of 10 | 0.8450 | 0.8457 | worse_inconclusive |
| nominal | final_error_m | adaptive_supervisor → sup_no_ff | -0.0054 | 7/3 of 10 | 0.1023 | 0.1934 | better_inconclusive |
| nominal | cmd_dv_mean | adaptive_supervisor → sup_no_ff | -0.0000 | 5/5 of 10 | 0.8396 | 0.9219 | better_inconclusive |
| nominal | RMSE | adaptive_supervisor → sup_speedlimit | 0.0490 | 0/10 of 10 | 0.0020 | 0.0020 | worse_significant |
| nominal | Peak | adaptive_supervisor → sup_speedlimit | 0.0809 | 2/8 of 10 | 0.0090 | 0.0098 | worse_significant |
| nominal | MinSep | adaptive_supervisor → sup_speedlimit | -0.1048 | 1/9 of 10 | 0.0089 | 0.0137 | worse_significant |
| nominal | final_error_m | adaptive_supervisor → sup_speedlimit | 0.0111 | 6/4 of 10 | 0.2962 | 0.9219 | worse_inconclusive |
| nominal | cmd_dv_mean | adaptive_supervisor → sup_speedlimit | -0.0061 | 8/2 of 10 | 0.0130 | 0.0098 | better_significant |
| nominal | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| nominal | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| nominal | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| nominal | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| nominal | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| nominal | RMSE | pidr → adaptive_legacy | 0.0864 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| nominal | Peak | pidr → adaptive_legacy | 0.1746 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| nominal | MinSep | pidr → adaptive_legacy | 0.0068 | 6/4 of 10 | 0.4669 | 0.3223 | better_inconclusive |
| nominal | final_error_m | pidr → adaptive_legacy | 0.0467 | 0/10 of 10 | 0.0001 | 0.0020 | worse_significant |
| nominal | cmd_dv_mean | pidr → adaptive_legacy | 0.0885 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_3s | RMSE | adaptive_legacy → adaptive_supervisor | -0.0106 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_3s | Peak | adaptive_legacy → adaptive_supervisor | -0.0219 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_3s | MinSep | adaptive_legacy → adaptive_supervisor | -0.0210 | 1/9 of 10 | 0.0013 | 0.0039 | worse_significant |
| blackout_3s | final_error_m | adaptive_legacy → adaptive_supervisor | 0.0191 | 2/8 of 10 | 0.0219 | 0.0371 | worse_significant |
| blackout_3s | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | 0.0034 | 0/10 of 10 | 0.0013 | 0.0020 | worse_significant |
| blackout_3s | RMSE | pidr → adaptive_supervisor | 0.1202 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_3s | Peak | pidr → adaptive_supervisor | 0.2540 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_3s | MinSep | pidr → adaptive_supervisor | 0.0422 | 9/1 of 10 | 0.0042 | 0.0098 | better_significant |
| blackout_3s | final_error_m | pidr → adaptive_supervisor | 0.0589 | 0/10 of 10 | 0.0001 | 0.0020 | worse_significant |
| blackout_3s | cmd_dv_mean | pidr → adaptive_supervisor | 0.0853 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_3s | RMSE | sup_observe_only → adaptive_supervisor | 0.0061 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_3s | Peak | sup_observe_only → adaptive_supervisor | 0.0146 | 0/10 of 10 | 0.0001 | 0.0020 | worse_significant |
| blackout_3s | MinSep | sup_observe_only → adaptive_supervisor | 0.0218 | 10/0 of 10 | 0.0001 | 0.0020 | better_significant |
| blackout_3s | final_error_m | sup_observe_only → adaptive_supervisor | -0.0012 | 4/6 of 10 | 0.8700 | 0.9219 | better_inconclusive |
| blackout_3s | cmd_dv_mean | sup_observe_only → adaptive_supervisor | -0.0014 | 8/2 of 10 | 0.0475 | 0.0488 | better_significant |
| blackout_3s | RMSE | adaptive_supervisor → sup_no_ff | -0.0061 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_3s | Peak | adaptive_supervisor → sup_no_ff | -0.0146 | 10/0 of 10 | 0.0001 | 0.0020 | better_significant |
| blackout_3s | MinSep | adaptive_supervisor → sup_no_ff | -0.0218 | 0/10 of 10 | 0.0001 | 0.0020 | worse_significant |
| blackout_3s | final_error_m | adaptive_supervisor → sup_no_ff | 0.0012 | 6/4 of 10 | 0.8700 | 0.9219 | worse_inconclusive |
| blackout_3s | cmd_dv_mean | adaptive_supervisor → sup_no_ff | 0.0014 | 2/8 of 10 | 0.0475 | 0.0488 | worse_significant |
| blackout_3s | RMSE | adaptive_supervisor → sup_speedlimit | 0.1701 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_3s | Peak | adaptive_supervisor → sup_speedlimit | 0.4252 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_3s | MinSep | adaptive_supervisor → sup_speedlimit | -0.3722 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_3s | final_error_m | adaptive_supervisor → sup_speedlimit | 0.0146 | 4/6 of 10 | 0.3568 | 0.3223 | worse_inconclusive |
| blackout_3s | cmd_dv_mean | adaptive_supervisor → sup_speedlimit | -0.0198 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_3s | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_3s | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_3s | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_3s | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_3s | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_3s | RMSE | pidr → adaptive_legacy | 0.1308 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_3s | Peak | pidr → adaptive_legacy | 0.2759 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_3s | MinSep | pidr → adaptive_legacy | 0.0632 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_3s | final_error_m | pidr → adaptive_legacy | 0.0398 | 1/9 of 10 | 0.0005 | 0.0039 | worse_significant |
| blackout_3s | cmd_dv_mean | pidr → adaptive_legacy | 0.0819 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_6s | RMSE | adaptive_legacy → adaptive_supervisor | -0.0154 | 10/0 of 10 | 0.0005 | 0.0020 | better_significant |
| blackout_6s | Peak | adaptive_legacy → adaptive_supervisor | -0.0096 | 9/1 of 10 | 0.3144 | 0.0645 | better_inconclusive |
| blackout_6s | MinSep | adaptive_legacy → adaptive_supervisor | 0.0219 | 6/4 of 10 | 0.2287 | 0.3223 | better_inconclusive |
| blackout_6s | final_error_m | adaptive_legacy → adaptive_supervisor | 0.0360 | 2/8 of 10 | 0.0055 | 0.0098 | worse_significant |
| blackout_6s | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | 0.0018 | 1/9 of 10 | 0.2506 | 0.0840 | worse_inconclusive |
| blackout_6s | RMSE | pidr → adaptive_supervisor | 0.1525 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_6s | Peak | pidr → adaptive_supervisor | 0.1279 | 2/8 of 10 | 0.0187 | 0.0273 | worse_significant |
| blackout_6s | MinSep | pidr → adaptive_supervisor | 0.4070 | 9/1 of 10 | 0.0065 | 0.0137 | better_significant |
| blackout_6s | final_error_m | pidr → adaptive_supervisor | 0.2902 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_6s | cmd_dv_mean | pidr → adaptive_supervisor | 0.0745 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_6s | RMSE | sup_observe_only → adaptive_supervisor | -0.0045 | 7/3 of 10 | 0.1276 | 0.1055 | better_inconclusive |
| blackout_6s | Peak | sup_observe_only → adaptive_supervisor | -0.0658 | 10/0 of 10 | 0.0004 | 0.0020 | better_significant |
| blackout_6s | MinSep | sup_observe_only → adaptive_supervisor | 0.0524 | 8/2 of 10 | 0.0200 | 0.0273 | better_significant |
| blackout_6s | final_error_m | sup_observe_only → adaptive_supervisor | -0.0078 | 7/3 of 10 | 0.4768 | 0.3223 | better_inconclusive |
| blackout_6s | cmd_dv_mean | sup_observe_only → adaptive_supervisor | 0.0071 | 1/9 of 10 | 0.0075 | 0.0059 | worse_significant |
| blackout_6s | RMSE | adaptive_supervisor → sup_no_ff | 0.0045 | 3/7 of 10 | 0.1276 | 0.1055 | worse_inconclusive |
| blackout_6s | Peak | adaptive_supervisor → sup_no_ff | 0.0658 | 0/10 of 10 | 0.0004 | 0.0020 | worse_significant |
| blackout_6s | MinSep | adaptive_supervisor → sup_no_ff | -0.0524 | 2/8 of 10 | 0.0200 | 0.0273 | worse_significant |
| blackout_6s | final_error_m | adaptive_supervisor → sup_no_ff | 0.0078 | 3/7 of 10 | 0.4768 | 0.3223 | worse_inconclusive |
| blackout_6s | cmd_dv_mean | adaptive_supervisor → sup_no_ff | -0.0071 | 9/1 of 10 | 0.0075 | 0.0059 | better_significant |
| blackout_6s | RMSE | adaptive_supervisor → sup_speedlimit | 0.2487 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_6s | Peak | adaptive_supervisor → sup_speedlimit | 0.4877 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_6s | MinSep | adaptive_supervisor → sup_speedlimit | -0.4009 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_6s | final_error_m | adaptive_supervisor → sup_speedlimit | 0.0286 | 2/8 of 10 | 0.0955 | 0.1055 | worse_inconclusive |
| blackout_6s | cmd_dv_mean | adaptive_supervisor → sup_speedlimit | -0.0260 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_6s | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_6s | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_6s | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_6s | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_6s | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_6s | RMSE | pidr → adaptive_legacy | 0.1679 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_6s | Peak | pidr → adaptive_legacy | 0.1375 | 2/8 of 10 | 0.0156 | 0.0273 | worse_significant |
| blackout_6s | MinSep | pidr → adaptive_legacy | 0.3851 | 9/1 of 10 | 0.0101 | 0.0098 | better_significant |
| blackout_6s | final_error_m | pidr → adaptive_legacy | 0.2542 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_6s | cmd_dv_mean | pidr → adaptive_legacy | 0.0727 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_maneuver | RMSE | adaptive_legacy → adaptive_supervisor | -0.0006 | 7/3 of 10 | 0.1862 | 0.1934 | better_inconclusive |
| blackout_maneuver | Peak | adaptive_legacy → adaptive_supervisor | -0.0281 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_maneuver | MinSep | adaptive_legacy → adaptive_supervisor | -0.0184 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_maneuver | final_error_m | adaptive_legacy → adaptive_supervisor | 0.0093 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_maneuver | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | 0.0004 | 2/8 of 10 | 0.3493 | 0.2754 | worse_inconclusive |
| blackout_maneuver | RMSE | pidr → adaptive_supervisor | 0.0485 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_maneuver | Peak | pidr → adaptive_supervisor | 0.0236 | 1/9 of 10 | 0.0053 | 0.0137 | worse_significant |
| blackout_maneuver | MinSep | pidr → adaptive_supervisor | 0.5375 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_maneuver | final_error_m | pidr → adaptive_supervisor | -0.0909 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_maneuver | cmd_dv_mean | pidr → adaptive_supervisor | 0.0751 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_maneuver | RMSE | sup_observe_only → adaptive_supervisor | -0.0022 | 8/2 of 10 | 0.0679 | 0.0840 | better_inconclusive |
| blackout_maneuver | Peak | sup_observe_only → adaptive_supervisor | -0.0036 | 4/6 of 10 | 0.6409 | 1.0000 | better_inconclusive |
| blackout_maneuver | MinSep | sup_observe_only → adaptive_supervisor | 0.0138 | 6/4 of 10 | 0.0775 | 0.1934 | better_inconclusive |
| blackout_maneuver | final_error_m | sup_observe_only → adaptive_supervisor | -0.0123 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_maneuver | cmd_dv_mean | sup_observe_only → adaptive_supervisor | 0.0030 | 0/10 of 10 | 0.0007 | 0.0020 | worse_significant |
| blackout_maneuver | RMSE | adaptive_supervisor → sup_no_ff | 0.0022 | 2/8 of 10 | 0.0679 | 0.0840 | worse_inconclusive |
| blackout_maneuver | Peak | adaptive_supervisor → sup_no_ff | 0.0036 | 6/4 of 10 | 0.6409 | 1.0000 | worse_inconclusive |
| blackout_maneuver | MinSep | adaptive_supervisor → sup_no_ff | -0.0138 | 4/6 of 10 | 0.0775 | 0.1934 | worse_inconclusive |
| blackout_maneuver | final_error_m | adaptive_supervisor → sup_no_ff | 0.0123 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_maneuver | cmd_dv_mean | adaptive_supervisor → sup_no_ff | -0.0030 | 10/0 of 10 | 0.0007 | 0.0020 | better_significant |
| blackout_maneuver | RMSE | adaptive_supervisor → sup_speedlimit | 0.1072 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_maneuver | Peak | adaptive_supervisor → sup_speedlimit | 0.2533 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_maneuver | MinSep | adaptive_supervisor → sup_speedlimit | -0.0074 | 2/8 of 10 | 0.0540 | 0.0371 | worse_inconclusive |
| blackout_maneuver | final_error_m | adaptive_supervisor → sup_speedlimit | -0.0090 | 7/3 of 10 | 0.5584 | 0.4922 | better_inconclusive |
| blackout_maneuver | cmd_dv_mean | adaptive_supervisor → sup_speedlimit | -0.0172 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_maneuver | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_maneuver | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_maneuver | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_maneuver | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_maneuver | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_maneuver | RMSE | pidr → adaptive_legacy | 0.0492 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_maneuver | Peak | pidr → adaptive_legacy | 0.0517 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_maneuver | MinSep | pidr → adaptive_legacy | 0.5559 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_maneuver | final_error_m | pidr → adaptive_legacy | -0.1003 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_maneuver | cmd_dv_mean | pidr → adaptive_legacy | 0.0747 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| random_loss_30 | RMSE | adaptive_legacy → adaptive_supervisor | 0.0050 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| random_loss_30 | Peak | adaptive_legacy → adaptive_supervisor | 0.0103 | 0/10 of 10 | 0.0002 | 0.0020 | worse_significant |
| random_loss_30 | MinSep | adaptive_legacy → adaptive_supervisor | 0.0207 | 10/0 of 10 | 0.0006 | 0.0020 | better_significant |
| random_loss_30 | final_error_m | adaptive_legacy → adaptive_supervisor | -0.0020 | 7/3 of 10 | 0.6573 | 0.5566 | better_inconclusive |
| random_loss_30 | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | 0.0004 | 2/8 of 10 | 0.1235 | 0.1309 | worse_inconclusive |
| random_loss_30 | RMSE | pidr → adaptive_supervisor | 0.0918 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| random_loss_30 | Peak | pidr → adaptive_supervisor | 0.1858 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| random_loss_30 | MinSep | pidr → adaptive_supervisor | 0.0283 | 9/1 of 10 | 0.0089 | 0.0195 | better_significant |
| random_loss_30 | final_error_m | pidr → adaptive_supervisor | 0.0492 | 0/10 of 10 | 0.0001 | 0.0020 | worse_significant |
| random_loss_30 | cmd_dv_mean | pidr → adaptive_supervisor | 0.0888 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| random_loss_30 | RMSE | sup_observe_only → adaptive_supervisor | 0.0055 | 0/10 of 10 | 0.0001 | 0.0020 | worse_significant |
| random_loss_30 | Peak | sup_observe_only → adaptive_supervisor | 0.0097 | 0/10 of 10 | 0.0005 | 0.0020 | worse_significant |
| random_loss_30 | MinSep | sup_observe_only → adaptive_supervisor | 0.0198 | 9/1 of 10 | 0.0010 | 0.0059 | better_significant |
| random_loss_30 | final_error_m | sup_observe_only → adaptive_supervisor | -0.0001 | 6/4 of 10 | 0.9770 | 0.8457 | better_inconclusive |
| random_loss_30 | cmd_dv_mean | sup_observe_only → adaptive_supervisor | 0.0005 | 3/7 of 10 | 0.1438 | 0.1602 | worse_inconclusive |
| random_loss_30 | RMSE | adaptive_supervisor → sup_no_ff | -0.0055 | 10/0 of 10 | 0.0001 | 0.0020 | better_significant |
| random_loss_30 | Peak | adaptive_supervisor → sup_no_ff | -0.0097 | 10/0 of 10 | 0.0005 | 0.0020 | better_significant |
| random_loss_30 | MinSep | adaptive_supervisor → sup_no_ff | -0.0198 | 1/9 of 10 | 0.0010 | 0.0059 | worse_significant |
| random_loss_30 | final_error_m | adaptive_supervisor → sup_no_ff | 0.0001 | 4/6 of 10 | 0.9770 | 0.8457 | worse_inconclusive |
| random_loss_30 | cmd_dv_mean | adaptive_supervisor → sup_no_ff | -0.0005 | 7/3 of 10 | 0.1438 | 0.1602 | better_inconclusive |
| random_loss_30 | RMSE | adaptive_supervisor → sup_speedlimit | 0.1136 | 0/10 of 10 | 0.0001 | 0.0020 | worse_significant |
| random_loss_30 | Peak | adaptive_supervisor → sup_speedlimit | 0.1459 | 1/9 of 10 | 0.0013 | 0.0039 | worse_significant |
| random_loss_30 | MinSep | adaptive_supervisor → sup_speedlimit | -0.1913 | 2/8 of 10 | 0.0017 | 0.0098 | worse_significant |
| random_loss_30 | final_error_m | adaptive_supervisor → sup_speedlimit | 0.0588 | 0/10 of 10 | 0.0001 | 0.0020 | worse_significant |
| random_loss_30 | cmd_dv_mean | adaptive_supervisor → sup_speedlimit | -0.0154 | 10/0 of 10 | 0.0029 | 0.0020 | better_significant |
| random_loss_30 | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| random_loss_30 | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| random_loss_30 | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| random_loss_30 | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| random_loss_30 | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| random_loss_30 | RMSE | pidr → adaptive_legacy | 0.0868 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| random_loss_30 | Peak | pidr → adaptive_legacy | 0.1755 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| random_loss_30 | MinSep | pidr → adaptive_legacy | 0.0077 | 7/3 of 10 | 0.4163 | 0.3223 | better_inconclusive |
| random_loss_30 | final_error_m | pidr → adaptive_legacy | 0.0512 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| random_loss_30 | cmd_dv_mean | pidr → adaptive_legacy | 0.0884 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| burst_loss | RMSE | adaptive_legacy → adaptive_supervisor | -0.0069 | 9/1 of 10 | 0.0063 | 0.0059 | better_significant |
| burst_loss | Peak | adaptive_legacy → adaptive_supervisor | -0.0141 | 9/1 of 10 | 0.0030 | 0.0039 | better_significant |
| burst_loss | MinSep | adaptive_legacy → adaptive_supervisor | -0.0197 | 5/5 of 10 | 0.2292 | 0.4922 | worse_inconclusive |
| burst_loss | final_error_m | adaptive_legacy → adaptive_supervisor | -0.0030 | 3/7 of 10 | 0.8159 | 0.8457 | better_inconclusive |
| burst_loss | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | 0.0033 | 1/9 of 10 | 0.0022 | 0.0059 | worse_significant |
| burst_loss | RMSE | pidr → adaptive_supervisor | 0.0943 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| burst_loss | Peak | pidr → adaptive_supervisor | 0.1861 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| burst_loss | MinSep | pidr → adaptive_supervisor | 0.0190 | 8/2 of 10 | 0.0302 | 0.0371 | better_significant |
| burst_loss | final_error_m | pidr → adaptive_supervisor | 0.0379 | 1/9 of 10 | 0.0014 | 0.0059 | worse_significant |
| burst_loss | cmd_dv_mean | pidr → adaptive_supervisor | 0.0879 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| burst_loss | RMSE | sup_observe_only → adaptive_supervisor | 0.0072 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| burst_loss | Peak | sup_observe_only → adaptive_supervisor | 0.0116 | 2/8 of 10 | 0.0023 | 0.0098 | worse_significant |
| burst_loss | MinSep | sup_observe_only → adaptive_supervisor | 0.0270 | 10/0 of 10 | 0.0003 | 0.0020 | better_significant |
| burst_loss | final_error_m | sup_observe_only → adaptive_supervisor | -0.0063 | 6/4 of 10 | 0.2481 | 0.3223 | better_inconclusive |
| burst_loss | cmd_dv_mean | sup_observe_only → adaptive_supervisor | 0.0004 | 2/8 of 10 | 0.3233 | 0.1934 | worse_inconclusive |
| burst_loss | RMSE | adaptive_supervisor → sup_no_ff | -0.0072 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| burst_loss | Peak | adaptive_supervisor → sup_no_ff | -0.0116 | 8/2 of 10 | 0.0023 | 0.0098 | better_significant |
| burst_loss | MinSep | adaptive_supervisor → sup_no_ff | -0.0270 | 0/10 of 10 | 0.0003 | 0.0020 | worse_significant |
| burst_loss | final_error_m | adaptive_supervisor → sup_no_ff | 0.0063 | 4/6 of 10 | 0.2481 | 0.3223 | worse_inconclusive |
| burst_loss | cmd_dv_mean | adaptive_supervisor → sup_no_ff | -0.0004 | 8/2 of 10 | 0.3233 | 0.1934 | better_inconclusive |
| burst_loss | RMSE | adaptive_supervisor → sup_speedlimit | 0.1472 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| burst_loss | Peak | adaptive_supervisor → sup_speedlimit | 0.2208 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| burst_loss | MinSep | adaptive_supervisor → sup_speedlimit | -0.2820 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| burst_loss | final_error_m | adaptive_supervisor → sup_speedlimit | 0.0667 | 1/9 of 10 | 0.0002 | 0.0039 | worse_significant |
| burst_loss | cmd_dv_mean | adaptive_supervisor → sup_speedlimit | -0.0217 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| burst_loss | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| burst_loss | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| burst_loss | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| burst_loss | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| burst_loss | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| burst_loss | RMSE | pidr → adaptive_legacy | 0.1011 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| burst_loss | Peak | pidr → adaptive_legacy | 0.2002 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| burst_loss | MinSep | pidr → adaptive_legacy | 0.0386 | 8/2 of 10 | 0.0429 | 0.0488 | better_significant |
| burst_loss | final_error_m | pidr → adaptive_legacy | 0.0409 | 0/10 of 10 | 0.0001 | 0.0020 | worse_significant |
| burst_loss | cmd_dv_mean | pidr → adaptive_legacy | 0.0846 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | RMSE | adaptive_legacy → adaptive_supervisor | -0.0025 | 9/1 of 10 | 0.0110 | 0.0195 | better_significant |
| latency_jitter | Peak | adaptive_legacy → adaptive_supervisor | -0.0112 | 10/0 of 10 | 0.0008 | 0.0020 | better_significant |
| latency_jitter | MinSep | adaptive_legacy → adaptive_supervisor | -0.0194 | 0/10 of 10 | 0.0021 | 0.0020 | worse_significant |
| latency_jitter | final_error_m | adaptive_legacy → adaptive_supervisor | 0.0091 | 3/7 of 10 | 0.1727 | 0.2754 | worse_inconclusive |
| latency_jitter | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | 0.0018 | 1/9 of 10 | 0.0011 | 0.0039 | worse_significant |
| latency_jitter | RMSE | pidr → adaptive_supervisor | 0.0946 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | Peak | pidr → adaptive_supervisor | 0.1868 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | MinSep | pidr → adaptive_supervisor | 0.0191 | 9/1 of 10 | 0.0547 | 0.0488 | better_inconclusive |
| latency_jitter | final_error_m | pidr → adaptive_supervisor | 0.0559 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | cmd_dv_mean | pidr → adaptive_supervisor | 0.0888 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | RMSE | sup_observe_only → adaptive_supervisor | 0.0076 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | Peak | sup_observe_only → adaptive_supervisor | 0.0111 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | MinSep | sup_observe_only → adaptive_supervisor | 0.0227 | 10/0 of 10 | 0.0001 | 0.0020 | better_significant |
| latency_jitter | final_error_m | sup_observe_only → adaptive_supervisor | 0.0075 | 2/8 of 10 | 0.1657 | 0.2324 | worse_inconclusive |
| latency_jitter | cmd_dv_mean | sup_observe_only → adaptive_supervisor | 0.0010 | 1/9 of 10 | 0.0050 | 0.0195 | worse_significant |
| latency_jitter | RMSE | adaptive_supervisor → sup_no_ff | -0.0076 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| latency_jitter | Peak | adaptive_supervisor → sup_no_ff | -0.0111 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| latency_jitter | MinSep | adaptive_supervisor → sup_no_ff | -0.0227 | 0/10 of 10 | 0.0001 | 0.0020 | worse_significant |
| latency_jitter | final_error_m | adaptive_supervisor → sup_no_ff | -0.0075 | 8/2 of 10 | 0.1657 | 0.2324 | better_inconclusive |
| latency_jitter | cmd_dv_mean | adaptive_supervisor → sup_no_ff | -0.0010 | 9/1 of 10 | 0.0050 | 0.0195 | better_significant |
| latency_jitter | RMSE | adaptive_supervisor → sup_speedlimit | 0.1537 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | Peak | adaptive_supervisor → sup_speedlimit | 0.2099 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | MinSep | adaptive_supervisor → sup_speedlimit | -0.2776 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | final_error_m | adaptive_supervisor → sup_speedlimit | 0.0799 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | cmd_dv_mean | adaptive_supervisor → sup_speedlimit | -0.0227 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| latency_jitter | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| latency_jitter | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| latency_jitter | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| latency_jitter | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| latency_jitter | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| latency_jitter | RMSE | pidr → adaptive_legacy | 0.0972 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | Peak | pidr → adaptive_legacy | 0.1981 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | MinSep | pidr → adaptive_legacy | 0.0385 | 9/1 of 10 | 0.0008 | 0.0039 | better_significant |
| latency_jitter | final_error_m | pidr → adaptive_legacy | 0.0468 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_jitter | cmd_dv_mean | pidr → adaptive_legacy | 0.0870 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_then_blackout | RMSE | adaptive_legacy → adaptive_supervisor | -0.0112 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| latency_then_blackout | Peak | adaptive_legacy → adaptive_supervisor | -0.0291 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| latency_then_blackout | MinSep | adaptive_legacy → adaptive_supervisor | -0.0051 | 2/7 of 10 | 0.1748 | 0.1641 | worse_inconclusive |
| latency_then_blackout | final_error_m | adaptive_legacy → adaptive_supervisor | -0.0078 | 3/7 of 10 | 0.5878 | 0.8457 | better_inconclusive |
| latency_then_blackout | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | 0.0058 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_then_blackout | RMSE | pidr → adaptive_supervisor | 0.1277 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_then_blackout | Peak | pidr → adaptive_supervisor | 0.2727 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_then_blackout | MinSep | pidr → adaptive_supervisor | 0.0960 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| latency_then_blackout | final_error_m | pidr → adaptive_supervisor | 0.0597 | 0/10 of 10 | 0.0001 | 0.0020 | worse_significant |
| latency_then_blackout | cmd_dv_mean | pidr → adaptive_supervisor | 0.0869 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_then_blackout | RMSE | sup_observe_only → adaptive_supervisor | 0.0096 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_then_blackout | Peak | sup_observe_only → adaptive_supervisor | 0.0318 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_then_blackout | MinSep | sup_observe_only → adaptive_supervisor | 0.0192 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| latency_then_blackout | final_error_m | sup_observe_only → adaptive_supervisor | -0.0104 | 6/4 of 10 | 0.2030 | 0.3223 | better_inconclusive |
| latency_then_blackout | cmd_dv_mean | sup_observe_only → adaptive_supervisor | -0.0011 | 7/3 of 10 | 0.1776 | 0.1934 | better_inconclusive |
| latency_then_blackout | RMSE | adaptive_supervisor → sup_no_ff | -0.0096 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| latency_then_blackout | Peak | adaptive_supervisor → sup_no_ff | -0.0318 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| latency_then_blackout | MinSep | adaptive_supervisor → sup_no_ff | -0.0192 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_then_blackout | final_error_m | adaptive_supervisor → sup_no_ff | 0.0104 | 4/6 of 10 | 0.2030 | 0.3223 | worse_inconclusive |
| latency_then_blackout | cmd_dv_mean | adaptive_supervisor → sup_no_ff | 0.0011 | 3/7 of 10 | 0.1776 | 0.1934 | worse_inconclusive |
| latency_then_blackout | RMSE | adaptive_supervisor → sup_speedlimit | 0.1980 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_then_blackout | Peak | adaptive_supervisor → sup_speedlimit | 0.4464 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_then_blackout | MinSep | adaptive_supervisor → sup_speedlimit | -0.4902 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_then_blackout | final_error_m | adaptive_supervisor → sup_speedlimit | 0.0394 | 4/6 of 10 | 0.0336 | 0.0840 | worse_inconclusive |
| latency_then_blackout | cmd_dv_mean | adaptive_supervisor → sup_speedlimit | -0.0295 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| latency_then_blackout | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| latency_then_blackout | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| latency_then_blackout | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| latency_then_blackout | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| latency_then_blackout | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| latency_then_blackout | RMSE | pidr → adaptive_legacy | 0.1389 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_then_blackout | Peak | pidr → adaptive_legacy | 0.3018 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| latency_then_blackout | MinSep | pidr → adaptive_legacy | 0.1011 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| latency_then_blackout | final_error_m | pidr → adaptive_legacy | 0.0675 | 0/10 of 10 | 0.0001 | 0.0020 | worse_significant |
| latency_then_blackout | cmd_dv_mean | pidr → adaptive_legacy | 0.0811 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| nominal_gentle | RMSE | adaptive_legacy → adaptive_supervisor | -0.0016 | 8/2 of 10 | 0.0997 | 0.0840 | better_inconclusive |
| nominal_gentle | Peak | adaptive_legacy → adaptive_supervisor | 0.0002 | 0/2 of 10 | 0.2075 | 0.5000 | worse_inconclusive |
| nominal_gentle | MinSep | adaptive_legacy → adaptive_supervisor | -0.0026 | 1/3 of 10 | 0.1028 | 0.2500 | worse_inconclusive |
| nominal_gentle | final_error_m | adaptive_legacy → adaptive_supervisor | 0.0069 | 1/9 of 10 | 0.0058 | 0.0059 | worse_significant |
| nominal_gentle | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | -0.0003 | 7/3 of 10 | 0.1758 | 0.1602 | better_inconclusive |
| nominal_gentle | RMSE | pidr → adaptive_supervisor | -0.0113 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| nominal_gentle | Peak | pidr → adaptive_supervisor | -0.0121 | 10/0 of 10 | 0.0313 | 0.0020 | better_significant |
| nominal_gentle | MinSep | pidr → adaptive_supervisor | 0.0172 | 9/0 of 10 | 0.1084 | 0.0039 | better_inconclusive |
| nominal_gentle | final_error_m | pidr → adaptive_supervisor | -0.0263 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| nominal_gentle | cmd_dv_mean | pidr → adaptive_supervisor | 0.0135 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| nominal_gentle | RMSE | sup_observe_only → adaptive_supervisor | -0.0014 | 7/3 of 10 | 0.1656 | 0.1602 | better_inconclusive |
| nominal_gentle | Peak | sup_observe_only → adaptive_supervisor | 0.0003 | 0/2 of 10 | 0.2322 | 0.5000 | worse_inconclusive |
| nominal_gentle | MinSep | sup_observe_only → adaptive_supervisor | -0.0024 | 0/4 of 10 | 0.1139 | 0.1250 | worse_inconclusive |
| nominal_gentle | final_error_m | sup_observe_only → adaptive_supervisor | 0.0069 | 2/8 of 10 | 0.0049 | 0.0098 | worse_significant |
| nominal_gentle | cmd_dv_mean | sup_observe_only → adaptive_supervisor | -0.0004 | 6/4 of 10 | 0.1475 | 0.1934 | better_inconclusive |
| nominal_gentle | RMSE | adaptive_supervisor → sup_no_ff | 0.0014 | 3/7 of 10 | 0.1656 | 0.1602 | worse_inconclusive |
| nominal_gentle | Peak | adaptive_supervisor → sup_no_ff | -0.0003 | 2/0 of 10 | 0.2322 | 0.5000 | better_inconclusive |
| nominal_gentle | MinSep | adaptive_supervisor → sup_no_ff | 0.0024 | 4/0 of 10 | 0.1139 | 0.1250 | better_inconclusive |
| nominal_gentle | final_error_m | adaptive_supervisor → sup_no_ff | -0.0069 | 8/2 of 10 | 0.0049 | 0.0098 | better_significant |
| nominal_gentle | cmd_dv_mean | adaptive_supervisor → sup_no_ff | 0.0004 | 4/6 of 10 | 0.1475 | 0.1934 | worse_inconclusive |
| nominal_gentle | RMSE | adaptive_supervisor → sup_speedlimit | 0.0002 | 4/6 of 10 | 0.7024 | 0.6953 | worse_inconclusive |
| nominal_gentle | Peak | adaptive_supervisor → sup_speedlimit | 0.0003 | 1/1 of 10 | 0.4325 | 1.0000 | worse_inconclusive |
| nominal_gentle | MinSep | adaptive_supervisor → sup_speedlimit | 0.0015 | 2/2 of 10 | 0.3788 | 0.6250 | better_inconclusive |
| nominal_gentle | final_error_m | adaptive_supervisor → sup_speedlimit | 0.0045 | 2/8 of 10 | 0.1781 | 0.0840 | worse_inconclusive |
| nominal_gentle | cmd_dv_mean | adaptive_supervisor → sup_speedlimit | -0.0122 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| nominal_gentle | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| nominal_gentle | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| nominal_gentle | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| nominal_gentle | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| nominal_gentle | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| nominal_gentle | RMSE | pidr → adaptive_legacy | -0.0097 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| nominal_gentle | Peak | pidr → adaptive_legacy | -0.0123 | 10/0 of 10 | 0.0320 | 0.0020 | better_significant |
| nominal_gentle | MinSep | pidr → adaptive_legacy | 0.0198 | 9/0 of 10 | 0.0697 | 0.0039 | better_inconclusive |
| nominal_gentle | final_error_m | pidr → adaptive_legacy | -0.0332 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| nominal_gentle | cmd_dv_mean | pidr → adaptive_legacy | 0.0138 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_gentle | RMSE | adaptive_legacy → adaptive_supervisor | -0.0452 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_gentle | Peak | adaptive_legacy → adaptive_supervisor | -0.1379 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_gentle | MinSep | adaptive_legacy → adaptive_supervisor | 0.0116 | 7/0 of 10 | 0.0167 | 0.0156 | better_inconclusive |
| blackout_gentle | final_error_m | adaptive_legacy → adaptive_supervisor | -0.0114 | 10/0 of 10 | 0.0038 | 0.0020 | better_significant |
| blackout_gentle | cmd_dv_mean | adaptive_legacy → adaptive_supervisor | 0.0087 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_gentle | RMSE | pidr → adaptive_supervisor | 0.0260 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_gentle | Peak | pidr → adaptive_supervisor | 0.0958 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_gentle | MinSep | pidr → adaptive_supervisor | 0.0080 | 6/4 of 10 | 0.4400 | 0.6953 | better_inconclusive |
| blackout_gentle | final_error_m | pidr → adaptive_supervisor | -0.0142 | 9/1 of 10 | 0.0075 | 0.0059 | better_significant |
| blackout_gentle | cmd_dv_mean | pidr → adaptive_supervisor | 0.0093 | 0/10 of 10 | 0.0001 | 0.0020 | worse_significant |
| blackout_gentle | RMSE | sup_observe_only → adaptive_supervisor | 0.0460 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_gentle | Peak | sup_observe_only → adaptive_supervisor | 0.1317 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_gentle | MinSep | sup_observe_only → adaptive_supervisor | -0.0100 | 0/6 of 10 | 0.0342 | 0.0312 | worse_inconclusive |
| blackout_gentle | final_error_m | sup_observe_only → adaptive_supervisor | 0.0182 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_gentle | cmd_dv_mean | sup_observe_only → adaptive_supervisor | -0.0050 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_gentle | RMSE | adaptive_supervisor → sup_no_ff | -0.0460 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_gentle | Peak | adaptive_supervisor → sup_no_ff | -0.1317 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_gentle | MinSep | adaptive_supervisor → sup_no_ff | 0.0100 | 6/0 of 10 | 0.0342 | 0.0312 | better_inconclusive |
| blackout_gentle | final_error_m | adaptive_supervisor → sup_no_ff | -0.0182 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_gentle | cmd_dv_mean | adaptive_supervisor → sup_no_ff | 0.0050 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_gentle | RMSE | adaptive_supervisor → sup_speedlimit | 0.0315 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_gentle | Peak | adaptive_supervisor → sup_speedlimit | 0.0367 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_gentle | MinSep | adaptive_supervisor → sup_speedlimit | -0.0075 | 1/5 of 10 | 0.0778 | 0.0625 | worse_inconclusive |
| blackout_gentle | final_error_m | adaptive_supervisor → sup_speedlimit | 0.0110 | 1/9 of 10 | 0.0094 | 0.0039 | worse_significant |
| blackout_gentle | cmd_dv_mean | adaptive_supervisor → sup_speedlimit | -0.0407 | 10/0 of 10 | 0.0000 | 0.0020 | better_significant |
| blackout_gentle | RMSE | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_gentle | Peak | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_gentle | MinSep | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_gentle | final_error_m | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_gentle | cmd_dv_mean | adaptive_supervisor → sup_no_avoid | 0.0000 | 0/0 of 10 | n/a | n/a | identical |
| blackout_gentle | RMSE | pidr → adaptive_legacy | 0.0712 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_gentle | Peak | pidr → adaptive_legacy | 0.2337 | 0/10 of 10 | 0.0000 | 0.0020 | worse_significant |
| blackout_gentle | MinSep | pidr → adaptive_legacy | -0.0036 | 4/6 of 10 | 0.7552 | 0.3223 | worse_inconclusive |
| blackout_gentle | final_error_m | pidr → adaptive_legacy | -0.0028 | 6/4 of 10 | 0.6083 | 0.5566 | better_inconclusive |
| blackout_gentle | cmd_dv_mean | pidr → adaptive_legacy | 0.0006 | 3/7 of 10 | 0.5974 | 0.5566 | worse_inconclusive |
