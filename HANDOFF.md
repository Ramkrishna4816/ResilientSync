# HANDOFF (round 2)

Round-1 handoff (supervisor, fault injection, first benchmark, adaptive-discrepancy investigation) is preserved verbatim at the end of this file.

## 1. Status

All commands below were run **in the author's Linux sandbox** (Python 3.13, numpy 2.5.3, fastapi 0.146, Chromium via Playwright).
**Nothing was run on your Windows machine.**

| area | status | evidence |
|---|---|---|
| connectivity graph, λ₂, consensus metrics, tracker (`simulation/connectivity.py`) | implemented, tested | 28 tests |
| diagnostics integrated in engine (history, `get_state()["connectivity"]`) without changing dynamics | implemented | pinned RMSE test unchanged |
| recordings / replay / rerun compare / investigation summary / recovery milestones (`simulation/recording.py`) | implemented, tested | 44 tests |
| API: `/connectivity`, `/experiments/config|run`, `/recordings*`, upload, rerun, run lock | implemented, tested | 17 tests |
| benchmark: connectivity/consensus metrics, `*_gentle` scenarios, overwrite guard, report + plots | implemented, run | 7 tests; `eval_v2` = 1000 runs, 0 failed |
| dashboard: arena layers, synchronised plots, replay, experiment controls, tabs | implemented, **checked visually only in headless Chromium (Linux)** | 3 smoke tests + screenshots |
| docs: `docs/EXPERIMENT_PROTOCOL.md` (sections 8–13), `docs/IMPLEMENTATION_PLAN.md`, `Readme.md` | updated | – |
| connectivity-aware supervisor (control) | **not implemented, by decision** | protocol §8.3 |
| peer-to-peer follower links / directed consensus protocol | not implemented | model has a star topology |

**Tests:** `python -m pytest -q` → **194 passed, 1 warning** (Starlette `anyio.abc.BlockingPortal` deprecation, harmless). The 3 UI smoke tests need
Playwright+Chromium and are *skipped* without them (so a machine without them reports 191 passed, 3 skipped).
Baseline at the start of this round: 95 passed.

## 2. Files changed / added (round 2)

