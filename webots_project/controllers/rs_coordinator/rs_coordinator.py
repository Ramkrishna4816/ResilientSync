"""rs_coordinator -- Webots Supervisor controller running the ResilientSync engine.

Reads ground-truth poses of all robots, hands them to resilientsync_webots.WebotsAdapter
(-> the ORIGINAL controllers / supervisor / faulted network), and sends the resulting wheel
speeds to the per-robot rs_wheel_driver controllers.  The closed loop is
resilientsync_webots.runner.run_closed_loop, shared with the stand-in plant.

Run configuration: JSON file named by env RS_RUN_CONFIG, else
webots_project/config/run_config.json.   STATUS: not yet executed in Webots.
"""
import json
import os
import struct
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]          # <repo>/webots_project/controllers/rs_coordinator/<this file>
sys.path.insert(0, str(ROOT))

from controller import Supervisor                    # noqa: E402  (provided by Webots)

try:
    import numpy as np                                   # noqa: E402
    from experiments.run_benchmark import ARMS           # noqa: E402
    from resilientsync_webots.faults import load_scenarios              # noqa: E402
    from resilientsync_webots.frames import FrameMap, measured_state, rotation_from_yaw, tilt_from_rotation_matrix   # noqa: E402
    from resilientsync_webots.robot_params import CONTROL_PERIOD_MS    # noqa: E402
    from resilientsync_webots.runconfig import load_run_config          # noqa: E402
    from resilientsync_webots.runner import RunSpec, run_closed_loop    # noqa: E402
except Exception as _exc:                                # explain it in the Webots console and on disk
    from resilientsync_webots.bootstrap_hint import explain_import_failure   # stdlib only
    _msg = explain_import_failure(_exc, ROOT)
    print(_msg, file=sys.stderr, flush=True)
    try:
        (ROOT / "results" / "webots").mkdir(parents=True, exist_ok=True)
        (ROOT / "results" / "webots" / "_startup_error.txt").write_text(_msg + "\n\n" + traceback.format_exc())
    except OSError:
        pass
    raise SystemExit(1)


class WebotsPlant:
    def __init__(self, sup, n, frame, teleport=True):
        self.sup, self.n, self.fm, self.teleport = sup, n, frame, teleport
        self.nodes = [sup.getFromDef(f"RS_{i}") for i in range(n)]
        if any(x is None for x in self.nodes):
            raise RuntimeError(f"world must define DEF RS_0..RS_{n-1} (is the world's robot count {n}?)")
        self.slots = [sup.getFromDef(f"SLOT_{i}") for i in range(1, n)]
        self.tx = sup.getDevice("cmd_tx")
        self.ts = CONTROL_PERIOD_MS
        self.t0 = 0.0
        self._pose = [None] * n

    def place(self, states_rs):
        if self.teleport:
            for node, s in zip(self.nodes, states_rs):
                node.getField("translation").setSFVec3f(self.fm.world_translation(s[:2]))
                node.getField("rotation").setSFRotation(rotation_from_yaw(self.fm.rs_to_world_yaw(s[2])))
                node.resetPhysics()
        # settle one control period with zero wheel commands so getPosition() reflects the teleport;
        # plant.time() is measured from here so engine time and plant time start together at 0.
        self.apply(np.zeros((self.n, 2)))
        if self.sup.step(self.ts) == -1:
            raise RuntimeError("Webots stopped during placement")
        self.t0 = self.sup.getTime()

    def time(self):
        return self.sup.getTime() - self.t0

    def measure(self):
        out = []
        self._pose = []
        for nd in self.nodes:
            pos, rot, vel = nd.getPosition(), nd.getOrientation(), nd.getVelocity()
            self._pose.append((pos, rot))
            out.append(measured_state(pos, rot, vel, self.fm))
        return np.array(out)

    def extras(self):
        """Webots-only observations of the SAME tick: height and tilt (detects tipping / sinking)."""
        d = {}
        for i, (pos, rot) in enumerate(self._pose):
            roll, pitch = tilt_from_rotation_matrix(rot)
            d.update({f"gt_z_{i}": pos[2], f"roll_{i}": roll, f"pitch_{i}": pitch})
        return d

    def apply(self, wheels):
        flat = [float(x) for x in np.asarray(wheels, float).ravel()]
        self.tx.send(struct.pack(f"<d{len(flat)}d", self.sup.getTime(), *flat))

    def advance(self):
        if self.sup.step(self.ts) == -1:
            raise RuntimeError("Webots stopped before the scenario finished")

    def update_slot_markers(self, out, adapter):
        for i, node in enumerate(self.slots, start=1):
            if node is not None:
                xy = self.fm.rs_to_world_xy([out.row[f"slot_x_{i}"], out.row[f"slot_y_{i}"]])
                node.getField("translation").setSFVec3f([float(xy[0]), float(xy[1]), 0.01])


def main():
    cfg_path = Path(os.environ.get("RS_RUN_CONFIG", ROOT / "webots_project" / "config" / "run_config.json"))
    sup = Supervisor()
    status = 1
    print(f"[rs_coordinator] python {sys.version.split()[0]}  config {cfg_path}", flush=True)
    try:
        scenarios = load_scenarios()
        n_world = 0
        while sup.getFromDef(f"RS_{n_world}") is not None:           # robots actually present in the loaded world
            n_world += 1
        cfg = load_run_config(cfg_path, ROOT, scenarios, ARMS, n_world=n_world)   # relative out_dir -> <project root>/...
        sc, arm = scenarios[cfg["scenario"]], ARMS[cfg["arm"]]
        spec = RunSpec(cfg["scenario"], cfg["arm"], cfg["seed"], cfg["duration_s"], cfg["n_agents"], plant="webots")
        out_dir = Path(cfg["out_dir"]) / spec.run_id
    except Exception as exc:                                          # bad config / world mismatch: say so, persistently
        msg = f"[rs_coordinator] CONFIGURATION ERROR: {type(exc).__name__}: {exc}\n  config file: {cfg_path}"
        print(msg, file=sys.stderr, flush=True)
        try:
            (ROOT / "results" / "webots").mkdir(parents=True, exist_ok=True)
            (ROOT / "results" / "webots" / "_startup_error.txt").write_text(msg + "\n\n" + traceback.format_exc())
        except OSError:
            pass
        return                                                        # keep Webots open so the console stays readable
    print(f"[rs_coordinator] run {spec.run_id}; logs -> {out_dir}", flush=True)
    try:
        fm = FrameMap(*cfg.get("frame", [0.0, 0.0, 0.0]))
        plant = WebotsPlant(sup, spec.n_agents, fm, bool(cfg.get("teleport_initial", True)))
        meta = run_closed_loop(spec, sc, arm, plant, out_dir,
                               {"webots_version": os.environ.get("RS_WEBOTS_VERSION", "unknown"),
                                "basic_time_step_ms": int(sup.getBasicTimeStep()),
                                "world": sup.getWorldPath() if hasattr(sup, "getWorldPath") else "unknown"},
                               on_step=plant.update_slot_markers)
        print(f"[rs_coordinator] {spec.run_id}: {meta['status']} ({meta['steps_run']} steps)")
        status = 0 if meta["status"] == "completed" else 2
    except Exception:
        traceback.print_exc()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "coordinator_error.txt").write_text(traceback.format_exc())
    if cfg.get("quit_when_done", True):
        sup.simulationQuit(status)


main()
