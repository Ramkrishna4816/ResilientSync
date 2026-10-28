# Experiment protocol — resilience benchmark

All numbers quoted in this project come from `experiments/run_benchmark.py`; the
files in `experiments/results_resilience/eval/` (first round, 800 runs, preserved untouched) and
`experiments/results_resilience/eval_v2/` (second round, adds connectivity / consensus metrics and two
feasibility scenarios) are the measured outputs of the commands in section 6. Nothing is edited by hand.

## 1. Controllers (arms)

| arm | definition |
|---|---|
| `zoh` | zero-order hold of the last leader packet (original baseline) |
| `pidr` | PID tracking of a dead-reckoned leader slot (original baseline) |
| `advanced` | PIDR + neighbour coupling + avoidance + gain scheduling (original baseline) |
| `adaptive_legacy` | `adaptive_comm` with `supervisor_enabled=False`: feed-forward scaled when quality < 0.30 (the prototype *after* the total-speed cap was removed) |
| `adaptive_capped` | `adaptive_legacy` + `adaptive_comm_total_speed_cap=True` — the earlier prototype that produced 2.289 m RMSE; kept only as a record |
| `adaptive_supervisor` | `adaptive_comm` + resilience supervisor with the shipped defaults (the new controller) |
| `sup_observe_only` | supervisor runs, all modifiers neutral (control arm; numerically equal to `advanced`) |
| `sup_no_ff`, `sup_no_avoid` | supervisor with one modifier neutralised |
| `sup_speedlimit` | supervisor with the first-design HOLD speed limit of 0.8 × max speed |

## 2. Resilience supervisor (per follower)

States NORMAL / DEGRADED / HOLD / RECOVERING (`simulation/supervisor.py`).
Inputs: communication quality `q` (age × (1 − inferred loss)) and age of the
newest usable leader message. Legal transitions: NORMAL→{DEGRADED,HOLD},
DEGRADED→{NORMAL,HOLD}, HOLD→RECOVERING, RECOVERING→{NORMAL,HOLD}.
Hysteresis: q enter 0.35 / exit 0.50; HOLD age enter 1.25 s / exit 0.50 s;
dwell 0.10 s (degrade), 0.50 s (return), 0.30 s (leave HOLD), 0.25 s minimum
time before de-escalating. Output: a caution level c∈[0,1] (fast rise, 1.5 s
ramp down) scaling feed-forward (×0.6 at c=1), avoidance gain (×1.5 at c=1)
and the speed limit (×1.0 by default). Commands are always clipped by the
simulator's actuator limits; the supervisor can never command a stop.
Thresholds were calibrated on the *nominal* channel (see the docstring of
`SupervisorConfig`).

## 3. Fault models (`simulation/network.py`, `FaultEvent` / `FaultProfile`)

| scenario | fault |
|---|---|
| `nominal` | none (default Gilbert–Elliott channel only) |
| `blackout_3s` | 100 % loss, t = 5–8 s (the original benchmark) |
| `blackout_6s` | 100 % loss, t = 4–10 s |
| `blackout_maneuver` | blackout t = 5–8 s while the leader stops (5.5–6.5 s) then turns (6.5–7.5 s): stale dead-reckoning is wrong |
| `random_loss_30` | extra independent 30 % loss, t = 4–12 s |
| `burst_loss` | per-link two-state chain, p(g→b)=p(b→g)=0.15, loss 100 % in bad state, t = 4–12 s |
| `latency_jitter` | +0.4 s ± 0.2 s uniform, t = 4–12 s |
| `latency_then_blackout` | +0.3 s ± 0.15 s for 3 s, then 3 s blackout (t = 3–9 s) |

Faults are applied inside `Network.transmit`; blackout reuses the existing
forced-loss mechanism (identical RNG stream — verified by test), other faults
use separate seeded generators per link, so all arms see the same channel
realisation. Start/end edges are logged in `Network.fault_log`.

## 4. Seeds

* **Evaluation seeds: 42–51** (10 seeds). Initial follower offsets, channel RNG
  and sensor noise are functions of the seed only; arms are therefore paired.
* **Tuning seeds: 100–109** were used *only* to calibrate supervisor thresholds
  and to choose the HOLD fallback strength (`experiments/results_resilience/tuning_*`).
  No parameter was tuned on the evaluation seeds. (Seeds 42–44 are the seeds of the
  original benchmark.)

