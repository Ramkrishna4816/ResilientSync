"""Run scenarios x arms x seeds through the adapter with the STAND-IN plant (not Webots)."""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from experiments.run_benchmark import ARMS
from resilientsync_webots.faults import load_scenarios
from resilientsync_webots.frames import FrameMap
from resilientsync_webots.runner import RunSpec, run_closed_loop
from resilientsync_webots.standin import StandInPlant

ap = argparse.ArgumentParser()
ap.add_argument("--scenarios", nargs="+", default=["nominal_gentle", "blackout_gentle"])
ap.add_argument("--arms", nargs="+", default=["pidr", "advanced", "adaptive_legacy", "adaptive_supervisor"])
ap.add_argument("--seeds", nargs="+", type=int, default=[100, 101, 102])
ap.add_argument("--n-agents", type=int, default=5)
ap.add_argument("--duration", type=float, default=18.0)
ap.add_argument("--out", default=str(ROOT / "results" / "standin"))
ap.add_argument("--rotated-frame", action="store_true", help="run the plant in an offset/rotated world frame")
a = ap.parse_args()
sc = load_scenarios()
fm = FrameMap(3.0, -2.0, 0.5) if a.rotated_frame else FrameMap()
for s in a.scenarios:
    for arm in a.arms:
        for seed in a.seeds:
            spec = RunSpec(s, arm, seed, a.duration, a.n_agents, plant="standin")
            meta = run_closed_loop(spec, sc[s], ARMS[arm], StandInPlant(a.n_agents, fm),
                                   Path(a.out) / spec.run_id, {"frame": [fm.origin_x, fm.origin_y, fm.yaw]})
            print(f"{spec.run_id}: {meta['status']} ({meta['steps_run']} steps, {meta['wall_s']} s)")
