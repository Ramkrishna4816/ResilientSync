# Implementation plan (round 2) — audit, ranking and status

## 1. Verified baseline (this session, Linux sandbox, Python 3.13, numpy 2.5.3)

* Uploaded ZIP: `python -m pytest -q` → **95 passed, 1 warning** (Starlette `BlockingPortal` deprecation).
* Already present and working: resilience supervisor, fault profiles (blackout, random/burst loss, latency+jitter), benchmark
  (800 runs), dashboard resilience panel. **Missing:** connectivity graph / consensus metrics, replay, experiment controls,
  accurate arena layers, synchronised plots, reproducible config save/load, overwrite protection of results.
* Adaptive discrepancy: unchanged from round 1 (stale CSV produced with the removed total-speed cap) — see HANDOFF.md.

## 2. Ranked work items

| # | item | technical value | depends on | risk | effort | status |
|---|---|---|---|---|---|---|
| 1 | connectivity graph + λ₂ + consensus metrics (pure functions + tracker) | high | – | low (diagnostic only) | S | **done**, 28 tests |
| 2 | integrate diagnostics into engine history/state without altering dynamics | high | 1 | low (pinned RMSE test still passes) | S | **done** |
| 3 | recordings (versioned JSON, validation, replay, rerun compare, summary, milestones) | high | 2 | medium (format) | M | **done**, 44 tests |
| 4 | API: connectivity, experiments, recordings, validation, run lock | high | 3 | low | S | **done**, 17 tests |
| 5 | benchmark: connectivity/consensus metrics, gentle scenarios, overwrite guard, report/plots | high | 1 | low | M | **done**, 7 tests, 1000-run eval_v2 |
| 6 | viewport + synchronised plots + replay UI + experiment controls | high | 3,4 | medium (visual) | L | **done**, browser-checked, 3 smoke tests |
| 7 | model audit (Feature I): documented findings, regression tests for properties | high | 5 | low | S | **done** (5 findings; none "fixed" by changing the model) |
| 8 | docs: protocol, README, handoff | high | all | low | M | **done** |
| 9 | connectivity-aware supervisor (control) | low | 1 | high (needs global knowledge) | M | **not implemented — by decision** (EXPERIMENT_PROTOCOL §8.3) |
| 10 | peer-to-peer follower links, directed consensus protocol | medium | – | high (changes the model) | L | not done |
| 11 | retune supervisor feed-forward on tuning seeds 100–109 and re-evaluate on 42–51 | medium | 5 | medium | S | **not done** (suggested next step; see HANDOFF) |

## 3. Architecture (data flow)

```
Network (faults, delivery stats)  ->  Agent rx state -> _link_quality -> ResilienceSupervisor -> FollowerController -> RK4 plant
        |                                                                                                   |
        +--> connectivity.evaluate_topology (DIAGNOSTIC, global)  <-- states, headings, speeds <-------------+
                         |
                  history / get_state / recording.json  ->  Replay / REST  ->  browser (scene -> viewport + plots)
```
