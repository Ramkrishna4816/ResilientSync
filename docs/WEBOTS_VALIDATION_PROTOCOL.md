# Webots validation protocol

Status legend: **[known]** read from code/config; **[user-reported]** stated by the project owner, not verified by me; **[TO FILL]** must be recorded from the first real Webots run (`meta.json`, console). Nothing here was observed by me in Webots.

## 1. Versions
| Item | Value |
|---|---|
| Webots | R2025a installed on Windows at `C:\Users\harih\AppData\Local\Programs\Webots\` **[user-reported]**; title bar of the user's screenshot reads "Webots R2025a" **[observed in screenshot]**; exact build string **[TO FILL]** from `meta.json: webots_version` |
| World / PROTO header | `#VRML_SIM R2023b utf8` **[known]**. User reports the world opens in R2025a **[user-reported]**. Whether Webots applied an automatic upgrade is **[TO FILL]**: check the Webots console on load for "upgrad" messages; if present, copy the upgraded header into `make_worlds.py` and the PROTO. |
| Python used by the Webots controllers | **[TO FILL]** (`[rs_coordinator] python X.Y.Z` is printed at start; `python scripts/check_webots_env.py --write-runtime-ini` pins it) |
| numpy / scipy | **[TO FILL]** (`check_webots_env.py`) |
| Authoring/analysis sandbox (stand-in runs only) | Python 3.12.3, numpy 2.4.4, scipy 1.17.1, Linux; no Webots |

## 2. Robot model and physical assumptions [known]
Custom `RSDiffDrive.proto`: axle-midpoint reference, wheel radius 0.0975 m, wheel-centre separation (track) 0.33 m, two `RotationalMotor`s in velocity mode (`setPosition(inf)`), motor `maxVelocity` 20 rad/s (= 1.95 m/s), body 0.40 × 0.26 × 0.10 m, mass 8 kg + 2 × 0.6 kg wheels, `centerOfMass 0 0 0`. Two frictionless caster spheres are part of the robot's top-level `boundingObject` (see section 11). Motor torque/acceleration limits are Webots defaults (not tuned). Wheel slip, contact friction (default 1.0, wheel–floor) and inertia are Webots' own.
Constants live in `resilientsync_webots/robot_params.py`; `tests/test_webots_assets.py` checks the PROTO against them.

## 3. Time
`basicTimeStep` 10 ms; control period 50 ms = engine `DT` (0.05 s, 20 Hz) [known]. Sequence per tick: read all poses → engine step (controllers, supervisor, network, faults) → send wheel speeds over the actuation channel → `step(50 ms)`. The actuation Emitter/Receiver is simulation plumbing (≤ 1 basic step latency), **not** the radio link under test and **never faulted**. Engine time and Webots time are compared every tick (`t_plant − t`); `max_time_skew_s` is stored in `meta.json`; a constant start offset (placement settling) is allowed, drift is not.

## 4. Initial poses, formation, trajectories
Initial poses = the engine's seeded initial conditions (nominal wedge slots plus seeded noise); the coordinator teleports the robots there (`teleport_initial`), then settles one control period with zero commands. Formation: 5-agent WEDGE [known: `simulation/formation.py`], 3-agent variant for smoke tests. Leader trajectories: `default`, `gentle`, `maneuver` (open-loop, `experiments/run_benchmark.py`). Gentle paths are used for primary results because the default path is infeasible for outer slots (HANDOFF finding 4).

## 5. Coordinate mapping
Webots world is ENU (`coordinateSystem "ENU"`): x East, y North, z Up. RS frame = ENU; identity map (`FrameMap`, offset/rotation supported and tested). Heading `= atan2(R[3], R[0])` of `getOrientation()`; `v` = world linear velocity projected on heading; `omega` = `wz`. Reference point = axle midpoint at z = 0.0975 m.

## 6. What the controller sees vs. ground truth
| Quantity | Source | Note |
|---|---|---|
| Leader pose/velocity at followers | **only** the faulted network (dead reckoning from the last delivered packet) | realistic |
| Own pose/velocity | Webots ground truth + engine Gaussian noise (`sensor_sigma` 0.025) | **idealised** (no odometry/GPS model) |
| Neighbour poses (coupling, avoidance, yield-speed) | Webots ground truth, **global** | **idealised: not decentralised** (engine limitation) |
| Evaluation (`formation_rms`, `min_sep`, `true_slot_err_*`) | Webots ground truth | evaluation only |
The 5-agent engine runs in ONE coordinator process; a follower "node" is a data structure, not a separate process.

