"""
supervisor.py -- explainable resilience supervisor (finite-state machine).

One `ResilienceSupervisor` watches ONE follower's view of the leader link and
decides how cautiously that follower should track the (possibly stale) leader.
It is pure Python: no RNG, no wall-clock, no numpy state, so identical input
sequences always give identical states, transitions and explanations.

States
------
NORMAL      communication is fresh and reliable
DEGRADED    quality is declining -> mildly conservative tracking
HOLD        leader information is older than the maximum permitted age ->
            explicitly bounded fallback (see "What HOLD does" below)
RECOVERING  fresh messages are back -> caution is ramped out gradually

Legal transitions (everything else raises IllegalTransitionError)
-----------------------------------------------------------------
    NORMAL     -> DEGRADED, HOLD
    DEGRADED   -> NORMAL,   HOLD
    HOLD       -> RECOVERING
    RECOVERING -> NORMAL,   HOLD

Inputs per update: simulation time `t` [s], communication `quality` in [0,1]
(see controller.estimate_communication_quality) and `age` [s] of the newest
usable leader message.  HOLD entry / exit use *age only*: the quality
estimate contains a sliding loss window that stays pessimistic for about one
second after a link returns, which would otherwise keep the supervisor in HOLD
although fresh data is already arriving.

Hysteresis and dwell
--------------------
* every threshold has a separate enter and exit value (enter < exit for
  quality, exit < enter for age);
* a transition fires only after its trigger condition has held continuously
  for a configurable dwell time;
* de-escalating (leaving a state towards more trust) requires
  `min_state_time_s` in that state; escalations (to DEGRADED or HOLD) are
  never delayed by that rule, only by their own dwell time.

What HOLD does (and does not do)
--------------------------------
HOLD is NOT "stop".  Stopping while the leader keeps moving only increases the
formation error, and stopping close to neighbours does not by itself
guarantee safe separation (actuator lag means the robot still travels after a
zero command).  Instead the supervisor outputs bounded *caution modifiers*
that the follower controller applies to its normal command:

    ff_scale     multiplier on the leader-velocity feed-forward (<= 1)
    speed_frac   fraction of the actuator speed limit allowed (0 < f <= 1)
    avoid_scale  multiplier on the collision-avoidance aim-point shift (>= 1)

All modifiers are derived from one scalar "caution level" c in [0, 1] that
rises quickly on escalation and falls slowly (ramp) on recovery.  Modifiers
can never loosen an actuator limit; the simulator still clips every command.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SupervisorState(str, Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    HOLD = "HOLD"
    RECOVERING = "RECOVERING"


S = SupervisorState
STATE_CODES = {S.NORMAL: 0, S.DEGRADED: 1, S.HOLD: 2, S.RECOVERING: 3}
STATE_NAMES = tuple(s.value for s in S)

LEGAL_TRANSITIONS: Dict[SupervisorState, frozenset] = {
    S.NORMAL: frozenset({S.DEGRADED, S.HOLD}),
    S.DEGRADED: frozenset({S.NORMAL, S.HOLD}),
    S.HOLD: frozenset({S.RECOVERING}),
    S.RECOVERING: frozenset({S.NORMAL, S.HOLD}),
}


class IllegalTransitionError(RuntimeError):
    """Raised if code attempts a transition that is not in LEGAL_TRANSITIONS."""


def is_legal_transition(src: SupervisorState, dst: SupervisorState) -> bool:
    return dst in LEGAL_TRANSITIONS[src]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def _finite(name: str, v: float) -> float:
    v = float(v)
    if not math.isfinite(v):
        raise ValueError(f"{name} must be finite, got {v!r}")
    return v


@dataclass(frozen=True)
class SupervisorConfig:
    """Thresholds, dwell times and fallback strength (all validated).

    Calibration note: with NO injected fault the default simulated channel
    (Gilbert-Elliott loss + 1-4 step latency) gives a communication quality of
    median 0.61, 5th percentile 0.40, 1st percentile 0.30 and a message age of
    p99 0.6 s / max 1.1 s (10 seeds x 30 s x 4 followers, seeds 100-109).  The
    defaults below are placed outside that nominal envelope so that the
    supervisor stays in NORMAL on a healthy link.  Re-calibrate if the channel
    parameters in `Config` change.
    """
    # --- DEGRADED (quality based, hysteresis: enter < exit) ----------------
    degrade_enter_q: float = 0.35
    degrade_exit_q: float = 0.50
    degrade_enter_dwell_s: float = 0.10
    degrade_exit_dwell_s: float = 0.50
    # --- HOLD (age based, hysteresis: exit < enter) ------------------------
    hold_enter_age_s: float = 1.25     # maximum permitted leader-message age
    hold_exit_age_s: float = 0.50
    hold_enter_dwell_s: float = 0.0    # escalation is immediate by default
    hold_exit_dwell_s: float = 0.30
    # --- RECOVERING -> NORMAL ----------------------------------------------
    recovery_exit_q: float = 0.45      # must be >= degrade_enter_q
    recovery_ramp_s: float = 1.5       # time for caution to fall from 1 to 0
    # --- general -----------------------------------------------------------
    min_state_time_s: float = 0.25
    # --- caution / fallback strength ---------------------------------------
    degraded_caution: float = 0.35     # caution level c while DEGRADED
    caution_rise_per_s: float = 3.0    # how fast c may rise on escalation
    hold_ff_scale: float = 0.60        # feed-forward multiplier at c = 1
    hold_speed_frac: float = 1.00      # speed-limit fraction at c = 1 (1 = no limit; 0.8 measurably hurt, see docs)
    hold_avoid_scale: float = 1.50     # avoidance multiplier at c = 1

    def __post_init__(self):
        for name in ("degrade_enter_q", "degrade_exit_q", "degrade_enter_dwell_s",
                     "degrade_exit_dwell_s", "hold_enter_age_s", "hold_exit_age_s",
                     "hold_enter_dwell_s", "hold_exit_dwell_s", "recovery_exit_q",
                     "recovery_ramp_s", "min_state_time_s", "degraded_caution",
                     "caution_rise_per_s", "hold_ff_scale", "hold_speed_frac",
                     "hold_avoid_scale"):
            _finite(name, getattr(self, name))
        for name in ("degrade_enter_q", "degrade_exit_q", "recovery_exit_q",
                     "degraded_caution"):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"{name} must lie in [0, 1]")
        if not self.degrade_enter_q < self.degrade_exit_q:
            raise ValueError("hysteresis requires degrade_enter_q < degrade_exit_q")
        if self.recovery_exit_q < self.degrade_enter_q:
            raise ValueError("recovery_exit_q must be >= degrade_enter_q, otherwise the "
                             "supervisor would re-enter DEGRADED immediately after recovering")
        if not 0.0 < self.hold_exit_age_s < self.hold_enter_age_s:
            raise ValueError("hysteresis requires 0 < hold_exit_age_s < hold_enter_age_s")
        for name in ("degrade_enter_dwell_s", "degrade_exit_dwell_s",
                     "hold_enter_dwell_s", "hold_exit_dwell_s", "min_state_time_s"):
            if getattr(self, name) < 0.0:
                raise ValueError(f"{name} must be >= 0")
        if self.recovery_ramp_s <= 0.0 or self.caution_rise_per_s <= 0.0:
            raise ValueError("recovery_ramp_s and caution_rise_per_s must be > 0")
        if not 0.0 < self.hold_ff_scale <= 1.0:
            raise ValueError("hold_ff_scale must lie in (0, 1]")
        if not 0.0 < self.hold_speed_frac <= 1.0:
            raise ValueError("hold_speed_frac must lie in (0, 1]: the supervisor "
                             "may limit speed but never commands a stop")
        if self.hold_avoid_scale < 1.0:
            raise ValueError("hold_avoid_scale must be >= 1 (avoidance is never weakened)")


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TransitionRecord:
    t: float
    src: str
    dst: str
    reason: str
    quality: float
    age: float
    kind: str = "transition"        # "transition" | "reset"

    def as_dict(self) -> dict:
        age = self.age if math.isfinite(self.age) else None
        return {"t": round(self.t, 3), "from": self.src, "to": self.dst,
                "reason": self.reason, "quality": round(self.quality, 3),
                "age": None if age is None else round(age, 3), "kind": self.kind}


@dataclass(frozen=True)
class SupervisorDecision:
    """What the controller receives each tick."""
    state: SupervisorState
    transitioned: bool
    reason: str                     # reason of the MOST RECENT transition
    quality: float
    age: float
    caution: float
    ff_scale: float
    speed_frac: float
    avoid_scale: float
    time_in_state: float


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------
class ResilienceSupervisor:
    """Deterministic NORMAL / DEGRADED / HOLD / RECOVERING state machine."""

    def __init__(self, cfg: Optional[SupervisorConfig] = None, name: str = ""):
        self.cfg = cfg or SupervisorConfig()
        self.name = name
        self.reset()

    # ------------------------------------------------------------------
    def reset(self, t: Optional[float] = None, reason: Optional[str] = None) -> None:
        """Return to NORMAL.  With a reason, a 'reset' record is logged first
        (used when a follower leaves formation-following); a bare reset()
        also clears the log and counters (new run / simulation restart)."""
        keep_log = reason is not None
        old = getattr(self, "state", S.NORMAL)
        old_log = getattr(self, "transitions", []) if keep_log else []
        old_dur = getattr(self, "durations", None) if keep_log else None
        self.state = S.NORMAL
        self.transitions: List[TransitionRecord] = list(old_log)
        self.durations: Dict[str, float] = (
            old_dur if old_dur is not None else {s.value: 0.0 for s in S})
        self.invalid_inputs = 0 if not keep_log else getattr(self, "invalid_inputs", 0)
        self.caution = 0.0
        self._t_last: Optional[float] = None
        self._t_state: Optional[float] = None
        self._pending: Optional[SupervisorState] = None
        self._pending_since: Optional[float] = None
        self.last_reason = "Initial state: NORMAL (no transition yet)."
        self.last_quality = 1.0
        self.last_age = 0.0
        if keep_log:
            tt = 0.0 if t is None else float(t)
            self.transitions.append(TransitionRecord(
                tt, old.value, S.NORMAL.value, reason, self.last_quality,
                self.last_age, kind="reset"))
            self.last_reason = reason

    def suspend(self, t: float, reason: str) -> None:
        """The follower stopped following the leader (SCATTER, STOP, ...).

        Clears timers so the next update does not count the gap as time in a
        state.  A non-NORMAL state is reset with a logged 'reset' record."""
        if self.state != S.NORMAL:
            self.reset(t=t, reason=reason)
        else:
            self.caution = 0.0
            self._t_last = self._t_state = None
            self._pending = self._pending_since = None

    # ------------------------------------------------------------------
    def _sanitize(self, quality, age):
        """Missing / invalid values are treated as the worst case, and counted."""
        bad = False
        try:
            q = float(quality)
        except (TypeError, ValueError):
            q, bad = 0.0, True
        try:
            a = float(age)
        except (TypeError, ValueError):
            a, bad = math.inf, True
        if not math.isfinite(q):
            q, bad = 0.0, True
        q = min(max(q, 0.0), 1.0)
        if math.isnan(a) or a < 0.0:
            a, bad = math.inf, True
        if bad:
            self.invalid_inputs += 1
        return q, a, bad

    def _desired(self, q: float, age: float):
        """(target state, dwell, human reason) implied by the inputs, or None."""
        c, st = self.cfg, self.state
        if st in (S.NORMAL, S.DEGRADED, S.RECOVERING):
            if age >= c.hold_enter_age_s:
                return (S.HOLD, c.hold_enter_dwell_s,
                        f"Entered HOLD because leader information age {self._fa(age)} "
                        f"exceeded the maximum permitted age {c.hold_enter_age_s:.2f}s.")
        if st == S.NORMAL:
            if q < c.degrade_enter_q:
                return (S.DEGRADED, c.degrade_enter_dwell_s,
                        f"Entered DEGRADED because communication quality {q:.2f} "
                        f"fell below the configured threshold {c.degrade_enter_q:.2f}.")
        elif st == S.DEGRADED:
            if q >= c.degrade_exit_q:
                return (S.NORMAL, c.degrade_exit_dwell_s,
                        f"Returned to NORMAL because communication quality {q:.2f} "
                        f"stayed at or above {c.degrade_exit_q:.2f} for the required dwell time.")
        elif st == S.HOLD:
            if age <= c.hold_exit_age_s:
                return (S.RECOVERING, c.hold_exit_dwell_s,
                        f"Entered RECOVERING after leader messages stayed fresh "
                        f"(age {self._fa(age)} <= {c.hold_exit_age_s:.2f}s) for the required dwell time.")
        elif st == S.RECOVERING:
            if q >= c.recovery_exit_q and self.caution <= 1e-9:
                return (S.NORMAL, 0.0,
                        f"Returned to NORMAL after the recovery ramp completed and "
                        f"quality {q:.2f} reached {c.recovery_exit_q:.2f}.")
        return None

    @staticmethod
    def _fa(age: float) -> str:
        return "inf" if not math.isfinite(age) else f"{age:.2f}s"

    def _target_caution(self) -> float:
        return {S.NORMAL: 0.0, S.DEGRADED: self.cfg.degraded_caution,
                S.HOLD: 1.0, S.RECOVERING: 0.0}[self.state]

    def _transition(self, dst: SupervisorState, t: float, reason: str,
                    q: float, age: float) -> None:
        if not is_legal_transition(self.state, dst):
            raise IllegalTransitionError(f"{self.state.value} -> {dst.value} is not legal")
        self.transitions.append(TransitionRecord(
            t, self.state.value, dst.value, reason, q, age))
        self.state = dst
        self._t_state = t
        self.last_reason = reason
        self._pending = None
        self._pending_since = None

    # ------------------------------------------------------------------
    def update(self, t: float, quality: float, age: float) -> SupervisorDecision:
        """Advance the machine to time `t` and return the caution decision."""
        t = _finite("t", t)
        if self._t_last is not None and t < self._t_last - 1e-12:
            raise ValueError(f"time went backwards ({t} < {self._t_last}); "
                             "call reset() when the simulation restarts")
        q, a, _bad = self._sanitize(quality, age)
        self.last_quality, self.last_age = q, a
        c = self.cfg
        if self._t_last is None:                 # first sample: initialise clocks
            self._t_last = self._t_state = t
            dt = 0.0
        else:
            dt = max(0.0, t - self._t_last)
        self.durations[self.state.value] += dt   # time since the last update
        self._t_last = t

        # --- caution level follows the state, rate-limited -----------------
        target = self._target_caution()
        if target > self.caution:
            self.caution = min(target, self.caution + c.caution_rise_per_s * dt)
        else:
            self.caution = max(target, self.caution - dt / c.recovery_ramp_s)

        # --- trigger evaluation with dwell ----------------------------------
        transitioned = False
        want = self._desired(q, a)
        if want is None:
            self._pending = self._pending_since = None
        else:
            dst, dwell, reason = want
            if dst != self._pending:
                self._pending, self._pending_since = dst, t
            held = t - self._pending_since
            in_state = t - self._t_state
            allowed = (dst in (S.HOLD, S.DEGRADED)
                       or in_state + 1e-9 >= c.min_state_time_s)
            if held + 1e-9 >= dwell and allowed:
                self._transition(dst, t, reason, q, a)
                transitioned = True            # caution level follows next update

        return self.decision(transitioned)

    # ------------------------------------------------------------------
    def decision(self, transitioned: bool = False) -> SupervisorDecision:
        c = self.cfg
        lvl = min(max(self.caution, 0.0), 1.0)
        t_in = 0.0 if self._t_state is None or self._t_last is None \
            else max(0.0, self._t_last - self._t_state)
        return SupervisorDecision(
            state=self.state, transitioned=transitioned, reason=self.last_reason,
            quality=self.last_quality, age=self.last_age, caution=lvl,
            ff_scale=1.0 - lvl * (1.0 - c.hold_ff_scale),
            speed_frac=1.0 - lvl * (1.0 - c.hold_speed_frac),
            avoid_scale=1.0 + lvl * (c.hold_avoid_scale - 1.0),
            time_in_state=t_in)

    def snapshot(self, max_transitions: int = 20) -> dict:
        d = self.decision()
        tot = sum(self.durations.values())
        return {
            "state": d.state.value, "reason": d.reason,
            "quality": round(d.quality, 3),
            "age": None if not math.isfinite(d.age) else round(d.age, 3),
            "caution": round(d.caution, 3), "ff_scale": round(d.ff_scale, 3),
            "speed_frac": round(d.speed_frac, 3), "avoid_scale": round(d.avoid_scale, 3),
            "time_in_state": round(d.time_in_state, 3),
            "durations": {k: round(v, 3) for k, v in self.durations.items()},
            "duration_fraction": {k: (round(v / tot, 4) if tot > 0 else 0.0)
                                  for k, v in self.durations.items()},
            "transition_count": len(self.transitions),
            "invalid_inputs": self.invalid_inputs,
            "transitions": [r.as_dict() for r in self.transitions[-max_transitions:]],
        }
