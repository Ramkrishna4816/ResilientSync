"""Runs the REAL rs_coordinator.py main() and the REAL rs_wheel_driver.py against a FAKE Webots `controller` module.

This is NOT Webots: it proves the Python-level logic of the two controllers (API call shapes, message packing,
teleport, logging, quit) is consistent.  Physics, contact, timing and the real API remain unverified until a real
Webots run.
"""
import json
import math
import os
import runpy
import struct
import sys
import types
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "webots_project" / "controllers"
R, TRACK = 0.0975, 0.33


class _Field:
    def __init__(self, node, name): self.node, self.name = node, name
    def setSFVec3f(self, v): self.node.pos = list(v)
    def setSFRotation(self, r): self.node.yaw = float(r[3])


class _Node:
    def __init__(self): self.pos, self.yaw, self.v, self.w = [0.0, 0.0, 0.0975], 0.0, 0.0, 0.0
    def getField(self, name): return _Field(self, name)
    def resetPhysics(self): self.v = self.w = 0.0
    def getPosition(self): return list(self.pos)
    def getOrientation(self):
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        return [c, -s, 0, s, c, 0, 0, 0, 1]
    def getVelocity(self): return [self.v * math.cos(self.yaw), self.v * math.sin(self.yaw), 0, 0, 0, self.w]


class _Emitter:
    def __init__(self): self.packets = []
    def send(self, data):
        assert isinstance(data, (bytes, bytearray))
        self.packets.append(bytes(data))


