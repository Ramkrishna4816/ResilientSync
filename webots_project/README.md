# ResilientSync in Webots (3D) - setup and run guide (Windows + Git Bash)

> **Status:** the world opens in Webots R2025a and the controllers start (user report). **No complete Webots experiment has been verified yet.** The adapter, fault injection, logging, analysis and diagnostics were verified with a Python stand-in plant only. See `docs/WEBOTS_VALIDATION.md` and `docs/WEBOTS_VALIDATION_PROTOCOL.md`.

## 0. Where did my first run's logs go?  (bug fixed in this release)
The previous release resolved the relative `out_dir` against Webots' working directory (the controller folder). If you pressed Play on the world earlier, look for logs there:
```bash
cd ~/Downloads/ResilientSync-stage4-webots/ResilientSync
find . -name meta.json -o -name coordinator_error.txt -o -name steps.csv 2>/dev/null
```
Also note: with the shipped `run_config.json` (`"quit_when_done": true`) Webots **quits itself** after the 18 s scenario. Set it to `false` if you want the window to stay open.

## 1. One-time setup (Git Bash, project root)
```bash
cd ~/Downloads/ResilientSync-stage5-webots/ResilientSync      # the folder you unzip this release into
python --version                                              # 3.10-3.12 expected
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-webots.txt      # numpy, scipy, pandas, matplotlib, pytest (no dashboard stack)
python scripts/check_webots_env.py --write-runtime-ini        # pins Webots' coordinator to THIS venv's python.exe
```
`check_webots_env.py` must end with `Result: ready`. It finds `C:\Users\harih\AppData\Local\Programs\Webots\msys64\mingw64\bin\webots.exe` automatically (or pass `--webots-exe`).

## 2. Offline tests (real pytest on your machine)
```bash
python -m pytest -q tests/test_webots_frames.py tests/test_webots_diffdrive.py tests/test_webots_faults.py tests/test_webots_logging.py tests/test_webots_adapter.py tests/test_webots_assets.py tests/test_webots_runconfig.py tests/test_webots_diagnose.py
python -m pytest -q          # whole suite (needs requirements.txt; the dashboard canvas tests also need: python -m playwright install chromium)
```

## 2b. How to SEE the 3D simulation and the website

### The 3D Webots window
Recommended (opens Webots, runs the scenario in real time, keeps the window open at the end):
```bash
python scripts/run_webots_trials.py --scenarios blackout_gentle --arms adaptive_supervisor --seeds 100 --n-agents 5 --mode realtime --show --keep-open
```
* The coordinator drives the simulation by itself; you do not press Play. Watch the leader (yellow) and the followers; the coloured discs on the floor are the engine's target slots. The camera rides behind/above the leader (`follow "leader"`, Mounted Shot).
* The blackout runs from t = 5 s to 8 s of simulation time (`blackout_gentle`); the clock is in the Webots toolbar.
* When the scenario ends (18 s) Webots stays open. Close the window; the launcher then prints the diagnosis and writes the website replay file.
* `--mode fast` runs faster than real time (not watchable). Without `--keep-open` Webots quits itself when the scenario ends (this is why your earlier run closed on its own).
* Mouse: left-drag rotates, wheel zooms. To leave the leader-following camera: *View > Follow Object > None*.

Manual alternative: start Webots, *File > Open World*, choose `webots_project/worlds/resilientsync_5robots.wbt`, set `"quit_when_done": false` in `webots_project/config/run_config.json` first, press the *Reset* button if time is already running, then Play. (Scenario/seed come from that JSON file.)

### The website (dashboard)
```bash
python -m pip install -r requirements.txt        # one time: adds fastapi, uvicorn, jinja2 (dashboard only)
python -m web.app                                # leave this terminal running
```
Open http://127.0.0.1:8000 in a browser (stop with Ctrl+C in that terminal).
* **Run / live tabs = the Python simulator** (its own plant). They are NOT Webots.
* **Replay tab > Recordings dropdown > `webots__<scenario>__<arm>__s<seed>__n<N>`** shows a Webots run: measured poses, formation error, supervisor states, faults. Every Webots run launched with `run_webots_trials.py` writes `recording.json` and copies it to `recordings/webots__*.json`. For a run made earlier: `python scripts/export_recording.py --latest`, then reload the page.
* Live streaming of a running Webots simulation into the website is **not implemented**; the website replays finished runs.
* The Replay tab's "rerun" button re-simulates with the Python plant and the default leader path, so it is not expected to match a Webots recording.
* If `pip install -r requirements.txt` fails, send me the output (this stack failed once before; the Webots controller does not need it).

