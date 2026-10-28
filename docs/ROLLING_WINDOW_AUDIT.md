# Audit of the rolling communication-quality estimator (backend)

Separate from the frontend panel (`ROLLING_WINDOW_UI_FIX.md`). Code: `simulation/simulation.py::_deliver`, `::_link_quality`; `agent.py::pose_delivery_window` (deque, maxlen 40);
`config.py::supervisor_min_loss_window = 20`; `controller.py::estimate_communication_quality`; `supervisor.py`.
Environment: Python 3.12.3, numpy 2.4.4, scipy 1.17.1, Linux sandbox, engine code **unchanged**. Not run on Windows. Full pytest suite not run (pytest not installable offline).

## How the estimator works (read from code, then confirmed by trace)
* Leader broadcasts a POSE_UPDATE every step (dt = 0.05 s) with a sample counter `pose_seq`.
* A follower appends to its window **only when a packet is delivered** (`_deliver`): `missed = pose_seq - last - 1` samples are appended as `True` (capped at the window length 40), then one `False` for the delivered sample.
* Packets with `msg.sequence <= rx_seq` (duplicates, late/out-of-order) are dropped and do not touch the window or `rx_time`.
* `loss = sum(window) / denom`. In `adaptive_comm` with the supervisor on, `denom = max(len(window), min(20, 40))`. quality = `(1 - loss) * exp(-age/0.8)`-type bounded score (`estimate_communication_quality`, tested bounded in [0,1]).

## Findings
| # | Question | Result | Classification |
|---|---|---|---|
| 1 | Is the denominator padded during warm-up? | **Yes**, to 20 samples, adaptive_comm + supervisor only. One miss + one hit = 5 % loss instead of the observed 50 %. Pinned by test. | Deliberate smoothing (documented in `config.py`). Underestimates early loss. |
| 2 | Does padding change behaviour? | No measurable effect (below). Mean quality differs by 0.007; RMSE, min separation, HOLD fraction, recovery time identical. | Harmless on tested scenarios. |
| 3 | Updated on missing packets? | **No: delivery-driven.** During a total outage the window is frozen (trace: raw loss 0.57 constant from t=5.05 to 8.10 s while true loss was 100 %). Misses are booked in one jump when the next packet arrives. | **Confirmed limitation**, not a behavioural defect: message age (which keeps growing) drives quality to ~0 and the supervisor to HOLD. |
| 4 | Sequence gaps / duplicates / out-of-order | Gaps counted exactly (capped at window length). Duplicates and late packets ignored, not double counted; a late packet that was already booked as missed stays a miss ("not received in order"). | Correct under that definition. |
| 5 | Eviction | Correct (deque maxlen); W consecutive successes evict every miss. | OK |
| 6 | Loss high after communication returns? | **Yes, by construction:** after the 3 s blackout the loss jumps 0.57 -> 0.93 on the first packet and decays over ~40 samples (2 s). Quality at t_restore+0.3 s = 0.07, +1.5 s = 0.31, +2.0 s = 0.53 while message age is already ~0.1 s. | Smoothing choice (2 s window memory). It, together with supervisor dwell/ramp, sets the ~2.5 s time-to-NORMAL; see 7. |
| 7 | Is that lag caused by the estimator? | Not separable from the supervisor ramp with these variants: removing padding or making the estimator real-time left time-to-NORMAL unchanged at 2.53 s. A shorter window or a loss reset on recovery was **not** tested and would be threshold tuning. | Open |
| 8 | Per-follower isolation | Each follower has its own window; a gap for follower 1 leaves follower 2 untouched (test). | OK |
| 9 | Nominal channel | With no fault the raw window loss is already 0.25-0.57 (Gilbert-Elliott channel) and mean quality is ~0.57. The supervisor thresholds are calibrated around this (see `SupervisorConfig` note). | Context |

## Measured comparison (`docs/evidence/estimator_compare.py`, output `estimator_compare.json`)
Identical seeds 100-109 (tuning seeds, not evaluation seeds 42-51), `adaptive_comm`, default path, 14 s, forced total blackout 5-8 s for the blackout scenario.
Variants: **current**; **nopad** (`supervisor_min_loss_window=1`); **realtime** (window plus samples overdue by more than 4 steps counted as pending misses, grace = max nominal latency; monkeypatched in the script only).
Mean over 10 seeds; paired difference vs current with 95 % t-interval. **Exploratory**, uncorrected.

| scenario | variant | RMSE [m] | min sep [m] | mean quality | HOLD frac | time to all-NORMAL after restore [s] | collision samples |
|---|---|---|---|---|---|---|---|
| nominal | current | 1.600 | 1.114 | 0.570 | 0 | - | 0 |
| nominal | nopad | 1.600 (d 0) | 1.114 (d 0) | 0.563 (d -0.007 [-0.007,-0.006]) | 0 | - | 0 |
| nominal | realtime | 1.600 (d +0.000) | 1.115 (d +0.001) | 0.568 (d -0.002) | 0 | - | 0 |
| blackout 3 s | current | 1.683 | 1.130 | 0.452 | 0.156 | 2.530 | 0 |
| blackout 3 s | nopad | 1.683 (d 0) | 1.130 (d 0) | 0.445 (d -0.007) | 0.156 | 2.530 | 0 |
| blackout 3 s | realtime | 1.683 (d +0.000) | 1.130 (d +0.000) | 0.443 (d -0.009) | 0.156 | 2.530 | 0 |

Adaptive feed-forward scaling and supervisor transitions were not compared separately: state fractions and recovery time are identical, and quality moves by < 0.01.

## Decision
**No change to the estimator.** No behavioural defect was confirmed; the padding and the frozen-outage behaviour are real but have no measurable effect on tracking, safety or recovery here. A time-driven estimator would be more honest as a *diagnostic* (the dashboard's "estimated loss" lags reality by up to the outage length) - recommended only if that plot is used for decisions.
The existing supervisor already is a per-follower NORMAL/DEGRADED/HOLD/RECOVERING state machine, so no second recovery system was added.

## Limitations of this audit
* The default leader path is infeasible for outer slots (RMSE 1.6 m even nominally, HANDOFF finding 4), which can mask estimator effects. The `*_gentle` scenarios are the more sensitive test and were **not** run here; do that before concluding the estimator is irrelevant.
* One scenario (3 s forced blackout), one controller, 10 seeds; no burst/latency-jitter/repeated-interruption schedules.
* Regression tests: `tests/test_loss_estimator.py` (9 tests, all passed when run with a plain-Python runner; **not** with real pytest). One test pins the frozen-window limitation: if the estimator is later made time-driven, update that test deliberately.