## 5. Metrics

Formation RMSE and peak error (`compute_metrics`, unchanged); minimum inter-agent
separation; collision % of samples and number of collision events; post-fault
minimum error and final error; recovery (below); supervisor transition count and
seconds per state (mean per follower); command smoothness = mean |Δv_cmd| and
|Δω_cmd| per step over followers; mean/min communication quality; max message age.

**Recovery criterion — unchanged from `simulation/metrics.py::compute_recovery_metrics`:**
baseline = median error in the 1 s before the fault; threshold = max(0.5 m,
1.25 × baseline); recovered when the error stays ≤ threshold for 0.5 s after the
fault window ends. Recovery time is reported only for runs that satisfy it;
other runs are `not_recovered`; scenarios without a finite fault window or with
fewer than 0.5 s after it are `not_applicable`.

**Collision definition — unchanged:** minimum pairwise distance < `Config.collision_distance` (0.38 m).

## 6. Procedure

```bash
python -m experiments.run_benchmark --tag eval --workers 2         # ~3 min on 2 cores
python -m experiments.run_benchmark --seeds 100 101 102 103 104 --tag tuning_check --no-plots
python -m experiments.run_benchmark --quick                         # ~10 s smoke run
```

Statistics: paired differences per seed; paired t-test and Wilcoxon p-values;
a verdict is `*_significant` only if p(t) < 0.05 **and** ≥ 80 % of seeds move the
same way. p-values are uncorrected for multiple comparisons (≈ 100 are shown), n = 10.

## 7. Limitations

* One plant (unicycle with first-order actuator lag), one 5-robot wedge, one leader trajectory (plus one maneuver).
* The simulation is not fully decentralised: neighbour coupling and avoidance read global state (see `IMPLEMENTATION_NOTES.md`).
* Quality is a heuristic, not a calibrated probability; with the default channel its nominal value is only ≈ 0.6, so thresholds are tied to that channel.
* The sustained-recovery band is **not** met in most scenarios (0/10 runs in every blackout scenario except `blackout_maneuver`) because the post-blackout error never returns below max(0.5 m, 1.25 × baseline) within the 18 s run; the criterion was not relaxed.
* Statistical significance is reported on tiny effects (≈ 0.01 m RMSE); it should not be read as practical importance.


---

# Second round (`eval_v2`): connectivity, consensus, replay, audit findings

## 8. Three different things (never conflate them)

| concept | question | where measured | typical failure mode |
|---|---|---|---|
| **formation tracking** | how close is each robot to its slot? | `formation_rms` (unchanged) | low error does *not* imply agreement of headings |
| **consensus** | do state variables agree? | `simulation/connectivity.py` heading / speed disagreement | agreement does not imply formation is kept |
| **connectivity** | can information flow? | graph from real `Network` delivery statistics | a connected network does not guarantee good tracking |

### 8.1 Communication graph
Nodes = agents (0 = leader). A directed link *i→j* is **up** if a packet arrived on it
within a timeout. The simulator is a star: pose broadcast L→Fi (every tick), heartbeat/ACK Fi→L
(every 0.5 s). Followers do not exchange packets, so there are no follower–follower links; links are
**never** created from physical proximity.

* **Primary (formation) graph** = leader→follower pose links (downlink timeout `connectivity_downlink_timeout_s` = 1.0 s),
  viewed as an undirected graph (`view="union"`). This is the information the controller consumes.
  `isolated_from_leader` = followers with no path to the leader in it; an **interruption** is a maximal
  interval with ≥ 1 isolated follower. Detection latency equals the timeout, so a 3 s blackout shows as a ≈ 2.0 s interruption
  (start ≈ fault start + 1 s, restoration = first packet after the fault ends).
* **Bidirectional graph** (downlink *and* uplink, uplink timeout 2.0 s = 4 heartbeat periods) is reported as
  `bidirectional_isolated` / `uplink_down` but does not define interruptions (see 10.2 for why).
* **Algebraic connectivity** λ₂ = second-smallest eigenvalue of the Laplacian L = D − A of a symmetric non-negative
  weight matrix; λ₂ > 0 iff connected (eigenvalues below 1e-9 are reported as 0). It is defined only for
  undirected graphs; the code raises `ValueError` for asymmetric input rather than silently symmetrising.
  For the unit-weight star of n agents λ₂ = 1; a disconnected graph has λ₂ = 0; n < 2 returns 0.
