"""WebotsAdapter -- runs the ORIGINAL ResilientSync engine with an external plant.

Per control tick:
    measured poses (RS frame) --> engine.set_measured_states
                              --> engine.step()   (controllers, supervisor, network + faults)
                              --> (v, omega) per robot --> wheel speeds
No control law is re-implemented here.  The engine's FollowerController / ResilienceSupervisor /
Network are used as-is; the adapter only (a) feeds measured poses, (b) converts commands,
(c) records what happened.

What the controllers actually see (see docs/WEBOTS_VALIDATION.md section 3):
  * leader state: ONLY through the faulted network (dead-reckoned from the last delivered packet)
  * own pose / velocity: measured ground truth from the plant (idealised, no onboard-sensor model)
    plus the engine's own Gaussian error noise (cfg.sensor_sigma)
  * neighbour poses (neighbour coupling, avoidance, yield): measured ground truth, global
    (an engine limitation, HANDOFF known-limitation 5)
Evaluation columns (`true_slot_err_*`, `formation_rms`, `min_sep`) are computed from ground truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from simulation.config import Config
from simulation.formation import formation_errors
from simulation.kinematics import body_to_world
from simulation.messages import HEARTBEAT, POSE_UPDATE
from simulation.network import dead_reckon
from simulation.simulation import MultiAgentSimulation
from simulation.supervisor import STATE_NAMES

from .diffdrive import cmd_to_wheels
from .faults import Scenario


class _EventSink:
    """Receives every network outcome of every tick (the engine calls log_tick)."""

    def __init__(self):
        self.rows: List[dict] = []

    def log_tick(self, now, agents, events):
        for e in events:
            self.rows.append({
                "t_sent": round(float(e.time), 6), "type": e.msg_type, "sender": e.sender,
                "receiver": e.receiver, "seq": e.sequence, "status": e.status,
                "latency_s": round(float(e.latency), 6),
                "t_arrival": "" if e.status == "LOST" else round(float(e.time + e.latency), 6)})


class _AdapterSim(MultiAgentSimulation):
    """Engine subclass that only OBSERVES deliveries (behaviour is unchanged)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.delivery_rows: List[dict] = []

    def _deliver(self, msg, now, dt):
        if msg.msg_type == POSE_UPDATE and msg.receiver != 0:
            a = self.agents[msg.receiver]
            self.delivery_rows.append({
                "t_delivered": round(float(now), 6), "receiver": msg.receiver, "seq": msg.sequence,
                "pose_seq": int(msg.payload.get("pose_seq", -1)),
                "t_sample": round(float(msg.timestamp), 6),
                "age_at_delivery_s": round(float(now - msg.timestamp), 6),
                "accepted": bool(msg.sequence > a.rx_seq)})
        super()._deliver(msg, now, dt)


@dataclass
class StepOutput:
    commands: np.ndarray         # (n, 2) v, omega  (engine output)
    wheels: np.ndarray           # (n, 2) left, right [rad/s] after saturation
    saturated: np.ndarray        # (n,) bool
    row: dict                    # one flat CSV row
    halted: bool = False


