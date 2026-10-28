"""Closed loop shared by the Webots coordinator and the stand-in plant.

A *plant* implements:
    place(states_rs)  put robots at the engine's seeded initial poses (best effort)
    time()            plant clock [s]
    measure()         (n,5) RS-frame states [x,y,theta,v,omega]
    apply(wheels)     (n,2) wheel speeds [rad/s]
    advance()         advance plant by one control period
"""
from __future__ import annotations

import time as _time
from dataclasses import dataclass, asdict
from pathlib import Path

from simulation.metrics import compute_recovery_metrics  # noqa: F401  (re-exported for analysis)

from .adapter import WebotsAdapter
from .faults import Scenario
from .runlog import RunWriter


@dataclass
class RunSpec:
    scenario: str
    arm: str
    seed: int
    duration_s: float = 18.0
    n_agents: int = 5
    plant: str = "standin"          # "webots" | "standin"
    tag: str = ""

    @property
    def run_id(self) -> str:
        return f"{self.scenario}__{self.arm}__s{self.seed}__n{self.n_agents}"


def run_closed_loop(spec: RunSpec, scenario: Scenario, arm, plant, outdir, extra_meta=None,
                    on_step=None) -> dict:
    adapter = WebotsAdapter(scenario, arm, seed=spec.seed, n_agents=spec.n_agents)
    writer = RunWriter(outdir)
    plant.place(adapter.initial_states())
    n_steps = int(round(spec.duration_s / adapter.dt))
    wall0, status, err = _time.time(), "completed", None
    k = 0
    try:
        for k in range(n_steps):
            out = adapter.step(plant.time(), plant.measure())
            if hasattr(plant, "extras"):              # plant-only observations (height, tilt)
                out.row.update(plant.extras())
            writer.step(out.row)
            if on_step:
                on_step(out, adapter)
            if out.halted:
                status, err = "engine_halted", adapter.sim.fault
                break
            plant.apply(out.wheels)
            plant.advance()
    except Exception as exc:                       # a crashed controller must be reported, not hidden
        status, err = "controller_error", f"{type(exc).__name__}: {exc}"
    meta = {"spec": asdict(spec), "status": status, "error": err, "steps_run": k + 1,
            "max_time_skew_s": adapter.max_skew, "wall_s": round(_time.time() - wall0, 2),
            "supervisor_active": adapter.supervisor_active,
            "scenario_window": scenario.window,
            "collision_distance_m": adapter.cfg.collision_distance, "dt": adapter.dt}
    meta.update(extra_meta or {})
    try:                                           # dashboard-replayable record of this run
        from .dashboard_export import build_webots_recording
        from simulation.recording import save_recording
        save_recording(build_webots_recording(adapter, spec, scenario, arm), Path(outdir) / "recording.json")
        meta["recording"] = "recording.json"
    except Exception as exc:                       # never lose the CSV logs because of the export
        meta["recording_error"] = f"{type(exc).__name__}: {exc}"
    writer.finish(adapter, meta)
    return meta