## 7. Communication and fault injection
The engine's `Network` (unchanged) sits between the leader's broadcast and each follower's receive path; faults (`blackout`, `random_loss`, `burst_loss`, `latency`) are configured in `webots_project/config/scenarios.json` (cross-checked against `experiments/run_benchmark.SCENARIOS` by tests). Logged per run: `comm_events.csv` (every message sent: seq, status OK/DELAYED/LOST, latency), `deliveries.csv` (every POSE_UPDATE actually delivered: seq, message age, accepted/rejected-as-stale), `faults.json` (profile + edges), per-tick `age_i`, `quality_i`, `loss_est_i`, `rx_seq_i`, `sent_i`, `lost_i`, `blackout_active`.

## 8. Seeds, duration, reproducibility
Duration 18 s (default). Seeds: **100–104 debug/tuning (project tuning seeds are 100–109)**; **42–51 held-out evaluation**; no parameter is changed between them. Matched initial conditions and fault schedules across controllers come from the shared seed. Webots physics is deterministic only when the same Webots build, step and CPU float behaviour are used; **repeatability across runs in Webots is [TO FILL]** (run the same seed twice and compare `steps.csv`).

## 9. Metrics (identical formulas to the Python simulator; computed from logged Webots ground truth)
* `formation_rms(t)` = RMS over followers of distance to the *true* slot (`formation_errors`).
* **RMSE** = sqrt(mean over ticks of `formation_rms²`); **Peak** = max `formation_rms`.
* **MinSep** = min over ticks and pairs of centre-to-centre distance; **collision** = MinSep < 0.38 m (Python-sim criterion; the Webots body is 0.40 × 0.26 m, so this is a proxy — also inspect contacts if MinSep < 0.5 m).
* **Message age** (follower i) = `t − rx_time` of the last accepted packet. **Pose loss %** = lost / sent POSE_UPDATE messages.
* **Recovery** (`simulation.metrics.compute_recovery_metrics`, defaults): baseline = mean error in the 1.0 s before the fault; threshold = max(0.5 m, 1.25 × baseline); recovered if the error stays below the threshold for ≥ 0.5 s after the fault ends; `recovery_time` = time from fault end to the start of that interval. Applies only to finite faults starting ≥ 1 s and ending ≥ 0.5 s before the run end.
* **Known weakness:** when the fault never pushes the error above the threshold (gentle blackout peak ≈ 0.5 m) the criterion is nearly trivial; `time_to_all_normal` (first tick after the fault ends when all followers are NORMAL) is reported as a separate, supervisor-specific number and is **not** a recovery criterion.
* Recovery is judged from formation error and separation, **not** from the supervisor state.
* Actuators: wheel-saturation samples (`sat_i`), tilt (`roll_i`, `pitch_i`) and height (`gt_z_i`) per tick.

## 10. Staged plan and acceptance gates
| Stage | Run | Gate (checked by `scripts/diagnose_webots_run.py`) |
|---|---|---|
| A smoke | 3 robots, `nominal`, 4 s | run completes; all robots move; no `coordinator_error.txt`; no NaN |
| B nominal | `nominal_gentle`, 5 robots | leader tracks native reference (≤ 0.5 m); clock drift < 5 ms; no teleport/frozen/tilt; formation error reported |
| C blackout | `blackout_gentle` | 0 accepted deliveries in the blackout; deliveries resume; states reached recorded; recovery judged from error |
| D loss | `random_loss_30`, `burst_loss`, `latency_jitter` | as C |
| E comparison | 4 arms, same seed | all complete |
| F repeated | 100–104, then 42–51 | failures reported, not dropped; no significance claims without a paired test |

## 11. Rear-caster warning investigation
Reported: `DEF RS_4 RSDiffDrive > Solid "rear_caster": As 'physics' is set to NULL, collisions will have no effect.`
**Cause (from the PROTO and the warning text):** the casters were child `Solid`s with a `boundingObject` but no `physics`. Webots uses only the top-level `boundingObject` of a physics body, so those spheres did **not** take part in contact detection. The warning was therefore **not harmless**: the robot would have been supported only by its two wheels, with the body box (0.0675 m above the floor) as the next contact when it pitched, i.e. likely nose-/tail-down tilt and dragging. Adding mass/physics to them would instead create separate free bodies, which is wrong for a fixed caster.
**Fix (applied):** casters are visual `Transform`s; the two spheres are children of the robot's `boundingObject Group`; the robot carries `contactMaterial "rs_caster"` (friction 0 against `default`, set in `WorldInfo.contactProperties`); the sphere lowest point equals −wheel radius relative to the axle (unit-tested). The wheels remain separate physics Solids (default material, friction 1).
**Verification still needed in Webots:** (1) the warning is gone from the console; (2) `diagnose_webots_run.py` shows tilt < 3° and |z − 0.0975| < 10 mm at rest and in motion. The earlier (pre-fix) logs had no tilt columns, so the pre-fix tilt was **not measured**; the diagnosis above is an inference from the warning, not an observation.

