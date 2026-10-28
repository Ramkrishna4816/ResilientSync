"""
simulation.py -- the reusable multi-agent simulation engine.

    sim = MultiAgentSimulation()
    sim.submit_command("GOTO 10 5")      # operator layer
    sim.step()                           # advance one tick (dt = cfg.dt)
    sim.get_state()                      # JSON-friendly snapshot for any UI

The SAME engine is used by Jupyter/Matplotlib, the FastAPI dashboard and
(later) a Webots controller.  It imports no UI code.  Only two things are
Matplotlib/Webots-specific and replaceable: the plant (`kinematics.rk4_step`)
and the view.

One tick (`step`)
-----------------
  1. keyboard one-shots + command state machine (GOTO arrival, REGROUP done ...)
  2. leader command  (AUTO trajectory | keyboard | GOTO | idle) -> boundary
     guard -> RK4 plant
  3. network: leader broadcasts POSE_UPDATE, un-ACKed commands are retried,
     follower heartbeats are sent, due packets are delivered and applied
  4. every follower: dead-reckon the leader, pick the control law for its
     mode, avoidance + boundary guard -> RK4 plant (sequential update, like
     the notebook)
  5. safety checks (NaN/Inf, hard clamp), metrics, link health, logging
"""
from __future__ import annotations

from collections import deque
from typing import Callable, Deque, Dict, List, Optional

import numpy as np

from .agent import Agent, AgentMode, LinkStatus, make_agents
from .connectivity import (ConnectivityTracker, ConsensusTolerance,
                           directed_adjacency, edge_disagreement, evaluate_topology,
                           heading_disagreement, speed_disagreement)
from .collision import (avoidance_vector, boundary_guard_command,
                        clamp_state_to_world, min_separation, yield_speed_factor)
from .commands import CommandManager, CommandResult, MissionState, SimMode
from .config import T_FINAL, Config
from .controller import (FollowerController, auto_leader_command, estimate_communication_quality,
                          go_to_point, steer_around)
from .formation import fit_shift, formation_rms, make_formation
from .kinematics import body_to_world, is_valid_state, rk4_step
from .keyboard import KeyboardController
from .messages import (ACK, COMMAND, FOLLOW, HEARTBEAT, POSE_UPDATE, REGROUP,
                       SCATTER, STOP, TASK_ASSIGN, CommEvent, Message,
                       MessageBus, STATUS_LOST)
from .network import Network, dead_reckon
from .supervisor import STATE_NAMES as STATE_CODES_NAMES, STATE_CODES, ResilienceSupervisor, SupervisorState
from .tasks import TaskManager

CONTROL_MODES = ("zoh", "pidr", "advanced", "adaptive_comm")
_DRIVE_KEYS = ("W", "A", "S", "D")