## 3. Staged Webots runs (each prints an automatic diagnosis)
```bash
# A. smoke: 3 robots, 6 s, watch it (--show keeps the window, --mode realtime runs at 1x)
python scripts/run_webots_trials.py --scenarios nominal --arms adaptive_supervisor --seeds 100 --n-agents 3 --duration 6 --mode realtime --show
# B. nominal formation, 5 robots
python scripts/run_webots_trials.py --scenarios nominal_gentle --arms adaptive_supervisor --seeds 100 --mode realtime --show
python scripts/diagnose_webots_run.py --latest
# C. blackout (5-8 s)
python scripts/run_webots_trials.py --scenarios blackout_gentle --arms adaptive_supervisor --seeds 100 --mode realtime --show
python scripts/analyze_runs.py --runs results/webots --out results/webots_report --reference --plot-seed 100
```
Do not go to D-F (loss, controller comparison, repeated seeds) until A-C pass `diagnose_webots_run.py` with no `[FAIL]`. Seeds 100-104 are for debugging; 42-51 are the held-out evaluation seeds.
Interactive alternative: set `RS_RUN_CONFIG` (`export RS_RUN_CONFIG="$PWD/webots_project/config/run_config.json"`), start Webots, open `webots_project/worlds/resilientsync_5robots.wbt`, press Play.

## 4. What to send back after the first run
1. The text printed by `run_webots_trials.py` (including the `diagnosis:` lines).
2. `results/webots/<run>/meta.json`, `diagnosis.json`, and `results/webots/<run>.webots.log` (Webots console output; look for the caster warning - it should be gone).
3. If `NO LOGS`: `coordinator_error.txt` and the last 30 lines of the Webots console.
4. A zip of `results/webots/<run>/` (steps.csv etc.) if you want me to analyse the motion.

## 5. Output per run (`results/webots/<scenario>__<arm>__s<seed>__n<N>/`)
`steps.csv` (50 ms ticks: ground-truth pose, **height and tilt**, commands, wheel speeds, saturation, per-follower message age / quality / supervisor state / sequence numbers / sent / lost, formation error, min separation, fault flags), `comm_events.csv`, `deliveries.csv`, `faults.json`, `transitions.json`, `meta.json` (plant = `webots`, Webots version, status, clock skew), `diagnosis.json`.

## 6. Troubleshooting
* **`ModuleNotFoundError: No module named 'numpy'` in the Webots console** (reported on the first real run): the interpreter named in `runtime.ini` has no numpy. Check and fix with that exact interpreter:
  ```bash
  .venv/Scripts/python.exe -m pip list | grep -i -E "numpy|scipy"
  .venv/Scripts/python.exe -m pip install -r requirements-webots.txt
  python scripts/check_webots_env.py --write-runtime-ini     # must show "Webots-style launch test ... OK"
  ```
  A failed `pip install -r requirements.txt` (dashboard packages) aborts the whole install, which is why `requirements-webots.txt` exists.
* **Config/world mismatch** (`loaded world has 3 robots`): use `"n_agents": "auto"` (default now) or open the matching world. Details in `results/webots/_startup_error.txt`.
* **`ModuleNotFoundError: numpy` / `resilientsync_webots`** in the Webots console: Webots used another Python. Re-run `check_webots_env.py --write-runtime-ini` inside the venv (or set Tools > Preferences > Python command). The controller adds the repo root to `sys.path` itself.
* **`world must define DEF RS_0..RS_N-1`**: `n_agents` in the config differs from the world's robot count (3 or 5).
* **No `meta.json`**: see `coordinator_error.txt`, the `.webots.log`, and section 0.
* **`clock_sync` WARN/FAIL in the diagnosis**: engine tick and Webots clock disagree; check `basicTimeStep` 10 ms and the 50 ms period.
* **`tilt`/`height` FAIL**: the robot tips or sinks: report the numbers; the caster model is the first suspect (see protocol section 11).
* **`frozen_*` / `cmd_to_motion_*`**: wheels not responding: check the wheel-driver console lines and the Receiver channel (1).