## 12. Known limitations
Ground-truth own/neighbour sensing; one process for all agents; actuation channel unfaulted; custom (not manufacturer) robot; unverified command chatter at wheel level (stand-in: mean |Δv| ≈ 0.58 m/s per tick); Webots-vs-Python-simulator comparison not yet made; stand-in results (332 runs) are **not** Webots results.

## 13. First real Webots evidence (user screenshot, stage-5 release, `resilientsync_3robots.wbt`)
| Observation (from the screenshot console/scene tree) | Conclusion |
|---|---|
| World loads in R2025a; scene tree shows WorldInfo, Viewpoint, floor, SLOT_1/2, RS_0..RS_2 (RSDiffDrive), `rs_coordinator` | the R2023b-header world and PROTO load in R2025a (no load error visible; the upper console lines were scrolled out, so a caster warning or upgrade notice there is **not ruled out**) |
| `rs_wheel_driver: Starting controller: python.exe -u rs_wheel_driver.py 1 3` and `... 2 3` | wheel drivers start with the intended arguments (robot index, count) |
| `rs_coordinator: Starting controller: ...\ResilientSync\.venv\Scripts\python.exe -u rs_coordinator.py` | `runtime.ini` is honoured; the coordinator uses the venv interpreter |
| `ModuleNotFoundError: No module named 'numpy'` at `rs_coordinator.py` line 23; `controller exited with status: 1` | **the venv Webots uses has no numpy.** The preceding `from controller import Supervisor` succeeded. The coordinator exited before sending any command: no robot moved, no log was written, simulated time (0:00:58) ran with idle robots |
| Scene: flat grey floor, red selection handle at the origin, robots not discernible | the camera frames the whole 26 x 16 m arena, so 0.4 m robots are ~20 px and sit under the coordinator's selection handle at the origin; this is framing, not necessarily a missing robot |
Cause of the missing numpy is **not established** (no pip output available). Working hypothesis: `pip install -r requirements.txt` aborted because one dashboard package failed to install, leaving the venv empty. `requirements-webots.txt` now isolates numpy/scipy from that stack.
No complete Webots experiment exists yet.

## 14. First complete Webots run (user-supplied console output, stage-6 release)
Run: `nominal`, `adaptive_supervisor`, seed 100, 3 robots, 6 s, `webots.exe --mode=realtime --batch`, Python 3.11.9 venv, Webots R2025a (title bar). Source: the diagnosis printed by `scripts/diagnose_webots_run.py` in the user's terminal. The CSV files themselves were **not** available to me; the numbers below are those the user pasted. Single run: no statistics, no equivalence claim.

| Check | Result (Webots) |
|---|---|
| run status / ticks | completed; 120 of 120 ticks |
| engine tick / clock sync | 0.0500 s; plant-vs-engine clock offset 0.000 s, drift 0.0 ms (max skew 1.3e-14 s) |
| finite values | all finite |
| motion | leader 4.70 m, follower 1 4.29 m, follower 2 6.07 m net displacement |
| teleports | largest one-tick jump 0.063 m (physical max ~0.062 m): none |
| leader speed / commanded | 0.999 |
| command-to-motion correlation (2 ticks later) | follower 1 0.33, follower 2 0.56 |
| wheel saturation | 0 samples |
| tilt / height (caster fix) | max 0.8 deg; max z deviation 0.8 mm: no tipping or sinking seen in this run |
| leader vs native-simulator reference path | max 0.34 m (final 0.34 m) after 6 s |
| formation error | RMSE 0.150 m, peak 0.289 m, last 2 s 0.214 m; min separation 1.50 m |
| supervisor | NORMAL only, 0 transitions (nominal run, no fault; expected) |
| command chatter (WARN) | mean abs dv 0.44 m/s, dw 1.59 rad/s per tick (stand-in: 0.58 / 1.85) |

Matched native Python simulator (same seed, scenario, 3 robots, 6 s, computed by me): RMSE 0.151 m, peak 0.329 m, last 2 s 0.228 m, min separation 1.49 m.
**Interpretation (cautious):** the pipeline works end to end in Webots (placement, clock lock, wheel actuation, measured-pose logging, clean exit); the robots stand level, so the caster fix is not contradicted; formation error is close to the native simulator for this one run. **Not established:** blackout behaviour in Webots, the 5-robot world, repeatability, other controllers, the chatter's physical effect (it is present but follower motion still tracks), and the leader's 0.34 m drift growth over an 18 s run (open-loop leader; expect it to grow).
`meta.json` showed `Webots unknown` because no API call returns the version; the launcher now records `webots --version` (`RS_WEBOTS_VERSION`).
