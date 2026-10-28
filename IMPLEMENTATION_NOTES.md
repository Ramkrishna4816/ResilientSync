# ResilientSync: adaptive communication-aware prototype

## What changed

- Added `adaptive_comm` as a fourth controller mode; the existing `zoh`, `pidr`, and `advanced` modes are preserved.
- Added receiver-side pose sample sequence numbers and a rolling window of inferred missing pose updates.
- Added a bounded communication-quality heuristic based on latest-pose age and inferred sequence gaps.
- The adaptive controller changes gain strength and leader-velocity feed-forward only when quality falls below a configurable threshold. Position feedback and angular steering remain active.
- Added per-follower communication quality to API state and the agent table.
- Added pytest tests and a reproducible blackout comparison runner.

## Verification performed

Commands run in the uploaded source copy:

```bash
python -m compileall -q simulation visualization web tests experiments
python -m pytest -q
python -m experiments.run_comparison --duration 18 --blackout-start 5 --blackout-duration 3 --seeds 42 43 44
```

Result: 6 tests passed. The three original modes (`zoh`, `pidr`, `advanced`) produced state arrays and formation-RMS arrays identical to the unmodified uploaded source for seed 42, 3 seconds, and `legacy=False`.

## Sample experiment result (18 s; blackout from 5–8 s; seeds 42, 43, 44)

Mean over three seeds:

| Mode | Formation RMSE (m) | Peak error (m) | Minimum separation (m) | Mean control effort | Collision samples (%) |
|---|---:|---:|---:|---:|---:|
| zoh | 2.6880 | 4.6345 | 0.4599 | 1.0879 | 0.5556 |
| pidr | 1.5408 | 2.2608 | 1.0924 | 1.0256 | 0.0000 |
| advanced | 1.6087 | 2.4328 | 1.1521 | 1.0524 | 0.0000 |
| adaptive_comm | 1.6377 | 2.4932 | 1.1719 | 1.0375 | 0.0000 |

Interpretation: in this initial small benchmark, `adaptive_comm` has slightly greater RMSE than `advanced`, while showing slightly larger minimum separation and slightly lower mean effort. These differences are not proof of a statistically significant improvement. Do not claim the adaptive controller is better overall. Use this as a baseline for further tuning and more seeds.

## How to run on Windows / Git Bash

From the project root:

```bash
python -m pip install -r requirements.txt
python -m pip install pytest
python -m pytest -q
python -m experiments.run_comparison --duration 18 --blackout-start 5 --blackout-duration 3 --seeds 42 43 44
python -m web.app
```

Open `http://127.0.0.1:8000`, select `adaptive communication-aware` in the Control dropdown, and use the existing forced-loss control to demonstrate degraded communication. The comparison script writes CSV and PNG outputs to `experiments/results/`.

## Limitations to disclose

- This is a heuristic prototype, not a learned controller or a proven novel algorithm.
- The initial benchmark uses only three seeds and one blackout scenario.
- Sequence gaps estimate missed pose updates; they do not provide a calibrated packet-loss probability.
- The current simulation still has centralized/global state for some neighbor-coupling and avoidance calculations; this is not a fully decentralized physical-robot implementation.

## Update (resilience extension)
The sample table above (adaptive_comm RMSE 1.6377 m) and `experiments/results/controller_comparison.csv` (2.289 m) come from two different code versions; see `HANDOFF.md` §2 and `docs/EXPERIMENT_PROTOCOL.md` for the current, reproducible numbers.