New: `simulation/connectivity.py`, `simulation/recording.py`, `tests/test_connectivity.py`, `tests/test_recording.py`, `tests/test_web_replay.py`,
`tests/test_benchmark.py`, `tests/test_ui_smoke.py`, `web/static/js/{core,viewport,plots}.js`, `recordings/example_adaptive_blackout_s42.json`,
`experiments/results_resilience/eval_v2/*`.
Modified: `simulation/config.py` (`connectivity_downlink_timeout_s`, `connectivity_uplink_timeout_s`), `simulation/network.py` (`link_is_up`, `up_links`),
`simulation/simulation.py` (`_diagnostics`, `connectivity_summary`, history fields, `collision_distance` in state), `experiments/run_benchmark.py`,
`web/app.py`, `web/templates/index.html`, `web/static/app.js`, `web/static/style.css`, `Readme.md`, `docs/*`, `requirements.txt`, `.gitignore`.
Untouched: `experiments/results/`, `experiments/results_resilience/eval/` (first-round results; protected by a test), the paper, the notebook, all controllers.
Not shipped: `install.cmd` (it is Claude Code's own bootstrap installer, unrelated to this project).

## 3. Decisions and why

* **Diagnostics never touch controllers.** Followers cannot know the global graph; the supervisor stays local (message age/quality).
* **Primary connectivity graph = leader→follower downlink**, per-direction timeouts (1.0 s / 2.0 s). A bidirectional graph gave spurious multi-second nominal "outages" because the Gilbert–Elliott chain advances per packet and the uplink is 10× sparser (finding 2).
* **No model/controller/threshold changes.** Five audit findings are documented and pinned by tests instead (protocol §10).
* **`*_gentle` scenarios** were declared before the results; they exist because the default path is infeasible for the outer slots (finding 4).
* Replay shows saved frames; "rerun" is a separate, explicit action (protocol §9).

## 4. Key measured results (`eval_v2`, seeds 42–51; details protocol §13)

| scenario | pidr | advanced | adaptive_legacy | adaptive_supervisor |
|---|---|---|---|---|
| blackout_gentle RMSE [m] | 0.117 | **0.097** | 0.188 | 0.143 |
| blackout_3s RMSE [m] (default path) | **1.537** | 1.651 | 1.668 | 1.657 |

* Supervisor vs `adaptive_legacy` on `blackout_gentle`: −0.045 m RMSE, 10/10 seeds. Supervisor vs `advanced`/`pidr`: worse. Cause: feed-forward scaling (`sup_no_ff` = `advanced`).
* Sustained formation recovery: 0/10 on all default-path scenarios except `blackout_maneuver`; 10/10 on the gentle blackout (criterion is relative to each run's baseline, so the maneuver result is partly a loose threshold).
* Connectivity: a 3 s blackout = 2.0 s interruption (1 s detection timeout). Heading consensus is independent of formation error.

## 5. Known limitations / unresolved

1. Adjacent seeds share shifted channel RNG streams (seed aliasing), so the 10 evaluation seeds are not independent. Not fixed (would change all historical numbers).
2. Sensor-noise chatter in `v_cmd` (derivative term); command-smoothness metrics mostly measure it.
3. The 0.25 rad / 1 s heading-consensus tolerance is a declared convention, not derived.
4. UI verified only in headless Chromium on Linux; not on Windows browsers. No dashboard screenshot is committed to the repo.
5. Neighbour coupling and avoidance still read global state (round-1 limitation).
6. Round-1 unexplained difference (1.638 m earlier vs 1.675 m now for the no-cap adaptive code) remains unexplained.
7. p-values are uncorrected for 350 comparisons.

## 6. Exact next steps

1. On Windows: `python -m venv .venv`, activate, `python -m pip install -r requirements.txt`, `python -m pytest -q` (expect 191 passed + 3 skipped without Playwright), `python -m web.app`, open http://127.0.0.1:8000, press **Run & record**.
2. Look at the dashboard on your machine and report layout problems (only Linux/Chromium was seen).
3. Optional science: retune only the supervisor's feed-forward behaviour on tuning seeds 100–109 (never on 42–51), then re-evaluate on 42–51 into a *new* tag.
4. Optional: fix seed aliasing behind an opt-in flag (`SeedSequence`) and report how the numbers change.

## 7. Commands executed this round

`python -m pytest -q` (many times; last: 194 passed), `python -m experiments.run_benchmark --quick --out /tmp/bq --workers 2`,
`python -m experiments.run_benchmark --tag eval_v2 --workers 2` (run twice: once before relabelling the saturation metric, then `--overwrite`; the shipped files are from the second run),
ad-hoc audit scripts (seed streams, saturation vs sensor noise, nominal false-interruption counts), headless-Chromium UI checks with screenshots.

## 8. Resume without repeating work

Everything above is committed in the tree; start from section 6. Do not re-run the audits (documented), do not overwrite `eval`/`eval_v2` without `--overwrite`.

---

# Round-1 HANDOFF (preserved)


## 1. Status
All planned stages (1–7) are implemented and tested **in my sandbox** (Linux, Python 3.13.16,
numpy 2.5.3, pandas 3.0.5, fastapi 0.146). I have not run anything on your machine.
Not implemented: the optional failure-replay tool. No known failing tests.

Actual results (sandbox): `python -m pytest -q` → **95 passed, 1 warning** (the Starlette
`anyio.abc.BlockingPortal` deprecation, as before). `python -m compileall -q simulation web experiments tests visualization` clean.
Benchmark: `python -m experiments.run_benchmark --tag eval --workers 2` → 800 runs, 0 failed/halted (~3 min on 2 cores).

## 2. Discrepancy investigation (Stage 1) — result
* The uploaded `simulation/controller.py` **no longer contains the total-speed cap** (`vcmd` was clipped to `[-0.25, max_v]`), and the active path is `run_comparison → MultiAgentSimulation(control_mode="adaptive_comm")` → `FollowerController.formation_command`; no other module overrides it.
* On the uploaded code `pytest` gave **11 passed, 1 failed**: `test_adaptive_comm_caps_total_speed_when_communication_is_stale` expects the cap (your "12 passed" must have been measured with the cap still present).
* `experiments/results/controller_comparison.csv` is **stale**: re-running adaptive_comm on the uploaded code gives mean RMSE 1.675 m (seeds 42–44), not 2.289 m. Re-inserting `clip(..., -0.25, max_v*speed_scale)` in a scratch copy reproduced the CSV (2.3212/2.2064/2.3372 vs CSV 2.3221/2.2064/2.3372) and made the test pass. So the numbers did not change because the CSV was produced/kept from the capped code; the cap itself is what doubled the RMSE.
* zoh/pidr/advanced numbers in the CSV reproduce exactly on the uploaded code.
* Not explained: your earlier 1.638 m figure vs today's 1.675 m for the no-cap code (some other small difference between that version and this one; I had no copy of it).
* Decision: keep the cap **removed by default**; kept it as opt-in `Config.adaptive_comm_total_speed_cap`, and changed the old test to enable that flag (it still asserts the cap) + added a test that the default has no cap. I did not delete any test. Original `experiments/results/*` untouched.

## 3. What was added
| file | change |
|---|---|
| `simulation/supervisor.py` (new) | state machine, config, transitions, reasons |
| `simulation/config.py` | `supervisor_enabled` (default True), `supervisor`, `supervisor_min_loss_window`, `adaptive_comm_total_speed_cap` |
| `simulation/controller.py` | `formation_command(..., supervisor=None)`; duplicated feed-forward block removed (behaviour identical) |
| `simulation/network.py` | `FaultEvent`, `FaultProfile`, `make_fault_profile`, fault hooks in `Network`, per-link forced-loss kept |
| `simulation/simulation.py` | per-follower supervisors, `_link_quality`, `fault_profile`/`supervisor_cfg` args, history fields (`supervisor_state`, `caution`, `v_cmd`, `w_cmd`), rolling `trace`, `resilience_summary`, `set_fault_profile_relative` |
| `experiments/run_benchmark.py` (new) | benchmark + ablation + report + plots |
| `experiments/results_resilience/{eval,tuning_*}` (new) | measured outputs |
| `web/app.py`, `web/templates/index.html`, `web/static/{app.js,style.css}` | `/resilience`, `/faults`, `/faults/clear`, `/benchmark`, reset options, resilience panel |
| `tests/test_supervisor.py`, `test_supervisor_integration.py`, `test_faults.py`, `test_web_resilience.py` (new); `test_adaptive_comm.py` (cap test now opt-in + 1 new test) | 95 tests total |
| `docs/*`, `Readme.md` (appended section), `HANDOFF.md` | documentation |

## 4. Decisions
* Supervisor flag default **True** for `adaptive_comm`; `supervisor_enabled=False` reproduces the pre-supervisor controller bit-for-bit (pinned in a test: RMSE 1.6854586513790624, seed 42).
* `CONTROL_MODES` unchanged (an existing test pins it); the supervisor is a config flag, not a new mode.
* HOLD uses age only (the loss-window in the quality estimate stays pessimistic ~1 s after a link returns).
* Thresholds calibrated on the nominal channel (quality median 0.61). Under nominal conditions the supervisor is DEGRADED ≈ 11 % of the time and never in HOLD (10 seeds × 30 s).
* First design (HOLD speed limit 0.8×) was measurably harmful on the tuning seeds → default 1.0 (no limit); avoidance boost has no measurable effect (avoidance vector ≈ 0 when robots are far apart).

## 5. Key measured results (eval seeds 42–51; full tables in `experiments/results_resilience/eval/report.md`)
Matched scenario, seeds 42–44, blackout 3 s (before/after, same seeds & fault):
| arm | RMSE | peak | min sep |
|---|---|---|---|
| zoh | 2.688 | 4.634 | 0.460 |
| pidr | 1.541 | 2.261 | 1.092 |
| advanced | 1.657 | 2.502 | 1.111 |
| adaptive_capped (old prototype; matches your CSV) | 2.288 | 4.059 | 0.702 |
| adaptive_legacy (cap removed) | 1.675 | 2.543 | 1.157 |
| adaptive_supervisor (new) | 1.664 | 2.520 | 1.134 |
PIDR has the lowest RMSE in all 8 scenarios. The supervisor vs its neutral control gains 0.02–0.05 m separation (significant, consistent) but is not better in RMSE; effects are tiny. Recovery criterion met 0/10 in most scenarios (10/10 only in `blackout_maneuver`).

## 6. Resume / next steps
1. `pip install -r requirements.txt pytest` (add `websockets` for the live WebSocket in uvicorn; the UI polls without it).
2. `python -m pytest -q` (expect 95 passed), then `python -m experiments.run_benchmark --quick`.
3. Run the app: `python -m web.app` → http://127.0.0.1:8000, choose *adaptive communication-aware*, Reset, schedule a blackout in the Resilience panel.
4. Ideas not done: replay tool; a supervisor that reacts to leader-maneuver uncertainty rather than link age; per-link decentralised neighbour terms; re-calibrate thresholds if channel parameters change; run the original `experiments/run_comparison` on your machine and keep its outputs separately (it overwrites `experiments/results/` — copy it first).

## 7. Commands I executed
`unzip` (via Python, archive uses backslash paths), `pytest` (several times), ad-hoc audit/sweep scripts (scratchpad), `python -m experiments.run_benchmark --quick`, tuning run (`--seeds 100..104`), full eval run, headless Chromium screenshot of the dashboard.


---
# Addendum: Webots 3D validation (stage 4)
* Engine hook (only change to `simulation/`): `simulation.py` gains `external_plant`, `cmd_out`, `set_measured_states()`, `_advance_plant()`; default path unchanged (engine tests identical before/after).
* New: `resilientsync_webots/` (adapter, frames, diffdrive, faults, runlog, runner, standin, analysis), `webots_project/` (PROTO, worlds, 2 controllers, scenario JSON), `scripts/*webots*|*standin*|analyze_runs.py`, `tests/test_webots_*.py` (59 tests, run with a pytest stand-in), `docs/WEBOTS_VALIDATION.md`.
* **Webots never executed.** First job on a machine with Webots: follow `webots_project/README.md` stage A, then fix whatever the console reports (PROTO/world syntax, API calls). Open risks: command chatter (~0.6 m/s per tick), physics stability of the custom PROTO, one-period placement settle.


---
# Addendum: after first load in Webots R2025a (stage 5)
* User report: world opens, controllers start, caster warning `Solid "rear_caster": ... physics NULL ... collisions will have no effect`. No logs or console output were available to me.
* Fixed (inferred from the warning + code, **not** observed in Webots): casters were child Solids without physics -> not in contact detection. Now part of the robot's top-level `boundingObject Group` (`protos/RSDiffDrive.proto`; see protocol section 11).
* Fixed: relative `out_dir` was resolved against Webots' cwd (controller folder) -> `resilientsync_webots/runconfig.py` resolves against the project root.
* Added: `scripts/check_webots_env.py`, `scripts/diagnose_webots_run.py` (+ automatic diagnosis in `run_webots_trials.py`), tilt/height columns, `docs/WEBOTS_VALIDATION_PROTOCOL.md`, 14 new tests.
* Deliberately NOT done yet (per the execution order): 3D visual polish (labels, trails, slot/communication overlays), dashboard integration, dashboard-fix verification, packet-loss/comparison/repeated Webots runs.


---
# Addendum: first real Webots console (stage 6)
* Real evidence (user screenshot): world loads in R2025a, wheel drivers start, runtime.ini selects the venv python, **coordinator crashed: numpy missing in that venv** -> no motion, no logs. See `docs/WEBOTS_VALIDATION_PROTOCOL.md` section 13.
* Fixed tooling weaknesses it exposed: `check_webots_env.py` no longer writes `runtime.ini` unless a Webots-style launch test (clean env, cwd = controller folder) passes (`resilientsync_webots/envcheck.py`); coordinator import/config errors now print an actionable message and write `results/webots/_startup_error.txt`; `n_agents: "auto"` takes the robot count from the loaded world (3-robot world + 5-robot config used to fail); new `requirements-webots.txt` (no dashboard stack).
* New tests: `tests/test_webots_envcheck.py`, `tests/test_webots_coordinator_mock.py` (real controllers vs a FAKE Webots `controller` module written by me - not Webots).
* Still no complete Webots run.


---
# Addendum: first complete Webots run + website replay (stage 7)
* **Real result (user console):** nominal, seed 100, 3 robots, 6 s completed in Webots R2025a: clock locked, all robots moved, tilt 0.8 deg, formation RMSE 0.150 m vs native 0.151 m (single run). See `docs/WEBOTS_VALIDATION_PROTOCOL.md` section 14. 5-robot world, blackout and loss scenarios still not run in Webots.
* New: every run writes `recording.json` (engine history on MEASURED poses) and the launcher copies it to `recordings/webots__*.json` for the dashboard's Replay tab; `scripts/export_recording.py` does this for old runs and checks the engine reproduces the logged commands. `--keep-open` flag; Webots version capture; the world camera now follows the leader (unverified in Webots).
* Dashboard: replays finished Webots runs only; no live Webots stream. The dashboard HTTP path (upload/listing) was not run here (no fastapi in the authoring sandbox).