class FakeSupervisor:
    """Minimal Webots Supervisor: wheel speeds from the last emitted packet drive ideal diff-drive nodes."""
    instance = None

    def __init__(self):
        FakeSupervisor.instance = self
        self.n_robots = int(os.environ["FAKE_N_ROBOTS"])
        self.nodes = {f"RS_{i}": _Node() for i in range(self.n_robots)}
        self.nodes.update({f"SLOT_{i}": _Node() for i in range(1, self.n_robots)})
        self.tx, self.t, self.quit_status, self.basic = _Emitter(), 0.0, None, 10
    def getFromDef(self, name): return self.nodes.get(name)
    def getDevice(self, name):
        assert name == "cmd_tx"; return self.tx
    def getBasicTimeStep(self): return float(self.basic)
    def getTime(self): return self.t
    def simulationQuit(self, status): self.quit_status = status
    def step(self, ms):
        assert ms % self.basic == 0
        if self.tx.packets:
            pk = struct.unpack(f"<d{2 * self.n_robots}d", self.tx.packets[-1])
            for i in range(self.n_robots):
                nd = self.nodes[f"RS_{i}"]
                wl, wr = pk[1 + 2 * i], pk[2 + 2 * i]
                nd.v, nd.w = R * (wl + wr) / 2, R * (wr - wl) / TRACK
                for _ in range(ms // self.basic):
                    nd.pos[0] += nd.v * math.cos(nd.yaw) * 0.01; nd.pos[1] += nd.v * math.sin(nd.yaw) * 0.01; nd.yaw += nd.w * 0.01
        self.t += ms / 1000.0
        return 0


@pytest.fixture
def fake_controller_module():
    mod = types.ModuleType("controller"); mod.Supervisor = FakeSupervisor
    old = sys.modules.get("controller"); sys.modules["controller"] = mod
    yield mod
    sys.modules.pop("controller", None)
    if old is not None: sys.modules["controller"] = old


def _run(tmp_path, n_world, cfg_extra, monkeypatch):
    cfg = {"scenario": "nominal", "arm": "adaptive_supervisor", "seed": 100, "duration_s": 3.0, "out_dir": str(tmp_path / "out"),
           "quit_when_done": True}; cfg.update(cfg_extra)
    p = tmp_path / "cfg.json"; p.write_text(json.dumps(cfg))
    monkeypatch.setenv("RS_RUN_CONFIG", str(p)); monkeypatch.setenv("FAKE_N_ROBOTS", str(n_world))
    runpy.run_path(str(CTRL / "rs_coordinator" / "rs_coordinator.py"), run_name="rs_coordinator_test")
    return FakeSupervisor.instance, tmp_path / "out"


def test_coordinator_runs_a_full_scenario_against_the_fake_supervisor(tmp_path, monkeypatch, fake_controller_module):
    sup, out = _run(tmp_path, 3, {"n_agents": "auto"}, monkeypatch)      # 3-robot world + "auto": the user's situation
    assert sup.quit_status == 0
    run = next(out.iterdir())
    meta = json.loads((run / "meta.json").read_text())
    assert meta["status"] == "completed" and meta["spec"]["plant"] == "webots" and meta["spec"]["n_agents"] == 3
    assert meta["steps_run"] == 60 and meta["basic_time_step_ms"] == 10
    import pandas as pd
    df = pd.read_csv(run / "steps.csv")
    assert {"gt_z_0", "roll_2", "pitch_1"} <= set(df.columns)             # tilt/height logging reaches the CSV
    assert df.gt_x_0.iloc[-1] > df.gt_x_0.iloc[0] + 1.0                    # leader moved via emitted wheel speeds
    assert np.allclose(np.diff(df.t), 0.05, atol=1e-9)
    assert abs((df.t_plant - df.t).max() - (df.t_plant - df.t).min()) < 1e-6   # engine and plant clocks stay locked
    assert len(sup.tx.packets) >= 60                                       # one actuation packet per tick (+ the placement tick)
    assert not (run / "coordinator_error.txt").exists()
    assert sup.nodes["SLOT_1"].pos != [0.0, 0.0, 0.0975]                  # target-slot markers were updated


def test_coordinator_teleports_to_engine_initial_poses_then_moves(tmp_path, monkeypatch, fake_controller_module):
    sup, out = _run(tmp_path, 3, {"n_agents": 3}, monkeypatch)
    import pandas as pd
    df = pd.read_csv(next(out.iterdir()) / "steps.csv")
    assert abs(df.gt_x_1.iloc[0] - (-1.25)) < 0.6 and abs(df.gt_z_1.iloc[0] - 0.0975) < 1e-9


def test_world_config_mismatch_is_reported_not_swallowed(tmp_path, monkeypatch, fake_controller_module):
    sup, out = _run(tmp_path, 3, {"n_agents": 5}, monkeypatch)            # 3-robot world, config says 5
    assert sup.quit_status is None                                         # Webots left open for the user
    err = ROOT / "results" / "webots" / "_startup_error.txt"
    assert err.exists() and "loaded world has 3 robots" in err.read_text()
    err.unlink()
    assert not out.exists()


def test_wheel_driver_applies_the_right_wheel_speeds(monkeypatch):
    sent = {}
    class Motor:
        def __init__(self, n): self.n = n
        def setPosition(self, p): assert p == float("inf")
        def setVelocity(self, v): sent[self.n] = v
    class Rx:
        def __init__(self): self.q = [struct.pack("<d6d", 0.0, 1, 2, 3, -4, 5, 99.0)]
        def enable(self, ts): pass
        def getQueueLength(self): return len(self.q)
        def getBytes(self): return self.q[0]
        def nextPacket(self): self.q.pop(0)
    class Robot:
        def __init__(self): self.k = 0; self.rx = Rx(); self.m = {"left wheel motor": Motor("l"), "right wheel motor": Motor("r")}
        def getBasicTimeStep(self): return 10.0
        def getDevice(self, n): return self.rx if n == "cmd_rx" else self.m[n]
        def getTime(self): return self.k * 0.01
        def step(self, ts):
            self.k += 1; return 0 if self.k < 3 else -1
    mod = types.ModuleType("controller"); mod.Robot = Robot; monkeypatch.setitem(sys.modules, "controller", mod)
    monkeypatch.setattr(sys, "argv", ["rs_wheel_driver.py", "2", "3"])        # robot index 2 of 3
    runpy.run_path(str(CTRL / "rs_wheel_driver" / "rs_wheel_driver.py"), run_name="drv")
    assert sent["l"] == 5.0            # robot 2 of 3 reads its own pair (5, 99) from the packet
    assert sent["r"] == 20.0           # 99 rad/s is clipped to the 20 rad/s motor limit