* Directed reachability (`reachable_from`) answers "can the leader's data reach follower j?" without undirected assumptions.

### 8.2 Consensus metrics (global diagnostics, units in brackets)
* heading disagreement [rad]: rms of wrap(θᵢ − circular mean) and max pairwise wrapped distance (±π wrap-around handled).
* speed disagreement [m/s]: std and max–min spread of vᵢ.
* edge disagreement: mean |wrap(θᵢ − θⱼ)| and |vᵢ − vⱼ| over communication-graph edges.
* computed over the leader and followers in FOLLOW/REGROUP mode.
* **Heading consensus criterion** (`ConsensusTolerance`): rms heading disagreement ≤ 0.25 rad sustained for 1.0 s,
  timed from the fault end (or t = 0 without a fault). Speed is *not* part of the criterion: robots holding a rigid
  formation through a turn legitimately have different speeds (vᵢ = v_L + ω × offset).
* The tolerance was fixed a priori from a 14° "visually aligned" notion and **not** tuned on results. With
  the default channel/path it is met only part of the time (see tables): the sensor noise makes the headings jitter
  (Sec. 10.3).

### 8.3 Global vs local information
Everything in 8.1–8.2 is computed by the simulator. A real follower only knows its own message age. Nothing here is fed
back into any controller. The supervisor remains purely local (message age + estimated quality).

**Connectivity-aware supervisor — not implemented, by decision.** In a star topology a follower's own message age already
tells it whether *its* link is up; global component structure adds no information a follower could legitimately use, and
using it would assume global knowledge. The planned ablation arm 4 is therefore reported as "not applicable", not as a
result.

## 9. Recordings, replay and rerun

* Format: JSON, `format = "resilientsync-recording"`, `version = 1` (`simulation/recording.py`); no pickle.
  `meta` (run spec incl. seed, controller, fault profile, dt, world, metrics), `frames` (per-tick arrays: states,
  targets, errors, quality, message age, supervisor state, commands, connectivity, consensus, link state, fault flag),
  `events` (supervisor transitions with reasons, fault intervals, connectivity interruptions, closest approach).
* Loading validates version, shapes, finiteness, strictly increasing time and a 40 MB limit; invalid files raise
  `RecordingError` (HTTP 422), never a traceback.
* **Replay** shows the saved frames (nothing is simulated). **Rerun** (`POST /recordings/{id}/rerun`) re-simulates the saved
  run spec and reports the maximum state deviation. The engine is deterministic for a given code version/NumPy build, so
  deviation is normally exactly 0, but this is *not guaranteed* across code versions or platforms — which is why the replay
  never silently re-simulates.