class WebotsAdapter:
    def __init__(self, scenario: Scenario, arm, seed: int = 42, n_agents: int = 5,
                 cfg: Optional[Config] = None):
        self.scenario, self.arm, self.seed, self.n = scenario, arm, int(seed), int(n_agents)
        cfg = cfg or arm.build_cfg()
        cfg = cfg.copy(n_agents=self.n)
        self.cfg = cfg
        self.sim = _AdapterSim(cfg, control_mode=arm.mode, seed=self.seed,
                               leader_trajectory=scenario.trajectory,
                               fault_profile=scenario.profile, record_history=True)
        self.sim.external_plant = True
        self.sink = _EventSink()
        self.sim.attach_logger(self.sink)
        self.dt = cfg.dt
        self.max_skew = 0.0
        self._cum = {f.id: {"sent": 0, "lost": 0} for f in self.sim.followers}

    # ------------------------------------------------------------------
    def initial_states(self) -> np.ndarray:
        """Engine's seeded initial conditions (n,5), RS frame -> used to place the robots."""
        return self.sim._S.copy()

    def step(self, t: float, measured_rs: np.ndarray, wheel_fn=cmd_to_wheels) -> StepOutput:
        sim = self.sim
        self.max_skew = max(self.max_skew, abs(t - sim.t))
        now = sim.t
        sim.set_measured_states(measured_rs)
        ok = sim.step()
        n = self.n
        cmds = np.zeros((n, 2))
        for i in range(n):
            cmds[i] = sim.cmd_out.get(i, (0.0, 0.0))
        wheels = np.zeros((n, 2))
        sat = np.zeros(n, bool)
        for i in range(n):
            wc = wheel_fn(*cmds[i])
            wheels[i], sat[i] = (wc.left, wc.right), wc.saturated
        return StepOutput(cmds, wheels, sat, self._row(now, t, measured_rs, cmds, wheels, sat), halted=not ok)

    # ------------------------------------------------------------------
    def _row(self, now, t_plant, S, cmds, wheels, sat) -> dict:
        sim, n = self.sim, self.n
        lt = sim.last_tick or {}
        r = {"t": round(now, 6), "t_plant": round(float(t_plant), 6), "step": sim.step_count,
             "fault_active": int(bool(sim.network.active_faults() or sim.network.forced_loss_all)),
             "blackout_active": int(sim.network._blackout_active),
             "formation_rms": float(lt.get("formation_rms", np.nan)),
             "min_sep": float(lt.get("min_distance", np.nan))}
        true_err = formation_errors(S, sim.formation)
        for i in range(n):
            r.update({f"gt_x_{i}": S[i, 0], f"gt_y_{i}": S[i, 1], f"gt_th_{i}": S[i, 2],
                      f"gt_v_{i}": S[i, 3], f"gt_w_{i}": S[i, 4],
                      f"cmd_v_{i}": cmds[i, 0], f"cmd_w_{i}": cmds[i, 1],
                      f"wheel_l_{i}": wheels[i, 0], f"wheel_r_{i}": wheels[i, 1],
                      f"sat_{i}": int(sat[i])})
        for a in sim.followers:
            i = a.id
            age = max(0.0, now - a.rx_time)
            win = a.pose_delivery_window
            est = dead_reckon(a.last_rx, age, self.arm.mode != "zoh", self.cfg.dr_lambda)
            st = sim.network._stats.get((0, i))
            sent = st.sent if st else 0
            lost = st.lost if st else 0
            r.update({
                f"true_slot_err_{i}": float(true_err[i - 1]),
                f"slot_x_{i}": float(lt["targets"][i][0]) if lt else np.nan,
                f"slot_y_{i}": float(lt["targets"][i][1]) if lt else np.nan,
                f"age_{i}": age,
                f"quality_{i}": float(lt["communication_quality"][i]) if lt else np.nan,
                f"loss_est_{i}": (sum(win) / len(win)) if len(win) else 0.0,
                f"sup_state_{i}": int(lt["supervisor_state"][i]) if lt else 0,
                f"caution_{i}": float(lt["caution"][i]) if lt else 0.0,
                f"rx_seq_{i}": a.rx_seq, f"pose_seq_rx_{i}": a.last_pose_sample_seq,
                f"sent_{i}": sent, f"lost_{i}": lost,
                f"leader_est_err_{i}": float(np.hypot(*(est[:2] - S[0, :2])))})
        return r

    # ------------------------------------------------------------------
    @property
    def supervisor_active(self) -> bool:
        return self.arm.mode == "adaptive_comm" and self.cfg.supervisor_enabled

    def transitions(self) -> list:
        out = []
        if self.supervisor_active:
            for fid, sup in self.sim.supervisors.items():
                for tr in sup.transitions:
                    out.append(dict(tr.as_dict(), follower=fid))
        return sorted(out, key=lambda r: r["t"])

    def state_names(self):
        return STATE_NAMES