class MultiAgentSimulation:
    def __init__(self, cfg: Config | None = None, n_agents: int | None = None,
                 control_mode: str = "advanced", seed: int = 42,
                 loss_scale: float = 1.0, sensor_sigma: float | None = None,
                 sim_mode: SimMode = SimMode.AUTO,
                 leader_trajectory: Callable[[float], np.ndarray] | None = None,
                 formation: str = "WEDGE", record_history: bool = False,
                 logger=None, fault_profile=None, supervisor_cfg=None):
        if control_mode not in CONTROL_MODES:
            raise ValueError(f"control_mode must be one of {CONTROL_MODES}")
        cfg = cfg or Config()
        if supervisor_cfg is not None:
            cfg = cfg.copy(supervisor=supervisor_cfg)
        if n_agents is not None and n_agents != cfg.n_agents:
            cfg = cfg.copy(n_agents=n_agents)
        if cfg.n_agents < 2:
            raise ValueError("need at least one follower")

        self.cfg = cfg
        self.n = cfg.n_agents
        self.dt = cfg.dt
        self.control_mode = control_mode
        self.sensor_sigma = sensor_sigma
        self.leader_trajectory = leader_trajectory or auto_leader_command
        self.rng = np.random.default_rng(seed)

        # --- formation + agents ------------------------------------------
        self.formation_name = formation
        self.formation = make_formation(self.n, formation)
        self.agents: List[Agent] = make_agents(self.n, self.formation, self.rng)
        # canonical state store; each agent.state is a live view of one row
        self._S = np.array([a.state for a in self.agents])
        for i, a in enumerate(self.agents):
            a.state = self._S[i]

        # --- subsystems --------------------------------------------------
        self.bus = MessageBus(cfg.comm_log_size)
        self.network = Network(cfg, self.bus, seed, loss_scale)
        self.network.set_fault_profile(fault_profile)
        self.commands = CommandManager(cfg)
        self.tasks = TaskManager(cfg)
        self.keyboard = KeyboardController(cfg)
        self.controllers: Dict[int, FollowerController] = {
            a.id: FollowerController(cfg) for a in self.followers}
        self._ctrl_mode: Dict[int, AgentMode] = {a.id: a.mode for a in self.followers}
        # one resilience supervisor per follower (used by adaptive_comm only)
        self.supervisors: Dict[int, ResilienceSupervisor] = {
            a.id: ResilienceSupervisor(cfg.supervisor, name=a.name) for a in self.followers}
        self._sup_active: Dict[int, bool] = {a.id: False for a in self.followers}

        # --- runtime state -----------------------------------------------
        self.t = 0.0
        self.step_count = 0
        self.halted = False
        self.fault: Optional[str] = None
        self.sim_mode = sim_mode
        self.leader_view: Dict[int, dict] = {}       # last heartbeat per follower
        self.pending: Dict[int, dict] = {}           # un-ACKed reliable commands
        self._cmd_counter = 0
        self._stop_snapshot: Optional[dict] = None
        self.clamp_count = np.zeros(self.n, int)
        self.status_log: Deque[dict] = deque(maxlen=cfg.status_log_size)
        self.tick_events: List[CommEvent] = []
        self.last_tick: dict = {}
        self.logger = logger
        self._record = record_history
        self._hist: List[dict] = []
        # lightweight rolling trace for live observability (always on)
        self.trace: Deque[tuple] = deque(maxlen=1200)
        # global connectivity / consensus diagnostics (never fed to controllers)
        self.conn_tracker = ConnectivityTracker(self.n)
        self.connectivity: dict = {}
        self.consensus_tol = ConsensusTolerance()
        self.closest_approach: dict = {"distance": None, "t": None, "pair": None,
                                       "midpoint": None}

        # --- external plant hook (Webots adapter) ----------------------------
        # False (default): the engine integrates its own RK4 plant (unchanged).
        # True: poses are supplied by a real plant through `set_measured_states`;
        # the engine only computes commands, which it stores in `cmd_out`.
        self.external_plant = False
        self.cmd_out: Dict[int, tuple] = {}

        self.leader.mode = self._driving_mode()

    # ==================================================================
    # Convenience accessors
    # ==================================================================
    @property
    def leader(self) -> Agent:
        return self.agents[0]

    @property
    def followers(self) -> List[Agent]:
        return self.agents[1:]

    def states(self) -> np.ndarray:
        """(n, 5) live state array (read-only by convention)."""
        return self._S

    # ---- external plant (Webots) ------------------------------------------
    def set_measured_states(self, states) -> None:
        """Overwrite the canonical state array with poses measured on a real plant.

        `states` is (n, 5): x, y, theta, v, omega in the engine frame.  Writes
        in place, so every `Agent.state` view stays valid.  Only meaningful with
        `external_plant = True`.
        """
        arr = np.asarray(states, float)
        if arr.shape != self._S.shape:
            raise ValueError(f"states must have shape {self._S.shape}, got {arr.shape}")
        self._S[:] = arr

    def _advance_plant(self, i: int, v: float, w: float, dt: float) -> None:
        """Command -> motion for agent i.  The ONLY place the plant is integrated."""
        self.cmd_out[i] = (float(v), float(w))
        if self.external_plant:
            return                                  # the real plant moves the robot
        self._S[i] = rk4_step(self._S[i], [v, w], dt, self.cfg.tau_motor)

    def attach_logger(self, logger) -> None:
        self.logger = logger

    def log_status(self, text: str) -> None:
        self.status_log.append({"t": round(self.t, 2), "text": text})

    # ==================================================================
    # Operator API (used by UIs)
    # ==================================================================
    def submit_command(self, text: str) -> CommandResult:
        """Execute a text command (GOTO 10 5, SCATTER, ...)."""
        if self.halted:
            return CommandResult(False, f"SIMULATION HALTED: {self.fault}", text)
        return self.commands.execute(text, self)

    def set_sim_mode(self, mode: SimMode) -> None:
        """AUTO / MANUAL / COMMAND: how the leader is driven."""
        self.sim_mode = SimMode(mode)
        if self.leader.mode == AgentMode.GOTO:        # switching mode cancels GOTO
            self.leader.target = None
        if self.leader.mode != AgentMode.STOPPED:
            self.leader.mode = self._driving_mode()
        self.keyboard.reset()

    def handle_key(self, key: str, down: bool = True) -> Optional[str]:
        """Keyboard entry point (Matplotlib, browser, CLI all call this)."""
        k = self.keyboard.normalize(key)
        if k in _DRIVE_KEYS and down:
            if self.commands.state == MissionState.STOPPED:
                self.commands.override_stop(self)      # driving overrides STOP
            if self.sim_mode != SimMode.MANUAL:
                self.set_sim_mode(SimMode.MANUAL)
                self.log_status("MODE MANUAL (keyboard)")
        return self.keyboard.set_key(key, down)

    def _process_keyboard_events(self) -> None:
        for text in self.keyboard.consume_events():
            self.commands.execute(text, self)

    # ---- hooks used by CommandManager ------------------------------------
    def _driving_mode(self) -> AgentMode:
        return {SimMode.AUTO: AgentMode.AUTO, SimMode.MANUAL: AgentMode.MANUAL,
                SimMode.COMMAND: AgentMode.IDLE}[self.sim_mode]

    def leader_goto(self, xy: np.ndarray) -> None:
        self.sim_mode = SimMode.COMMAND
        self.keyboard.reset()
        self.leader.target = np.array(xy, float)
        self.leader.mode = AgentMode.GOTO

    def leader_reached_goal(self) -> bool:
        a = self.leader
        return (a.target is not None
                and np.hypot(*(a.xy - a.target)) < self.cfg.goto_tolerance
                and abs(a.v) < 0.08)

    def finish_leader_goto(self) -> None:
        self.leader.target = None
        self.leader.mode = self._driving_mode()

    def stop_leader(self) -> None:
        a = self.leader
        self._stop_snapshot = {
            "mode": a.mode,
            "target": None if a.target is None else a.target.copy()}
        a.mode = AgentMode.STOPPED
        self.keyboard.reset()

    def resume_leader(self) -> None:
        a, snap = self.leader, self._stop_snapshot
        self._stop_snapshot = None
        if snap and snap["mode"] == AgentMode.GOTO and snap["target"] is not None:
            a.target, a.mode = snap["target"], AgentMode.GOTO
        else:
            a.mode = self._driving_mode()

    def clear_stop(self) -> None:
        self._stop_snapshot = None
        if self.leader.mode == AgentMode.STOPPED:
            self.leader.mode = self._driving_mode()

    def set_formation(self, name: str) -> None:
        self.formation = make_formation(self.n, name)
        self.formation_name = name.upper()

    def status_text(self) -> str:
        net = self.network.snapshot()
        lines = [f"t={self.t:.1f}s  MODE={self.sim_mode.value}  "
                 f"MISSION={self.commands.state.value}  FORMATION={self.formation_name}"]
        for a in self.agents:
            tk = f" task={a.task_id}" if a.task_id else ""
            lines.append(f"{a.name}: {a.mode.value} ({a.x:.1f},{a.y:.1f}) "
                         f"v={a.v:.2f} link={a.link.value}{tk}")
        lines.append(f"Network: loss {net['loss_rate']:.1f}%  "
                     f"avg latency {1000 * net['avg_latency']:.0f} ms")
        return "\n".join(lines)

    # ==================================================================
    # Messaging
    # ==================================================================
    def _transmit(self, msg: Message, dt: float | None = None) -> CommEvent:
        ev = self.network.transmit(msg, self.t, dt)
        self.tick_events.append(ev)
        return ev

    def send_command(self, receiver: int, msg_type: str,
                     payload: dict | None = None, reliable: bool = True) -> Message:
        """Leader -> follower command.

        reliable=True : carries a command id, is re-sent every
                        `cmd_retry_period` until the follower ACKs it (the
                        newest command to a follower supersedes older ones).
        reliable=False: informational one-shot (no state change on receipt).
        """
        payload = dict(payload or {})
        if reliable:
            self._cmd_counter += 1
            payload["cmd_id"] = self._cmd_counter
        msg = self.bus.create(0, receiver, msg_type, payload, self.t)
        self._transmit(msg)
        if reliable:
            self.pending[receiver] = {
                "type": msg_type, "payload": payload, "last": self.t,
                "attempts": 1, "cmd_id": payload["cmd_id"]}
        return msg

    def _broadcast_pose(self, now: float, dt: float, tick: dict) -> None:
        for q, f in enumerate(self.followers):
            msg = self.bus.create(0, f.id, POSE_UPDATE,
                                  {"state": self._S[0].copy(),
                                   "pose_seq": self.step_count + 1}, now)
            ev = self._transmit(msg, dt)
            tick["dropped"][q] = (ev.status == STATUS_LOST)

    def _retry_pending(self, now: float, dt: float) -> None:
        cfg = self.cfg
        for rid, p in list(self.pending.items()):
            if now - p["last"] < cfg.cmd_retry_period - 1e-9:
                continue
            if p["attempts"] >= cfg.cmd_max_attempts:
                del self.pending[rid]
                self.log_status(f"{p['type']} to {self.agents[rid].name} FAILED (no ACK)")
                continue
            msg = self.bus.create(0, rid, p["type"], p["payload"], now)
            self._transmit(msg, dt)
            p["last"] = now
            p["attempts"] += 1

    def _send_heartbeats(self, now: float, dt: float) -> None:
        for a in self.followers:
            if now + 1e-9 >= a.next_heartbeat:
                a.next_heartbeat = now + self.cfg.heartbeat_period
                payload = {"mode": a.mode.value, "task_id": a.task_id,
                           "task_done": a.task_done,
                           "x": float(a.x), "y": float(a.y)}
                self._transmit(self.bus.create(a.id, 0, HEARTBEAT, payload, now), dt)

    # ---- delivery ----------------------------------------------------------
    def _deliver(self, msg: Message, now: float, dt: float) -> None:
        if msg.receiver == 0:
            self._leader_receive(msg, now)
            return
        a = self.agents[msg.receiver]
        t = msg.msg_type
        if t == POSE_UPDATE:
            if msg.sequence > a.rx_seq:                 # ignore stale / reordered
                sample_seq = int(msg.payload.get("pose_seq", a.last_pose_sample_seq + 1))
                if sample_seq > a.last_pose_sample_seq:
                    missed = max(0, sample_seq - a.last_pose_sample_seq - 1)
                    window = a.pose_delivery_window
                    maxlen = window.maxlen or 40
                    for _ in range(min(missed, maxlen)):
                        window.append(True)
                    window.append(False)
                    a.last_pose_sample_seq = sample_seq
                a.rx_seq = msg.sequence
                a.last_rx = np.array(msg.payload["state"], float)
                a.rx_time = msg.timestamp
            return
        cid = msg.payload.get("cmd_id")
        if cid is None:                                 # informational only
            return
        if cid > a.last_cmd_id:                         # new command: apply once
            a.last_cmd_id = cid
            self._apply_to_follower(a, msg)
        ack = self.bus.create(a.id, 0, ACK, {"cmd_id": cid}, now)
        self._transmit(ack, dt)                         # always ACK (also duplicates)

    def _leader_receive(self, msg: Message, now: float) -> None:
        f, p = msg.sender, msg.payload
        if msg.msg_type == ACK:
            pend = self.pending.get(f)
            if pend and pend["cmd_id"] == p.get("cmd_id"):
                del self.pending[f]
        elif msg.msg_type == HEARTBEAT:
            self.leader_view[f] = dict(p, rx=now)
            tid = p.get("task_id")
            if tid:
                self.tasks.mark_in_progress(tid)
                if p.get("task_done") and self.tasks.complete(tid, now):
                    self.log_status(f"TASK {tid} COMPLETE (Agent {f})")

    def _set_follower(self, a: Agent, mode: AgentMode, target=None,
                      task_id=None) -> None:
        a.set_mode(mode)
        a.target = None if target is None else np.array(target, float)
        a.task_id = task_id
        a.task_done = False
        a.saved = None

    def _apply_to_follower(self, a: Agent, msg: Message) -> None:
        """Follower-side effect of a DELIVERED command message."""
        t, p = msg.msg_type, msg.payload
        if t in (FOLLOW, REGROUP):
            if "ox" in p:
                a.offset = np.array([p["ox"], p["oy"]], float)
            self._set_follower(a, AgentMode.FOLLOW if t == FOLLOW else AgentMode.REGROUP)
        elif t == SCATTER:
            self._set_follower(a, AgentMode.SCATTER, (p["x"], p["y"]))
        elif t == TASK_ASSIGN:
            self._set_follower(a, AgentMode.TASK, (p["x"], p["y"]), p["task_id"])
        elif t == STOP:
            if a.mode != AgentMode.STOPPED:
                a.saved = {"mode": a.mode,
                           "target": None if a.target is None else a.target.copy(),
                           "task_id": a.task_id, "task_done": a.task_done}
                a.set_mode(AgentMode.STOPPED)
        elif t == COMMAND:
            kind = p.get("kind")
            if kind == "GOTO" and p.get("apply"):
                self._set_follower(a, AgentMode.GOTO, (p["x"], p["y"]))
            elif kind == "RESUME" and a.mode == AgentMode.STOPPED:
                s, a.saved = a.saved, None
                if s:
                    a.set_mode(s["mode"])
                    a.target, a.task_id, a.task_done = s["target"], s["task_id"], s["task_done"]
                else:
                    a.set_mode(AgentMode.FOLLOW)

    # ==================================================================
    # Safety
    # ==================================================================
    def _finalize(self, i: int) -> bool:
        """Validate + hard-clamp agent i after integration.  False = fault."""
        s = self._S[i]
        if not is_valid_state(s, self.cfg.max_abs_coord):
            self.halted = True
            self.fault = (f"INVALID STATE (NaN/Inf/out of range) in "
                          f"{self.agents[i].name} at t={self.t:.2f}s")
            self.log_status(self.fault)
            return False
        if self.external_plant:                         # measured pose: never rewrite it
            return True
        s2, clamped = clamp_state_to_world(s, self.cfg)
        if clamped:
            self._S[i] = s2
            self.clamp_count[i] += 1
        return True

    # ==================================================================
    # Control per tick
    # ==================================================================
    def _leader_command(self, now: float, dt: float):
        cfg, a = self.cfg, self.leader
        mode = a.mode
        if mode == AgentMode.AUTO:
            v, w = self.leader_trajectory(now)
        elif mode == AgentMode.MANUAL:
            v, w = self.keyboard.command(dt)
        elif mode == AgentMode.GOTO and a.target is not None:
            aim = a.target
            if self.control_mode in ("advanced", "adaptive_comm"):  # steer around agents in the way
                aim = steer_around(a.xy, a.target, avoidance_vector(0, self._S, cfg), cfg)
            v, w, _d, _arr = go_to_point(a.state, aim, cfg.goto_max_v,
                                         cfg.goto_kv, cfg.goto_kw, cfg.max_w, 0.0)
            if np.hypot(*(a.xy - a.target)) < cfg.goto_tolerance:
                v = w = 0.0                           # arrived (judged on the real target)
        else:
            v = w = 0.0
        v, w = boundary_guard_command(a.state, v, w, cfg,
                                      a.target if mode == AgentMode.GOTO else None)
        if self.control_mode in ("advanced", "adaptive_comm") and not cfg.legacy_compat and v > 0:
            v *= yield_speed_factor(0, self._S, cfg)    # leader yields to agents ahead
        return (float(np.clip(v, -cfg.max_v, cfg.max_v)),
                float(np.clip(w, -cfg.max_w, cfg.max_w)))

    def _diagnostics(self, now: float, tick: dict) -> None:
        """Connectivity graph + consensus metrics from the REAL network/state.

        Global diagnostic only: a follower cannot observe this information.
        """
        cfg = self.cfg
        up = self.network.up_links(self.n, now, cfg.connectivity_downlink_timeout_s,
                                   cfg.connectivity_uplink_timeout_s)
        A_all = directed_adjacency(self.n, up)
        # PRIMARY graph: leader->follower pose links only.  These carry the
        # information the formation controller consumes; uplink heartbeats do
        # not influence tracking, so they are reported separately.
        A_down = directed_adjacency(self.n, [(i, j) for i, j in up if i == 0])
        topo = evaluate_topology(A_down, view="union")
        topo["uplink_down"] = [f.id for f in self.followers if (f.id, 0) not in set(up)]
        topo["bidirectional_isolated"] = evaluate_topology(A_all)["isolated_from_leader"]
        self.conn_tracker.update(now, topo["isolated_from_leader"])
        tick["downlink_up"] = np.array([(0, f.id) in set(up) for f in self.followers])
        ids = [0] + [a.id for a in self.followers
                     if a.mode in (AgentMode.FOLLOW, AgentMode.REGROUP)]
        th, v = self._S[ids, 2], self._S[ids, 3]
        hd, sd = heading_disagreement(th), speed_disagreement(v)
        sub = np.maximum(A_down, A_down.T)[np.ix_(ids, ids)]
        ed = edge_disagreement(th, v, sub)
        topo.update(consensus_agents=ids, heading_rms=hd["rms"], heading_max=hd["max"],
                    speed_std=sd["std"], speed_spread=sd["spread"],
                    edge_heading=ed["heading"], edge_speed=ed["speed"],
                    heading_consensus=bool(hd["rms"] <= self.consensus_tol.heading_rms_rad))
        self.connectivity = topo
        tick["n_isolated"] = len(topo["isolated_from_leader"])
        tick["n_unreached"] = len(topo["unreached_by_leader"])
        tick["n_components"] = topo["n_components"]
        tick["lambda2"] = topo["algebraic_connectivity"]
        tick["heading_rms"], tick["speed_std"] = hd["rms"], sd["std"]
        # closest approach (pair + time) over the whole run
        S = self._S[:, :2]
        d = np.linalg.norm(S[:, None, :] - S[None, :, :], axis=2)
        d[np.diag_indices(self.n)] = np.inf
        k = int(np.argmin(d)); i, j = divmod(k, self.n)
        ca = self.closest_approach
        if ca["distance"] is None or d[i, j] < ca["distance"]:
            self.closest_approach = {"distance": float(d[i, j]), "t": float(now),
                                     "pair": [int(min(i, j)), int(max(i, j))],
                                     "midpoint": [float((S[i, 0] + S[j, 0]) / 2),
                                                  float((S[i, 1] + S[j, 1]) / 2)]}

    def _link_quality(self, a: Agent, now: float):
        """(age, loss_estimate, quality) of follower `a`'s leader link."""
        age = max(0.0, now - a.rx_time)
        win = a.pose_delivery_window
        denom = len(win)
        if self.control_mode == "adaptive_comm" and self.cfg.supervisor_enabled and denom:
            denom = max(denom, min(self.cfg.supervisor_min_loss_window, win.maxlen or denom))
        loss = (sum(win) / denom) if denom else 0.0
        return age, loss, estimate_communication_quality(
            age, loss, self.cfg.adaptive_comm_age_tau)

    def _step_follower(self, a: Agent, now: float, dt: float, sigma: float,
                       advanced: bool, tick: dict) -> bool:
        cfg, i = self.cfg, a.id
        adaptive_comm = self.control_mode == "adaptive_comm"
        ctrl = self.controllers[i]
        if self._ctrl_mode[i] != a.mode:                # fresh PID on mode change
            ctrl.reset()
            self._ctrl_mode[i] = a.mode
        S = self._S
        mode = a.mode
        avoid = avoidance_vector(i, S, cfg) if advanced else np.zeros(2)

        if mode in (AgentMode.FOLLOW, AgentMode.REGROUP):
            est = dead_reckon(a.last_rx, max(0.0, now - a.rx_time),
                              self.control_mode != "zoh", cfg.dr_lambda)
            target = body_to_world(a.offset, est)
            nf = np.zeros(2)
            if advanced:                                # neighbour coupling
                for o in self.followers:
                    if o.id != i and o.mode in (AgentMode.FOLLOW, AgentMode.REGROUP):
                        desired_j = body_to_world(o.offset, est)
                        nf += cfg.k_neighbor * ((target - desired_j) - (S[i, :2] - S[o.id, :2]))
            if cfg.clamp_targets and not cfg.legacy_compat:
                # keep the WHOLE formation inside the world (rigid shift)
                pts = np.array([body_to_world(o.offset, est) for o in self.agents
                                if o.id == 0 or o.mode in (AgentMode.FOLLOW, AgentMode.REGROUP)])
                target = target + fit_shift(pts, cfg)
            age, loss_rate, quality = self._link_quality(a, now)
            decision = None
            if adaptive_comm and cfg.supervisor_enabled:
                decision = self.supervisors[i].update(now, quality, age)
                self._sup_active[i] = True
                tick["supervisor_state"][i] = STATE_CODES[decision.state]
                tick["caution"][i] = decision.caution
            v, w, eff, dist = ctrl.formation_command(
                S[i], target, nf, avoid, est, S[0], advanced, self.rng, sigma, dt,
                communication_quality=quality, adaptive_comm=adaptive_comm,
                supervisor=decision)
            tick["communication_quality"][i] = quality
        elif mode in (AgentMode.SCATTER, AgentMode.TASK, AgentMode.GOTO) \
                and a.target is not None:
            v, w, eff, dist, arrived = ctrl.static_command(S[i], a.target, avoid, advanced)
            if mode == AgentMode.TASK and arrived:
                a.task_done = True                      # reported via heartbeat
        else:                                           # STOPPED / IDLE
            v = w = 0.0
            eff, dist = S[i, :2].copy(), 0.0
        if self._sup_active[i] and mode not in (AgentMode.FOLLOW, AgentMode.REGROUP):
            self.supervisors[i].suspend(
                now, f"Reset: {a.name} left formation-following mode ({mode.value}).")
            self._sup_active[i] = False

        v, w = boundary_guard_command(S[i], v, w, cfg,
                                      None if mode in (AgentMode.STOPPED, AgentMode.IDLE) else eff)
        if advanced and not cfg.legacy_compat and v > 0:
            v *= yield_speed_factor(i, S, cfg)          # do not drive into someone
        v = float(np.clip(v, -cfg.max_v, cfg.max_v))
        w = float(np.clip(w, -cfg.max_w, cfg.max_w))
        self._advance_plant(i, v, w, dt)
        tick["targets"][i] = eff
        tick["errors"][i] = dist
        tick["effort"][i] = abs(v) + .35 * abs(w)
        tick["v_cmd"][i], tick["w_cmd"][i] = v, w
        return self._finalize(i)

    # ==================================================================
    # One simulation tick
    # ==================================================================
    def step(self, dt: float | None = None) -> bool:
        """Advance the simulation by one tick.  Returns False if halted."""
        if self.halted:
            return False
        cfg = self.cfg
        dt = self.dt if dt is None else float(dt)
        if not (np.isfinite(dt) and dt > 0):
            raise ValueError("dt must be a positive finite number")
        now = self.t
        advanced = self.control_mode in ("advanced", "adaptive_comm")
        adaptive_comm = self.control_mode == "adaptive_comm"
        sigma = cfg.sensor_sigma if self.sensor_sigma is None else self.sensor_sigma
        n = self.n
        tick = {"targets": np.zeros((n, 2)), "errors": np.zeros(n),
                "effort": np.zeros(n), "dropped": np.zeros(n - 1, bool),
                "communication_quality": np.ones(n),
                "supervisor_state": np.zeros(n, int), "caution": np.zeros(n),
                "v_cmd": np.zeros(n), "w_cmd": np.zeros(n)}

        # 1. operator layer ------------------------------------------------
        self._process_keyboard_events()
        self.commands.update(self)

        # 2. leader --------------------------------------------------------
        v, w = self._leader_command(now, dt)
        tick["v_cmd"][0], tick["w_cmd"][0] = v, w
        self._advance_plant(0, v, w, dt)
        if not self._finalize(0):
            return False

        # 3. network -------------------------------------------------------
        self.network.update_faults(now)
        self._broadcast_pose(now, dt, tick)
        self._retry_pending(now, dt)
        self._send_heartbeats(now, dt)
        for msg in self.network.poll(now):
            self._deliver(msg, now, dt)

        # 4. followers (sequential, as in the notebook) ---------------------
        for a in self.followers:
            if not self._step_follower(a, now, dt, sigma, advanced, tick):
                return False

        # 5. metrics, link health, logging ---------------------------------
        tick["min_distance"] = min_separation(self._S)
        tick["formation_rms"] = formation_rms(self._S, self.formation)
        for a in self.followers:
            a.link = self.network.link_status(a.id, now)
        self._diagnostics(now, tick)
        self.last_tick = tick
        sev = {0: 0, 1: 1, 3: 2, 2: 3}                    # NORMAL<DEGRADED<RECOVERING<HOLD
        worst = max((sev[int(c)] for c in tick["supervisor_state"][1:]), default=0)
        self.trace.append((round(now, 3), float(tick["formation_rms"]),
                           float(tick["min_distance"]),
                           float(np.mean(tick["communication_quality"][1:])), worst))
        if self._record:
            self._hist.append({
                "t": now, "states": self._S.copy(), "targets": tick["targets"],
                "errors": tick["errors"], "effort": tick["effort"],
                "dropped": tick["dropped"], "min_distance": tick["min_distance"],
                "formation_rms": tick["formation_rms"],
                "age": np.array([max(0.0, now - f.rx_time) for f in self.followers]),
                "communication_quality": tick["communication_quality"].copy(),
                "supervisor_state": tick["supervisor_state"].copy(),
                "caution": tick["caution"].copy(),
                "v_cmd": tick["v_cmd"].copy(), "w_cmd": tick["w_cmd"].copy(),
                "n_isolated": tick["n_isolated"], "n_unreached": tick["n_unreached"],
                "n_components": tick["n_components"], "lambda2": tick["lambda2"],
                "heading_rms": tick["heading_rms"], "speed_std": tick["speed_std"],
                "downlink_up": tick["downlink_up"].copy(),
                "fault_active": bool(self.network.active_faults()
                                     or self.network.forced_loss_all)})
        if self.logger is not None:
            self.logger.log_tick(now, self.agents, self.tick_events)
        self.tick_events = []
        self.t += dt
        self.step_count += 1
        return True

    def run(self, duration: float) -> None:
        """Convenience: step for `duration` seconds (stops early if halted)."""
        for _ in range(int(round(duration / self.dt))):
            if not self.step():
                break

    # ==================================================================
    # Outputs
    # ==================================================================
    def history(self) -> dict:
        """Run history in the notebook's dict format (needs record_history=True)."""
        h = self._hist
        if not h:
            raise RuntimeError("no history recorded (create with record_history=True)")
        out = {
            "t": np.array([r["t"] for r in h]),
            "states": np.array([r["states"] for r in h]),
            "targets": np.array([r["targets"] for r in h]),
            "errors": np.array([r["errors"] for r in h]),
            "formation_rms": np.array([r["formation_rms"] for r in h]),
            "min_distance": np.array([r["min_distance"] for r in h]),
            "control_effort": np.array([r["effort"] for r in h]),
            "packet_drop": np.array([r["dropped"] for r in h]),
            "blackout_age": np.array([r["age"] for r in h]),
            "communication_quality": np.array([r["communication_quality"] for r in h]),
            "supervisor_state": np.array([r["supervisor_state"] for r in h]),
            "caution": np.array([r["caution"] for r in h]),
            "v_cmd": np.array([r["v_cmd"] for r in h]),
            "w_cmd": np.array([r["w_cmd"] for r in h]),
            "n_isolated": np.array([r["n_isolated"] for r in h]),
            "n_unreached": np.array([r["n_unreached"] for r in h]),
            "n_components": np.array([r["n_components"] for r in h]),
            "lambda2": np.array([r["lambda2"] for r in h]),
            "heading_rms": np.array([r["heading_rms"] for r in h]),
            "speed_std": np.array([r["speed_std"] for r in h]),
            "fault_active": np.array([r["fault_active"] for r in h]),
            "downlink_up": np.array([r["downlink_up"] for r in h]),
        }
        out["collision"] = out["min_distance"] < self.cfg.collision_distance
        return out

    # ---- resilience observability ---------------------------------------
    def set_fault_profile_relative(self, name: str, start_in: float = 2.0,
                                   duration: float = 3.0, **params) -> dict:
        """Install a standard fault profile starting `start_in` s from now."""
        from .network import make_fault_profile
        if not (np.isfinite(start_in) and start_in >= 0.0):
            raise ValueError("start_in must be a finite number >= 0")
        prof = make_fault_profile(name, self.t + float(start_in), float(duration), **params)
        self.network.set_fault_profile(prof)
        self.log_status(f"FAULT PROFILE {name} scheduled at t={self.t + start_in:.1f}s "
                        f"for {duration:g}s")
        return prof.as_dict()

    def resilience_summary(self) -> dict:
        """Supervisor + communication health, from the real engine state."""
        active = self.control_mode == "adaptive_comm" and self.cfg.supervisor_enabled
        out = {"control_mode": self.control_mode, "supervisor_enabled": bool(self.cfg.supervisor_enabled),
               "supervisor_active": active, "faults": self.network.fault_snapshot()}
        if active:
            sups = {f.id: self.supervisors[f.id].snapshot() for f in self.followers}
            out["followers"] = sups
            sev = {"NORMAL": 0, "DEGRADED": 1, "RECOVERING": 2, "HOLD": 3}
            out["worst_state"] = max((v["state"] for v in sups.values()), key=lambda s: sev[s])
            merged = []
            for fid, v in sups.items():
                merged += [dict(t, agent=fid) for t in v["transitions"]]
            out["transitions"] = sorted(merged, key=lambda r: r["t"])[-30:]
            tot = {k: sum(v["durations"][k] for v in sups.values()) for k in STATE_CODES_NAMES}
            out["durations_total"] = {k: round(x, 2) for k, x in tot.items()}
        return out

    def connectivity_summary(self) -> dict:
        """Latest connectivity/consensus diagnostics + run-level tracker."""
        out = dict(self.connectivity) if self.connectivity else {}
        out["tracker"] = self.conn_tracker.summary(self.t)
        out["closest_approach"] = dict(self.closest_approach)
        out["link_timeout_s"] = {"downlink": self.cfg.connectivity_downlink_timeout_s,
                                 "uplink": self.cfg.connectivity_uplink_timeout_s}
        out["scope"] = "global diagnostic (not available to individual followers)"
        return out

    def get_state(self, n_messages: int = 40) -> dict:
        """JSON-serialisable snapshot of everything a UI needs."""
        cfg = self.cfg
        lt = self.last_tick
        agents = []
        for a in self.agents:
            d = a.as_dict()
            if a.id > 0:
                age, loss_rate, qual = self._link_quality(a, self.t)
                d["communication_age"] = round(age, 3)
                d["communication_loss_estimate"] = round(float(loss_rate), 3)
                d["communication_quality"] = round(qual, 3)
            d["slot"] = None
            if lt and a.id > 0 and a.mode in (AgentMode.FOLLOW, AgentMode.REGROUP):
                d["slot"] = [round(float(lt["targets"][a.id][0]), 3),
                             round(float(lt["targets"][a.id][1]), 3)]
            agents.append(d)

        targets = []
        if self.leader.mode == AgentMode.GOTO and self.leader.target is not None:
            targets.append({"agent": 0, "kind": "goto",
                            "x": float(self.leader.target[0]), "y": float(self.leader.target[1])})
        for f in self.followers:
            if f.target is not None:
                targets.append({"agent": f.id, "kind": f.mode.value.lower(),
                                "x": float(f.target[0]), "y": float(f.target[1])})
            elif (self.commands.state == MissionState.SCATTERING
                  and f.id in self.commands.scatter_targets):
                p = self.commands.scatter_targets[f.id]       # command not delivered yet
                targets.append({"agent": f.id, "kind": "scatter_pending",
                                "x": float(p[0]), "y": float(p[1])})

        return {
            "time": round(self.t, 3),
            "step": self.step_count,
            "halted": self.halted,
            "fault": self.fault,
            "sim_mode": self.sim_mode.value,
            "mission_state": self.commands.state.value,
            "control_mode": self.control_mode,
            "world": {"x_min": cfg.world_x_min, "x_max": cfg.world_x_max,
                      "y_min": cfg.world_y_min, "y_max": cfg.world_y_max,
                      "margin": cfg.boundary_margin},
            "collision_distance": cfg.collision_distance,
            "agents": agents,
            "targets": targets,
            "formation": {"name": self.formation_name,
                          "offsets": self.formation.tolist()},
            "tasks": self.tasks.to_list(),
            "allocation": self.tasks.summary_lines(),
            "network": self.network.snapshot(),
            "resilience": self.resilience_summary(),
            "connectivity": self.connectivity_summary(),
            "messages": self.bus.recent(n_messages),
            "command_history": self.commands.history_list(30),
            "status_log": list(self.status_log)[-20:],
            "keyboard": self.keyboard.state_report(),
            "manual_command": {"v": round(self.keyboard.v_cmd, 3),
                               "omega": round(self.keyboard.w_cmd, 3)},
            "pending_commands": len(self.pending),
            "boundary_clamps": int(self.clamp_count.sum()),
            "min_distance": None if not lt else round(float(lt["min_distance"]), 3),
            "formation_rms": None if not lt else round(float(lt["formation_rms"]), 3),
        }


# ---------------------------------------------------------------------------
# Research mode: batch simulation with the notebook's call signature
# ---------------------------------------------------------------------------
def simulate(mode: str = "advanced", seed: int = 42, loss_scale: float = 1.0,
             sensor_sigma: float | None = None, duration: float = T_FINAL,
             legacy: bool = True, cfg: Config | None = None,
             n_agents: int | None = None) -> dict:
    """Run one fixed-length scenario and return the notebook-style history.

    legacy=True  reproduces the original notebook (no boundary logic,
                 back-dated packets, constant feed-forward) so ZOH / PIDR /
                 Advanced numbers are directly comparable to the old results.
    legacy=False runs the full upgraded engine (boundary guard, causal
                 latency, decaying dead reckoning).
    """
    if cfg is None:
        cfg = Config.legacy() if legacy else Config()
    sim = MultiAgentSimulation(cfg, n_agents=n_agents, control_mode=mode,
                               seed=seed, loss_scale=loss_scale,
                               sensor_sigma=sensor_sigma, record_history=True)
    for _ in range(int(round(duration / cfg.dt)) + 1):   # inclusive of t = duration
        if not sim.step():
            break
    return sim.history()