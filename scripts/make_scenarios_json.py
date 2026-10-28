"""Regenerate webots_project/config/scenarios.json from experiments.run_benchmark.SCENARIOS."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from experiments.run_benchmark import SCENARIOS, gentle_trajectory, maneuver_trajectory
from resilientsync_webots.faults import Scenario, scenario_to_dict, DEFAULT_SCENARIO_FILE

def tname(fn):
    return {None: "default", gentle_trajectory: "gentle", maneuver_trajectory: "maneuver"}[fn]

out = {"_comment": "Fault-injection configuration. Same FaultEvent semantics as simulation/network.py. "
                   "Times are simulation seconds. Edit and re-run tests/test_webots_faults.py.",
       "default_duration_s": 18.0,
       "scenarios": {n: scenario_to_dict(Scenario(n, s.description, s.profile, tname(s.trajectory)))
                     for n, s in SCENARIOS.items()}}
DEFAULT_SCENARIO_FILE.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print("wrote", DEFAULT_SCENARIO_FILE, list(out["scenarios"]))
