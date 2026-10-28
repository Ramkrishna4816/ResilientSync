"""Test helpers for the Webots adapter (stand-in plant only; Webots is not required)."""
import tempfile
from pathlib import Path

from experiments.run_benchmark import ARMS
from resilientsync_webots.analysis import load_run
from resilientsync_webots.faults import load_scenarios
from resilientsync_webots.runner import RunSpec, run_closed_loop
from resilientsync_webots.standin import StandInPlant

SC = load_scenarios()


def run_short(scenario, arm="adaptive_supervisor", seed=100, duration=12.0, n=5, plant=None, out=None):
    out = Path(out or tempfile.mkdtemp())
    spec = RunSpec(scenario, arm, seed, duration, n, plant="standin")
    meta = run_closed_loop(spec, SC[scenario], ARMS[arm], plant or StandInPlant(n), out)
    return load_run(out), meta
