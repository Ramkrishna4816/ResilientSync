"""Webots/stand-in run  ->  dashboard recording (simulation.recording format v1).

The engine computes every replayed per-tick quantity (errors, supervisor state, connectivity, ...)
from the poses it is given.  In Webots mode those poses are the MEASURED Webots poses, so a
recording built from the adapter's own engine is a genuine record of the run, not a re-simulation.

  * live:    `build_webots_recording(adapter, ...)`   (called by the runner at the end of every run)
  * offline: `recording_from_run_dir(run_dir)`        re-drives a fresh engine with the logged measured
             poses; because the engine is deterministic given (seed, measured poses), it must reproduce
             the logged commands - the maximum difference is returned as an integrity check.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from simulation.recording import RunSpec as RecordingRunSpec
from simulation.recording import build_recording, validate_recording

ROOT = Path(__file__).resolve().parents[1]


def recording_spec(spec, scenario, arm) -> RecordingRunSpec:
    """Best-effort RunSpec for the dashboard (only used by its 'rerun'; the actual fault profile is stored separately)."""
    kw = dict(control_mode=arm.mode, seed=int(spec.seed), duration=float(max(1.0, spec.duration_s)),
              n_agents=int(spec.n_agents), supervisor_enabled=bool(arm.build_cfg().supervisor_enabled))
    evs = scenario.profile.events
    if len(evs) == 1:
        e = evs[0]
        name = {"blackout": "blackout", "random_loss": "random_loss", "burst_loss": "burst_loss", "latency": "latency_jitter"}.get(e.kind)
        if name:
            kw.update(fault_profile=name, fault_start=float(e.start), fault_duration=float(min(max(e.duration, 0.05), 600.0)))
            if e.kind == "random_loss":
                kw["fault_probability"] = float(e.probability)
            if e.kind == "latency":
                kw.update(extra_latency_s=float(e.extra_latency_s), jitter_s=float(e.jitter_s))
    else:
        kw["fault_profile"] = "none"
    return RecordingRunSpec(**kw).validate()


def build_webots_recording(adapter, spec, scenario, arm) -> dict:
    rec = build_recording(adapter.sim, recording_spec(spec, scenario, arm), stride=1)
    rec["meta"].update(
        source=spec.plant, scenario=spec.scenario, arm=spec.arm, leader_trajectory=scenario.trajectory_name,
        note=(f"Recorded from a {spec.plant.upper()} run: states are the MEASURED poses of that plant; the supervisor, "
              "network and error fields were computed by the ResilientSync engine on those poses. Replay shows these "
              "saved frames. 'Rerun' re-simulates with the NATIVE Python plant and the default leader path, so it is not "
              "expected to match a Webots run."))
    return validate_recording(rec)


def recording_from_run_dir(run_dir):
    """Rebuild a recording from steps.csv; returns (recording, max |logged command - recomputed command|)."""
    import pandas as pd
    from experiments.run_benchmark import ARMS
    from .adapter import WebotsAdapter
    from .faults import load_scenarios
    from .runner import RunSpec

    d = Path(run_dir)
    meta = json.loads((d / "meta.json").read_text())
    s = meta["spec"]
    spec = RunSpec(s["scenario"], s["arm"], s["seed"], s["duration_s"], s["n_agents"], plant=s["plant"], tag=s.get("tag", ""))
    sc, arm = load_scenarios()[spec.scenario], ARMS[spec.arm]
    df = pd.read_csv(d / "steps.csv")
    ad = WebotsAdapter(sc, arm, seed=spec.seed, n_agents=spec.n_agents)
    n, worst = spec.n_agents, 0.0
    for _, row in df.iterrows():
        meas = np.array([[row[f"gt_x_{i}"], row[f"gt_y_{i}"], row[f"gt_th_{i}"], row[f"gt_v_{i}"], row[f"gt_w_{i}"]] for i in range(n)])
        out = ad.step(float(row["t_plant"]), meas)
        logged = np.array([[row[f"cmd_v_{i}"], row[f"cmd_w_{i}"]] for i in range(n)])
        worst = max(worst, float(np.abs(out.commands - logged).max()))
    return build_webots_recording(ad, spec, sc, arm), worst
