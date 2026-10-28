# Multi-Agent Digital Twin

An interactive, software-only digital twin of a **leader–follower swarm of
differential-drive robots** that talk over a **lossy wireless link** (an
ESP-NOW stand-in). One leader and four followers (configurable) hold a
formation, react to operator commands, share work through task allocation, and
keep working when radio packets are lost.

It is built as a reusable **simulation engine** with three front ends on top:

| Front end | Purpose |
|---|---|
| **Python / Jupyter API** | Research mode: batch runs, ZOH vs PIDR vs Advanced comparison, Monte-Carlo, stability analysis |
| **Matplotlib window** | Local interactive view with keyboard, mouse and buttons |
| **Web dashboard (FastAPI + HTML)** | Browser control panel with live map, commands, tasks and communication log |

Pure Python. No Webots, ROS 2 or hardware is required (the architecture is
ready for them, see [Roadmap](#roadmap)).

---

## Contents

1. [Features](#features)
2. [Install](#install)
3. [Quick start](#quick-start)
4. [The web dashboard](#the-web-dashboard)
5. [The Matplotlib window](#the-matplotlib-window)
6. [Commands reference](#commands-reference)
7. [Keyboard control](#keyboard-control)
8. [Modes and mission states](#modes-and-mission-states)
9. [How it works](#how-it-works)
10. [Project structure](#project-structure)
11. [Python API](#python-api)
12. [REST / WebSocket API](#rest--websocket-api)
13. [Configuration](#configuration)
14. [Logging and metrics](#logging-and-metrics)
15. [Research mode (notebook compatibility)](#research-mode-notebook-compatibility)
16. [Troubleshooting](#troubleshooting)
17. [Known limitations](#known-limitations)
18. [Roadmap](#roadmap)

---

## Features

**Swarm behaviour**
- Leader plus N followers (default 5 agents) with a wedge formation. LINE and COLUMN presets are also built in.
- Followers track their formation slot using a dead-reckoned estimate of the leader, a cascaded PID controller with adaptive gains, neighbour coupling and collision avoidance.
- `GOTO`, `MOVE`, `SCATTER`, `REGROUP`, `FOLLOW`, `STOP`, `RESUME`, `FORMATION`, `STATUS`.
- Task allocation: create tasks, allocate them to the nearest free follower by priority, watch them complete, and the swarm regroups automatically afterwards.
- Single-agent commands, for example `AGENT 2 GOTO 10 5` or `AGENT 3 STOP`.

**Communication layer (real, not cosmetic)**
- Every leader→follower and follower→leader message passes through a Gilbert–Elliott burst-loss channel with random latency.
- Message types: `POSE_UPDATE`, `COMMAND`, `TASK_ASSIGN`, `SCATTER`, `REGROUP`, `FOLLOW`, `STOP`, `ACK`, `HEARTBEAT`.
- Commands are **reliable**: they carry an id, are acknowledged, and are re-sent until acknowledged, so a lost `SCATTER` still arrives eventually.
- Live link health per follower (`ONLINE`, `DEGRADED`, `OFFLINE`), per-link statistics, and a communication log that only shows what the network model actually did.
- Force 100 % packet loss to test dead-reckoning behaviour.

**Safety**
- The world is a bounded rectangle. Robots cannot leave it: targets are validated and clamped, a soft boundary guard steers robots away from walls, and a hard clamp is a last-resort numerical guard.
- Inter-agent avoidance, a "yield to whoever is ahead" speed rule, and a rigid-formation shift near walls so the formation does not collapse into a pile.
- NaN / Inf detection: the simulation halts and reports which agent failed instead of corrupting the display.
- Bad commands never crash anything; they return a clear message.

**Interfaces**
- Keyboard driving of the leader (W/A/S/D, SPACE, R, X, F).
- Click-on-map GOTO.
- Command history, status events, and CSV logging.

---

## Install

Python 3.10 or newer. Run every command **from the project root** (the folder that contains `simulation/`, `web/`, `experiments/`).

**Windows PowerShell**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # if scripts are blocked: Set-ExecutionPolicy -Scope Process Bypass
python -m pip install -r requirements.txt pytest
```

**Windows Git Bash** (note: `py` is usually *not* available there; use `python`)

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt pytest
```

**Linux / macOS**

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt pytest
```

`requirements.txt`: numpy, scipy, matplotlib, pandas, fastapi, `uvicorn[standard]` (includes `websockets` for the live stream; without it the dashboard falls back to polling), jinja2, httpx (API tests). Optional, only for the browser smoke test: `pip install playwright && python -m playwright install chromium` (the test is skipped when unavailable).

Test, dashboard, benchmark:

```bash
python -m pytest -q                                   # 194 tests in the author's Linux sandbox (see HANDOFF.md)
python -m web.app                                     # dashboard at http://127.0.0.1:8000
python -m experiments.run_benchmark --quick --out quick_out    # ~30 s smoke benchmark
python -m experiments.run_benchmark --tag my_run --workers 2   # full benchmark (1000 runs, ~6 min on 2 cores)
```

Existing benchmark folders (`eval`, `eval_v2`) are protected: a run into an existing `--tag` fails unless you pass `--overwrite`.

---

## Quick start

### 1. Web dashboard (recommended)

```bash
python -m web.app
```

Open <http://127.0.0.1:8000>. Options:

```bash
python -m web.app --host 0.0.0.0 --port 8080 --seed 7
uvicorn web.app:app --reload        # development auto-reload
```

### 2. Matplotlib window

```bash
python -m visualization.matplotlib_view
```

### 3. Headless / scripting

```python
from simulation import MultiAgentSimulation

sim = MultiAgentSimulation()
sim.submit_command("GOTO 10 5")
sim.run(20)                      # simulate 20 seconds
print(sim.status_text())
```

### 4. Jupyter

```python
from visualization import MatplotlibView
view = MatplotlibView()
view.to_html(duration=20)        # inline playback
```

For live keyboard and mouse control inside Jupyter, enable the ipympl backend
first (`%matplotlib widget`).

---

## The web dashboard

A single workspace: the **arena** (centre of attention), a **synchronised analysis stack** below it and a tabbed **side panel**.
The browser only displays data and sends validated requests; nothing in it simulates robots.

**Two data sources use the same renderers**

* **Live** – the real-time engine (WebSocket, polling fallback). Rolling plots over 30/60/120 s.
* **Replay** – a saved, versioned JSON recording. Play/pause, 0.25–4× speed, step ±1 frame, slider, click/drag on any plot to seek,
  jump to the peak formation error or minimum separation. Replay shows the *saved* frames; **Rerun & compare** re-simulates the saved
  seed + configuration and reports the deviation (normally exactly 0 on the same code version; not guaranteed otherwise).

**Arena layers** (toggle in the bar): trails (5/10/30 s/all), communication links (fresh ≤ 0.3 s / stale ≤ 1 s / lost, from the real
message age), desired formation slots and skeleton (from the *actual* leader pose), slot-error vectors, the controller's own
dead-reckoned target, fault start/end markers, closest-approach marker (red if below the collision distance), live closest-pair
distance, supervisor-state rings, isolated-agent rings, grid with units, scale bar, legend and status overlay.

**Analysis plots** (shared time axis, fault intervals shaded on every panel): formation RMS error, minimum separation (collision
threshold), communication quality, leader-message age, supervisor state per follower, connectivity (isolated followers and λ₂),
heading/speed disagreement (consensus).

**Side tabs**

| tab | content |
|---|---|
| Experiment | controller, supervisor on/off, duration, seed, agents, formation, fault profile + start/length/probability/latency/jitter, background loss. **Apply to live** (reset), **Run & record** (headless, saved, opens in Replay), **Save/Load config** (validated JSON). Live fault injection. |
| Replay | recordings list, load/upload/download, rerun & compare, investigation summary, the four recovery milestones |
| Inspector | supervisor state with generated reason, transition history (click to seek), per-agent table at the cursor |
| Network | connectivity graph diagnostics, interruptions, consensus metrics, link statistics, packet log (live) |
| Operator | the original mission commands, GOTO, keyboard, tasks, command history |
| Benchmark | measured table from `experiments/results_resilience/eval_v2` (falls back to `eval`) |

**Keyboard (live):** W A S D drive, SPACE stop, R regroup, X scatter, F follow. Replay: ← → step, SPACE play/pause.

**The four "recovery" events are never merged:** communication restored (message age ≤ 0.3 s), network connectivity restored,
heading consensus achieved, formation recovered (the unchanged sustained criterion). Recovery time is shown only when that
criterion is met.

**Honesty notes shown in the UI:** connectivity and consensus panels are labelled *global diagnostic* (a follower cannot see them);
HOLD is a bounded fallback, not a safety guarantee.

---

## The Matplotlib window

Same engine, same drawing rules (fixed frame, persistent artists, live
stepping).

| Control | Action |
|---|---|
| Buttons | FOLLOW, SCATTER, REGROUP, STOP, RESUME, ALLOCATE, MODE (cycles AUTO → MANUAL → COMMAND) |
| Command box (bottom) | Type any command and press Enter. Typing here does not drive the robot. |
| Left-click on map | `GOTO` that point |
| Keys | W/S/A/D drive, SPACE stop, R regroup, X scatter, F follow |

Panels on the right show agents, network, task allocation, the real
communication log, command history and keyboard state. The title shows time,
mode, mission, formation error and minimum separation.

Matplotlib's own shortcuts for those keys (save, fullscreen, home, …) are
disabled while the view is open.

Extras: `view.save_frame("shot.png")`, `view.save_animation("run.gif", duration=15)`,
`view.run_steps(n)` for headless runs.

---

## Commands reference

Commands are case-insensitive and work from the dashboard command box, the
Matplotlib command box, or code via `sim.submit_command("...")`.

| Command | Effect |
|---|---|
| `GOTO x y` | Leader drives to world coordinate (x, y); followers keep formation. Out-of-world targets are clamped, NaN/inf rejected. |
| `MOVE dx dy` | Like GOTO, but relative to the leader's current position. |
| `SCATTER` | Followers disperse to individual safe points around the leader. |
| `REGROUP` | Followers return to their formation slots, then the mission becomes `FOLLOWING`. |
| `FOLLOW` | Restore normal leader–follower behaviour (cancels active tasks). |
| `STOP` | Stop everything safely and remember the mission. |
| `RESUME` | Continue the interrupted mission. |
| `FORMATION` | Show the current offsets. |
| `FORMATION WEDGE\|LINE\|COLUMN` | Change formation and regroup. |
| `STATUS` | One-screen summary of every agent, link state and network loss. |
| `TASK id x y [priority]` | Create a task (priority 1 = most urgent). |
| `ALLOCATE` | Assign pending tasks to free followers. |
| `TASKS` | List tasks. |
| `CLEARTASKS` | Delete all tasks. |
| `MODE AUTO\|MANUAL\|COMMAND` | Choose how the leader is driven. |

**Single-agent prefix.** `AGENT 2 GOTO 10 5`, `AGENT 3 STOP`, `AGENT 3 RESUME`.
Also `A2 …` and `F2 …`. `GOTO` works for the leader (`LEADER GOTO 5 5`, or no
prefix) and for any follower. `STOP` and `RESUME` work per **follower**; with no
prefix, `ALL`, or `LEADER` they act on the **whole swarm** (the leader cannot be
stopped on its own). Every other command acts on the whole swarm.

Comma separators are accepted: `GOTO 10,5`.

Any new motion command issued while stopped cancels the stop automatically.

---

## Keyboard control

| Key | Action |
|---|---|
| **W** / **↑** | Accelerate forward (hold) |
| **S** / **↓** | Accelerate in reverse (hold) |
| **A** / **←** | Turn left (hold) |
| **D** / **→** | Turn right (hold) |
| **SPACE** | `STOP` |
| **R** | `REGROUP` |
| **X** | `SCATTER` |
| **F** | `FOLLOW` |

Pressing a driving key switches to `MANUAL` mode automatically (and cancels a
running GOTO). Speed ramps up while a key is held and coasts back to zero when
released; turning ramps the same way. Keyboard input never moves robots
directly: it produces a desired speed and turn rate that goes through the same
boundary guard, actuator lag and physics as every other command.

In the browser, keys are ignored while you are typing in a text box or select.

---

## Modes and mission states

**Leader drive mode** (`MODE …`): how the leader is driven.

| Mode | Behaviour |
|---|---|
| `AUTO` | Follows a predefined smooth trajectory (the notebook's open-loop pattern). The boundary guard turns it away from walls. This is the default. |
| `MANUAL` | Driven by the keyboard. |
| `COMMAND` | Holds still until you issue a command such as `GOTO`. Issuing `GOTO` switches to this mode. |

**Mission state** (`MISSION …`): what the swarm as a whole is doing.

| State | Meaning |
|---|---|
| `FOLLOWING` | Followers hold formation slots. |
| `GOTO` | Leader is driving to a target. Returns to the previous state on arrival (`GOTO COMPLETE`). |
| `SCATTERING` | Followers are dispersing or holding scatter points. |
| `REGROUPING` | Followers are returning to slots. Becomes `FOLLOWING` on completion. |
| `TASK_EXECUTION` | Followers are working on allocated tasks. Auto-regroups when all tasks are done. |
| `STOPPED` | Everything stopped. `RESUME` restores the saved state. |

**Per-agent modes** shown in the Agents panel: `AUTO`, `MANUAL`, `IDLE` and
`GOTO` (leader or single follower), `FOLLOW`, `REGROUP`, `SCATTER`, `TASK`,
`STOPPED`.

---

## How it works

### One simulation tick (`MultiAgentSimulation.step`)

1. **Operator layer.** Keyboard one-shots run, then the command state machine advances (GOTO arrival, scatter/regroup completion, task progress).
2. **Leader.** Its command comes from `AUTO`, the keyboard, `GOTO` or idle. It passes through the boundary guard and a "yield to anyone ahead" rule, then through the RK4 plant (unicycle plus first-order actuator lag).
3. **Network.** The leader broadcasts `POSE_UPDATE`; unacknowledged commands are re-sent every 0.25 s; followers send a `HEARTBEAT` every 0.5 s; due packets are delivered and applied.
4. **Followers** (updated one after another, as in the original notebook). Each dead-reckons the leader from its last packet, picks the control law for its mode, adds avoidance and the boundary guard, and integrates.
5. **Safety and bookkeeping.** NaN/Inf check, hard clamp, formation error, minimum separation, link health, logging.

### Control

- **Formation tracking (FOLLOW / REGROUP):** slot = leader pose + rotated offset. Body-frame error drives a velocity PID and a heading PID. Gains adapt to the error size. Neighbour coupling keeps followers evenly spaced. A forward feed-forward uses the leader's actual speed.
- **Go-to-point (GOTO / SCATTER / TASK):** a heading controller plus speed proportional to remaining distance, so robots slow smoothly and stop inside a tolerance. Robots turn in place when the target is behind them.
- **Avoidance:** an artificial-potential field with a small tangential component (so head-on robots sidestep to one side), force capping, and heading bending, which prevents deadlocks.

### Network and dead reckoning

- Channel: two-state Gilbert–Elliott (good/bad) burst-loss model plus random latency of 1–4 steps (50–200 ms).
- Latency is **causal**: a packet arrives after its delay, not instantly.
- Dead reckoning: while packets are missing, followers extrapolate the leader's pose from its last position and velocity. In the upgraded engine the velocity decays exponentially (`dr_lambda`), so a long blackout settles into a stationary hold instead of drifting indefinitely.
- Link status: `OFFLINE` if nothing has arrived for 2 s; `DEGRADED` if recent loss is above 20 % or nothing has arrived for 0.6 s.
- Commands are acknowledged and retried (up to 60 attempts). The newest command to a follower replaces older unacknowledged ones.

### Safety layers (boundaries)

1. **Target validation.** Operator targets are checked; outside-world targets are clamped inside, NaN/inf rejected.
2. **Soft boundary guard.** Inside a margin zone (default 2 m) the command blends toward "face inward" and speed drops if moving outward. It fades out near a robot's own target so a goal near a wall can still be reached.
3. **Rigid formation shift.** If the formation would stick out of the world, the whole formation shifts inward as one block so slot spacing is preserved.
4. **Hard clamp.** Last-resort position clamp (counted; normally 0).

---

## Project structure

```
multi_agent_digital_twin/
├── README.md
├── requirements.txt
├── simulation/                 # the engine (no UI imports)
│   ├── config.py               # world bounds, Config dataclass, defaults
│   ├── kinematics.py           # RK4 unicycle plant, frame transforms
│   ├── agent.py                # Agent, AgentMode, LinkStatus, agent creation
│   ├── messages.py             # Message, CommEvent, MessageBus
│   ├── network.py              # Gilbert-Elliott channel, dead reckoning, Network
│   ├── collision.py            # avoidance, boundary guard, target validation, clamp
│   ├── formation.py            # presets, slots, scatter targets, regroup check
│   ├── controller.py           # PID, adaptive gains, follower and go-to-point laws
│   ├── tasks.py                # Task, Allocator, NearestAvailableAllocator, TaskManager
│   ├── commands.py             # parser, mission state machine, command handlers
│   ├── keyboard.py             # key state -> desired leader command
│   ├── logger.py               # CSV logging
│   ├── metrics.py              # ITAE/RMSE, Routh-Hurwitz, sweeps, Monte-Carlo
│   ├── supervisor.py           # resilience supervisor (NORMAL/DEGRADED/HOLD/RECOVERING)
│   ├── connectivity.py         # communication graph, Laplacian/lambda2, consensus metrics, tracker
│   ├── recording.py            # versioned recordings, validation, Replay, RunSpec, rerun comparison
│   ├── simulation.py           # MultiAgentSimulation engine + simulate() wrapper
│   └── __init__.py
├── visualization/
│   ├── matplotlib_view.py      # interactive Matplotlib client
│   └── __init__.py
└── web/
    ├── app.py                  # FastAPI server + background simulation thread
    ├── templates/index.html    # dashboard page
    └── static/
        ├── app.js              # live/replay orchestration, panels, controls
        ├── js/core.js          # helpers, palette, API wrapper
        ├── js/viewport.js      # arena renderer (scene-driven)
        ├── js/plots.js         # synchronised analysis plots
        └── style.css
```

Dependency rule: `simulation/` never imports `visualization/` or `web/`.
Both front ends talk to the engine only through its public API.

---

## Python API

```python
from simulation import MultiAgentSimulation, SimMode, Config

sim = MultiAgentSimulation(
    cfg=Config(),              # all tunables
    n_agents=5,                # 1 leader + 4 followers
    control_mode="advanced",   # "zoh" | "pidr" | "advanced"
    seed=42, loss_scale=1.0,   # network randomness / loss multiplier
    sim_mode=SimMode.AUTO,     # AUTO | MANUAL | COMMAND
    formation="WEDGE",         # WEDGE | LINE | COLUMN
)

sim.step()                          # advance one tick (dt = 0.05 s)
sim.run(30)                         # advance 30 seconds
res = sim.submit_command("SCATTER") # res.ok, res.message
sim.handle_key("w", True)           # keyboard event
state = sim.get_state()             # JSON-friendly snapshot (agents, targets, tasks,
                                    # network, messages, command history, ...)
sim.network.set_forced_loss(True)   # force 100 % packet loss
```

Useful extras: `sim.attach_logger(SimLogger())`, `sim.tasks`, `sim.bus.recent()`,
`sim.network.snapshot()`.

To plug in your own task-allocation strategy, subclass `Allocator`
(`simulation/tasks.py`) and pass it to `TaskManager`; the rest of the system
does not change.

---

## REST / WebSocket API

Start the server, then browse the interactive docs at
<http://127.0.0.1:8000/docs>.

| Method | Path | Body | Purpose |
|---|---|---|---|
| GET | `/` | | Dashboard page |
| GET | `/state` | | Full snapshot |
| GET | `/agents` | | Agent list |
| GET | `/messages?n=40&hide_pose=false` | | Communication log |
| GET | `/network` | | Network statistics |
| GET | `/tasks` | | Tasks and allocation text |
| POST | `/command` | `{"text": "GOTO 10 5"}` | Any text command |
| POST | `/goto` | `{"x":10,"y":5,"agent":"ALL"}` | `agent`: `ALL`, `LEADER`, or a number |
| POST | `/scatter` `/regroup` `/follow` | | Swarm commands |
| POST | `/stop` `/resume` | `{"agent":"ALL"}` (optional) | Stop / resume |
| POST | `/formation/{name}` | | `WEDGE`, `LINE`, `COLUMN` |
| POST | `/mode` | `{"mode":"AUTO"}` | Leader drive mode |
| POST | `/key` | `{"key":"w","down":true}` | Keyboard events |
| POST | `/tasks` | `{"id":"A","x":4,"y":7,"priority":1}` | Add a task |
| POST | `/tasks/allocate` `/tasks/clear` | | Allocate / clear |
| POST | `/network/loss` | `{"forced":true}` | Force 100 % packet loss |
| POST | `/sim/pause` | `{"paused":true}` | Pause the clock |
| POST | `/sim/speed` | `{"speed":2}` | 0.1 – 8 |
| POST | `/sim/reset` | `{"seed":42,"loss_scale":1,"control_mode":"advanced","sim_mode":"AUTO","n_agents":5,"formation":"WEDGE"}` | Restart |
| WS | `/ws` | | State stream at about 10 Hz |

Command endpoints return `{"ok": bool, "message": "...", "command": "..."}`.
Invalid request bodies return HTTP 422 with a validation message.

---

## Configuration

All tunables live in `simulation/config.py` (`Config`). Pass your own instance
to `MultiAgentSimulation(cfg=Config(...))`. Selected values:

| Setting | Default | Meaning |
|---|---|---|
| world bounds | x −4…22, y −7…9 | World rectangle in metres |
| `dt` | 0.05 s | Control and integration step (20 Hz) |
| `kp, ki, kd` | 1.8, 0.18, 0.65 | Follower PID gains |
| `max_v`, `max_w` | 1.25 m/s, 2.4 rad/s | Actuator limits |
| `boundary_margin` | 2.0 m | Width of the soft boundary zone |
| `target_margin` | 0.6 m | How far inside the wall targets are kept |
| `safe_distance` | 0.70 m | Avoidance radius |
| `yield_min_distance` | 0.45 m | Robots ahead closer than this block motion |
| `goto_tolerance` | 0.25 m | Leader arrival radius |
| `target_tolerance` | 0.30 m | Follower arrival radius (scatter / task) |
| `regroup_tolerance` | 0.35 m | Per-follower radius for `REGROUP COMPLETE` |
| `scatter_radius` | 3.0 m | Scatter ring radius |
| `packet_good_to_bad`, `packet_bad_to_good` | 0.025, 0.22 | Gilbert–Elliott transition probabilities |
| `base_delay_steps`, `max_delay_steps` | 1, 4 | Latency range (steps of `dt`) |
| `dr_lambda` | 0.12 /s | Dead-reckoning velocity decay |
| `heartbeat_period` | 0.5 s | Follower heartbeat interval |
| `cmd_retry_period` | 0.25 s | Command retry interval |
| `offline_timeout_s` | 2.0 s | Silence before a link is `OFFLINE` |

---

## Logging and metrics

**CSV log** (optional, off by default):

```python
from simulation import MultiAgentSimulation, SimLogger
sim = MultiAgentSimulation(logger=SimLogger("logs"))
sim.run(60)
sim.logger.close()
```

One row per agent per tick, in `logs/sim_<timestamp>.csv`:

`timestamp, agent_id, x, y, theta, v, omega, mode, target_x, target_y,
packet_sent, packet_received, packet_lost, packet_latency, task_id`

Packet columns count that tick's traffic: sent *by* the agent, and received or
lost *to* the agent.

**Metrics** (`simulation.metrics`): `compute_metrics` (ITAE, RMSE, peak error,
control effort, minimum separation, packet loss %, collision %),
`routh_hurwitz_cubic`, `stability_scan`, `robustness_sweep`, `monte_carlo`,
`summarize_monte_carlo`.

---

## Research mode (notebook compatibility)

`simulate()` runs a fixed-length batch and returns the same history dictionary
the original notebook produced:

```python
from simulation import simulate, compute_metrics, monte_carlo, summarize_monte_carlo

h = simulate("advanced", seed=101)          # "zoh" | "pidr" | "advanced"
print(compute_metrics(h))

results = monte_carlo(simulate, runs=30)
print(summarize_monte_carlo(results))
```

- `legacy=True` (default) reproduces the original notebook exactly: no
  boundary logic, instantaneous back-dated packets, constant feed-forward. The
  results match the notebook's to about 1e-9.
- `legacy=False` runs the upgraded engine (boundary guard, causal latency,
  decaying dead reckoning, avoidance improvements).

Note: in the baseline `zoh` and `pidr` modes there is deliberately no collision
avoidance (as in the notebook), so their minimum separation can be small. Only
`advanced` avoids collisions.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: simulation` | Run from the project root, e.g. `python -m web.app`. |
| Page says "reconnecting…" | The server stopped, or a proxy blocks WebSockets. The page falls back to polling and reconnects on its own. |
| A key seems stuck | Click an empty part of the page, or press and release the key. The page also releases all keys when the window loses focus. |
| Keys do nothing | You are focused in a text box or dropdown; click the map or the page background. |
| Command says `SIMULATION HALTED` | The engine detected an invalid state. Press **Reset**. |
| Followers are far from the leader with heavy loss | Expected. With long blackouts the leader estimate fades to a hold. Untick forced loss or lower **Loss x**. |
| Scatter targets show as grey x | The `SCATTER` command has not reached that follower yet; it is being retried. |
| Matplotlib window does not open | Use a desktop backend (for example `pip install pyqt5` or use TkAgg), or use the web dashboard. |
| Port already in use | `python -m web.app --port 8001`. |

---

## Known limitations

- A single simulation instance is shared by everyone connected to the server (open the dashboard in two browsers and both control the same swarm).
- `ALLOCATE` uses true follower positions, not positions reported by heartbeats.
- Followers only change mode when a command is actually delivered, so under heavy loss a command can take a moment to take effect (by design).
- The dashboard was checked in headless Chromium only (Linux); it has not been run on Windows browsers by the author.
- The default AUTO path cannot be tracked by the outer wedge slots (≈ 1.5 m error with or without faults); use the `*_gentle` benchmark scenarios for recovery experiments. See `docs/EXPERIMENT_PROTOCOL.md` section 10 for this and four other audit findings (per-packet burst process, derivative noise chatter, seed aliasing, uplink timeouts).
- A connectivity-aware supervisor was deliberately not implemented (a follower cannot know the global graph).

---

## Roadmap

- `tests/` (kinematics, network, commands, tasks, boundaries, notebook regression) and `scenarios/` (default, scatter, regroup, tasks).
- Hungarian / auction task allocators (the `Allocator` interface is ready).
- Hardware-in-the-loop bridge (real ESP8266 pair behind the network interface).
- Webots: replace `kinematics.rk4_step` and the view; the commands, tasks, messages and control logic stay unchanged.
- Re-fit network parameters from measured ESP-NOW latency and loss on real hardware.
## ResilientSync adaptive communication-aware prototype

A separate `adaptive_comm` controller mode is available alongside `zoh`, `pidr`, and `advanced`. It estimates communication quality from the age of the latest leader pose and receiver-observed pose-sequence gaps. Under poor quality it softens feedback and scales translation conservatively while retaining angular steering. This is a heuristic prototype, not a calibrated probability or a proven performance improvement.

Run the initial regression tests from the repository root:

```bash
python -m pip install pytest
python -m pytest -q
```

Run a reproducible comparison including a forced communication blackout:

```bash
python -m experiments.run_comparison --duration 18 --seeds 42 43 44
```

The script writes CSV metrics and plots to `experiments/results/`. Report actual measured outcomes and limitations; do not assume the adaptive mode outperforms the existing controllers.


---

## Resilience extension (supervisor, fault injection, connectivity, replay, benchmark)

Details: `docs/EXPERIMENT_PROTOCOL.md`, `docs/IMPLEMENTATION_PLAN.md`, `HANDOFF.md`.

* **Resilience supervisor** (`simulation/supervisor.py`) inside `adaptive_comm`; `Config(supervisor_enabled=False)` reproduces the pre-supervisor controller exactly.
* **Fault injection** (`simulation/network.py`): `make_fault_profile("blackout"|"random_loss"|"burst_loss"|"latency_jitter"|"blackout_latency", start, duration, ...)` → `MultiAgentSimulation(fault_profile=...)`. Seeded and logged.
* **Connectivity & consensus** (`simulation/connectivity.py`): leader→follower link graph from real delivery statistics, components, isolated followers, algebraic connectivity λ₂, wrap-aware heading disagreement, speed disagreement, interruption tracking. Diagnostic only; never fed to controllers.
* **Recordings & replay** (`simulation/recording.py`): `RunSpec` → `run_spec()` → versioned JSON; `Replay` (seek/step/peak error/min separation/investigation summary/recovery milestones); `compare_rerun()`.
* **Benchmark** (`experiments/run_benchmark.py`): per-run + aggregate CSV, JSON, report, plots with fault bands; now also connectivity, consensus and command-limit metrics and two feasibility scenarios (`nominal_gentle`, `blackout_gentle`).
* **API additions:** `GET /connectivity`, `POST /experiments/config|run`, `GET /recordings[/{id}[/frame|/summary]]`, `POST /recordings/{id}/rerun`, `POST /recordings/upload`.

```python
from simulation.recording import RunSpec, run_spec, Replay
rec = run_spec(RunSpec(control_mode="adaptive_comm", seed=7, fault_profile="blackout"))
r = Replay(rec); r.seek(6.0); print("\n".join(r.summary()["text"]))
```

**Measured status (eval_v2, 10 seeds):** on the feasible path with a 3 s blackout the supervisor beats the earlier adaptive prototype (RMSE 0.188 → 0.143 m, 10/10 seeds) but not the plain `advanced` (0.097 m) or `pidr` (0.117 m) baselines; its feed-forward reduction is the cause (`sup_no_ff` = `advanced`). On the default path all arms sit at ≈ 1.5 m regardless. No controller is declared the winner.
`experiments/results/controller_comparison.csv` was produced with the removed total-speed cap (adaptive RMSE 2.29 m); current code gives ≈ 1.67 m — see HANDOFF.md.


## Webots 3D validation (adapter, world, stand-in)

A Webots world with a leader and followers, an adapter that runs the **unchanged** ResilientSync controllers, supervisor and faulted network against a real plant, per-step CSV logging and plots. **Status: the Webots side has never been run** (no Webots in the authoring environment); the adapter, fault injection, logging and analysis were validated with a Python stand-in plant (clearly labelled `plant=standin`).

* Run guide (Windows): `webots_project/README.md`
* Validation report (what ran where, results, limitations): `docs/WEBOTS_VALIDATION.md`
* Offline: `python scripts/run_standin_trials.py` then `python scripts/analyze_runs.py --runs results/standin/... --out ...`
* Tests: `tests/test_webots_*.py`
