"""Declarative fault / scenario configuration (JSON) -> engine FaultProfile.

`webots_project/config/scenarios.json` is the single, human-editable fault-injection
configuration.  It is built with the SAME `FaultEvent` / `FaultProfile` classes the Python
benchmark uses, so a fault means exactly the same thing in both simulators; a test
cross-checks every scenario against `experiments.run_benchmark.SCENARIOS`.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional

from simulation.network import FaultEvent, FaultProfile

DEFAULT_SCENARIO_FILE = Path(__file__).resolve().parent.parent / "webots_project" / "config" / "scenarios.json"
_EVENT_FIELDS = ("kind", "start", "duration", "probability", "p_good_to_bad", "p_bad_to_good",
                 "loss_in_bad", "extra_latency_s", "jitter_s", "label")


def trajectory_by_name(name: str) -> Optional[Callable]:
    """Leader trajectories are the benchmark's own functions (no copy)."""
    if name in (None, "", "default"):
        return None
    from experiments.run_benchmark import gentle_trajectory, maneuver_trajectory
    table = {"gentle": gentle_trajectory, "maneuver": maneuver_trajectory}
    if name not in table:
        raise ValueError(f"unknown trajectory {name!r}; choose default, gentle or maneuver")
    return table[name]


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    profile: FaultProfile
    trajectory_name: str = "default"

    @property
    def trajectory(self):
        return trajectory_by_name(self.trajectory_name)

    @property
    def window(self):
        """(start, end) of the finite disturbance (same rule as the benchmark) or None."""
        evs = [e for e in self.profile.events if math.isfinite(e.end)]
        return (min(e.start for e in evs), max(e.end for e in evs)) if evs else None


def event_from_dict(d: dict) -> FaultEvent:
    unknown = set(d) - set(_EVENT_FIELDS)
    if unknown:
        raise ValueError(f"unknown fault-event keys: {sorted(unknown)}")
    return FaultEvent(**d)            # FaultEvent validates every value


def scenario_from_dict(name: str, d: dict) -> Scenario:
    events = tuple(event_from_dict(e) for e in d.get("events", []))
    return Scenario(name, d.get("description", ""), FaultProfile(name, events, d.get("description", "")),
                    d.get("trajectory", "default"))


def load_scenarios(path=DEFAULT_SCENARIO_FILE) -> Dict[str, Scenario]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {n: scenario_from_dict(n, d) for n, d in data["scenarios"].items()}


def scenario_to_dict(s: Scenario) -> dict:
    evs = []
    for e in s.profile.events:
        d = {"kind": e.kind, "start": e.start, "duration": e.duration, "label": e.label or e.kind}
        if e.kind == "random_loss":
            d["probability"] = e.probability
        elif e.kind == "burst_loss":
            d.update(p_good_to_bad=e.p_good_to_bad, p_bad_to_good=e.p_bad_to_good, loss_in_bad=e.loss_in_bad)
        elif e.kind == "latency":
            d.update(extra_latency_s=e.extra_latency_s, jitter_s=e.jitter_s)
        evs.append(d)
    return {"description": s.description, "trajectory": s.trajectory_name, "events": evs}