* `GET /recordings/{id}/summary` produces the investigation summary and the four **separate** milestones after the fault window:
  communication restored (every follower's message age ≤ 0.3 s), connectivity restored, heading consensus achieved,
  formation recovered (the unchanged sustained criterion of section 5).

## 10. Audit findings (Stage 1/Feature I) — verified, documented, *not* tuned away

1. **Adaptive discrepancy** (carried over from `HANDOFF.md`): the CSV in `experiments/results/` was produced with the total-speed
   cap, which roughly doubles the RMSE; the cap is now opt-in (`adaptive_comm_total_speed_cap`). Historical outputs untouched.
2. **Per-packet burst process.** The Gilbert–Elliott channel advances once per *packet*, so a 4.5-packet mean burst lasts
   0.2 s on the 20 Hz pose downlink but ≈ 2.3 s on the 2 Hz heartbeat uplink (test:
   `test_sparse_uplink_sees_longer_silences_in_seconds_than_downlink`). A bidirectional graph therefore reports spurious
   multi-second "outages" in *nominal* runs (21 interruptions in 10 seeds × 30 s measured before switching the primary graph to
   the downlink; 2 afterwards, both genuine 1 s pose gaps). Model unchanged.
3. **Sensor-noise chatter.** With σ = 0.025 m the derivative term makes `v_cmd` jump between ≈ 0.06 and 1.25 m/s
   (mean |Δv| ≫ with noise than without; test `test_derivative_term_makes_command_chatter_with_sensor_noise`). The 0.05 s
   actuator lag hides most of it in the trajectory. Consequence: "commands at the speed limit" mixes chatter and
   infeasibility, and `cmd_dv_mean` mostly measures noise.
4. **The default AUTO path is not trackable by the outer wedge slots.** pidr, seeds 42–44, 18 s:
   RMSE 1.49 m (σ = 0.025) / 1.45 m (σ = 0) with 35 % of commands at max_v even without noise, versus RMSE 0.07 m on the gentle
   path. So the nominal error (≈ 1.5 m) is a property of geometry + path + speed limit, not of communication, which is why
   sustained recovery to max(0.5 m, 1.25 × baseline) is rarely reached in the default scenarios.
5. **Seed aliasing.** Channel seed = seed + offset + follower, so seed *s* / follower *k* equals seed *s+1* / follower *k−1*.
   Matched-seed comparisons stay valid (all arms share streams) but adjacent seeds are *not independent samples*, so the
   effective n of the 10 evaluation seeds is smaller than 10 (test `test_known_limitation_adjacent_seeds_...`).
   Fixing it would change every historical result, so it is only documented.

## 11. New scenarios (declared before running)

`nominal_gentle`, `blackout_gentle`: leader path v = 0.8 m/s, ω = 0.1 sin(0.24 t) (`gentle_trajectory`), added as a
feasibility control because of finding 10.4. Nothing about the existing scenarios, recovery criterion, collision threshold or
supervisor parameters was changed after seeing results.

## 12. Reproduce (Windows PowerShell or Git Bash, project root, venv active)

```bash
python -m pytest -q                                              # ~1 min
python -m experiments.run_benchmark --quick --out %TEMP%/rs_quick # ~30 s smoke (Git Bash: --out /tmp/rs_quick)
python -m experiments.run_benchmark --tag eval_v2 --workers 2     # 1000 runs, ~6 min on 2 cores
python -m experiments.run_benchmark --tag mine                    # your own tag; existing tags are protected (use --overwrite)
```

## 13. Measured results, `eval_v2` (10 seeds 42–51, 18 s, 1000 runs, 0 failed)

Mean ± std over seeds; full tables incl. connectivity/consensus in `experiments/results_resilience/eval_v2/report.md`.

**blackout_gentle (feasible path, 3 s blackout)**

| arm | RMSE [m] | peak [m] | min sep [m] | recovered | conn. interruption [s] | heading consensus reached |
|---|---|---|---|---|---|---|
| zoh | 1.264 ± 0.039 | 2.789 | 1.157 | 10/10 | 2.00 | 10/10 |
| pidr | 0.117 ± 0.005 | 0.333 | 1.347 | 10/10 | 2.00 | 10/10 |
| advanced | 0.097 ± 0.005 | 0.297 | 1.365 | 10/10 | 2.00 | 10/10 |
| adaptive_legacy | 0.188 ± 0.005 | 0.567 | 1.344 | 10/10 | 2.00 | 10/10 |
| adaptive_supervisor | 0.143 ± 0.005 | 0.429 | 1.355 | 10/10 | 2.00 | 10/10 |

**nominal_gentle (feasible path, no fault)**

| arm | RMSE [m] | peak [m] | min sep [m] | recovered | conn. interruption [s] | heading consensus reached |
|---|---|---|---|---|---|---|
| zoh | 0.218 ± 0.012 | 0.331 | 1.258 | n/a | 0.00 | 10/10 |
| pidr | 0.070 ± 0.005 | 0.145 | 1.350 | n/a | 0.00 | 10/10 |
| advanced | 0.060 ± 0.005 | 0.133 | 1.369 | n/a | 0.00 | 10/10 |
| adaptive_legacy | 0.060 ± 0.005 | 0.133 | 1.369 | n/a | 0.00 | 10/10 |
| adaptive_supervisor | 0.059 ± 0.006 | 0.133 | 1.367 | n/a | 0.00 | 10/10 |

**blackout_3s (default path — outer slots infeasible)**

| arm | RMSE [m] | peak [m] | min sep [m] | recovered | conn. interruption [s] | heading consensus reached |
|---|---|---|---|---|---|---|
| zoh | 2.669 ± 0.108 | 4.580 | 0.462 | 0/10 | 2.00 | 0/10 |
| pidr | 1.537 ± 0.008 | 2.252 | 1.080 | 0/10 | 2.00 | 0/10 |
| advanced | 1.651 ± 0.014 | 2.492 | 1.100 | 0/10 | 2.00 | 4/10 |
| adaptive_legacy | 1.668 ± 0.012 | 2.528 | 1.143 | 0/10 | 2.00 | 2/10 |
| adaptive_supervisor | 1.657 ± 0.013 | 2.506 | 1.122 | 0/10 | 2.00 | 4/10 |

**blackout_maneuver**

| arm | RMSE [m] | peak [m] | min sep [m] | recovered | conn. interruption [s] | heading consensus reached |
|---|---|---|---|---|---|---|
| zoh | 2.101 ± 0.095 | 4.013 | 0.106 | 10/10 | 2.00 | 5/10 |
| pidr | 1.210 ± 0.007 | 1.979 | 0.320 | 10/10 | 2.00 | 4/10 |
| advanced | 1.261 ± 0.011 | 2.007 | 0.843 | 10/10 | 2.00 | 10/10 |
| adaptive_legacy | 1.259 ± 0.010 | 2.031 | 0.876 | 10/10 | 2.00 | 10/10 |
| adaptive_supervisor | 1.259 ± 0.011 | 2.003 | 0.857 | 10/10 | 2.00 | 10/10 |

**Ablation on `blackout_gentle`** (paired by seed):

| comparison | mean ΔRMSE [m] | seeds improved / worsened | verdict |
|---|---|---|---|
| adaptive_legacy → adaptive_supervisor | -0.0452 | 10 / 0 | better_significant |
| pidr → adaptive_supervisor | +0.0260 | 0 / 10 | worse_significant |
| adaptive_supervisor → sup_no_ff | -0.0460 | 10 / 0 | better_significant |
| sup_observe_only → adaptive_supervisor | +0.0460 | 0 / 10 | worse_significant |

**What the data support**

* The supervisor improves on the earlier adaptive prototype without it (`adaptive_legacy`) in the feasible blackout (RMSE 0.188 → 0.143 m, peak 0.567 → 0.429 m, 10/10 seeds).
* It does **not** beat the plain baselines: `advanced` 0.097 m and `pidr` 0.117 m versus `adaptive_supervisor` 0.143 m. `advanced` has the lowest RMSE in this scenario.
* The loss is caused by the supervisor's feed-forward reduction during DEGRADED/HOLD: `sup_no_ff` (0.097 m) is numerically identical to `advanced` and better than the shipped supervisor on 10/10 seeds. When dead reckoning is accurate (smooth path) discarding feed-forward only hurts. The avoidance boost has no measurable effect (identical to `sup_no_avoid`) because robots are never close enough to trigger it, and the first-design HOLD speed limit (`sup_speedlimit`) is harmful.
* On the default curved path every arm has ≈ 1.5 m error with or without faults (finding 10.4); differences between arms are ≤ 0.1 m except `zoh` and the capped prototype, and the sustained-recovery criterion is met in 0/10 runs for all arms except in `blackout_maneuver` and the gentle scenarios (10/10, every arm).
* Connectivity: a 3 s blackout appears as a 2.0 s interruption in every arm (detection timeout 1 s); random loss and latency never disconnect the graph; burst loss gives 0.76 s mean interruption. These depend only on the channel realisation, not on the controller (identical across arms by construction).
* Heading consensus is *not* implied by formation tracking: on the default path 8–9/10 nominal runs reach the 0.25 rad criterion although the formation error is ≈ 1.5 m; during/after a blackout `zoh` and the capped prototype rarely do.
* **No winner is declared**: results depend on the scenario, adjacent seeds are correlated (finding 10.5), and the p-values are uncorrected (350 comparisons).
* The planned arm 4 (connectivity-aware supervisor) was not implemented (Sec. 8.3), so it has no result.

### 13.x Caveat on the recovery criterion

Formation recovery is judged against each run's *own* baseline (threshold = max(0.5 m, 1.25 x baseline RMSE)). In runs whose baseline is already large (e.g. `blackout_maneuver`), the threshold is loose, so a 10/10 recovery rate there partly reflects that looseness and is not evidence of good tracking.
