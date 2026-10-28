"""
recording.py -- versioned run recordings and a lightweight replay engine.

Two different things must not be confused:

REPLAY   Showing the frames that were SAVED in a recording.  Nothing is
         simulated; the timeline cannot differ from what was recorded.
RERUN    Re-simulating from the recorded `RunSpec` (seed + configuration).
         The engine is deterministic for a given code version / NumPy build,
         so a rerun normally matches, but this is not guaranteed across code
         changes or platforms.  `compare_rerun` reports the actual difference.

Format (JSON, version 1, no pickle):

    {"format": "resilientsync-recording", "version": 1,
     "meta":   {run spec, dt, stride, n_agents, world, created_utc, ...},
     "frames": {"t": [...], "states": [[[x,y,th,v,w] * n] ...], ...},
     "events": {"supervisor_transitions": [...], "fault_intervals": [...],
                "connectivity_interruptions": [...], "closest_approach": {...}}}

All per-frame arrays have the same length as frames["t"].  Loading validates
shape, finiteness, monotonic time and a size limit, and rejects anything else
with `RecordingError` (never an unhandled exception).
"""
from __future__ import annotations

import bisect
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .config import Config
from .connectivity import summarize_series
from .connectivity import ConsensusTolerance, first_sustained_time
from .metrics import compute_metrics, compute_recovery_metrics
from .network import PROFILE_NAMES, make_fault_profile

FORMAT = "resilientsync-recording"
VERSION = 1
MAX_BYTES = 40 * 1024 * 1024
CONTROL_MODES = ("zoh", "pidr", "advanced", "adaptive_comm")
FORMATIONS = ("WEDGE", "LINE", "COLUMN")
STATE_NAMES = {0: "NORMAL", 1: "DEGRADED", 2: "HOLD", 3: "RECOVERING"}

# per-frame arrays: name -> trailing shape description (None = scalar per frame,
# "n" = one value per agent, "f" = one per follower, "n5" = n x 5 states, "n2" = n x 2)
FRAME_FIELDS = {
    "t": None, "states": "n5", "targets": "n2", "errors": "n",
    "formation_rms": None, "min_distance": None,
    "communication_quality": "n", "age": "f", "supervisor_state": "n", "caution": "n",
    "v_cmd": "n", "w_cmd": "n", "n_isolated": None, "n_unreached": None,
    "n_components": None, "lambda2": None, "heading_rms": None, "speed_std": None,
    "downlink_up": "f", "fault_active": None,
}


class RecordingError(ValueError):
    """The recording is malformed, incompatible or too large."""


# ---------------------------------------------------------------------------
# Run specification (what is needed to RERUN)
# ---------------------------------------------------------------------------
@dataclass
class RunSpec:
    control_mode: str = "adaptive_comm"
    seed: int = 42
    duration: float = 18.0
    n_agents: int = 5
    formation: str = "WEDGE"
    loss_scale: float = 1.0
    supervisor_enabled: bool = True
    fault_profile: str = "blackout"
    fault_start: float = 5.0
    fault_duration: float = 3.0
    fault_probability: float = 0.30
    extra_latency_s: float = 0.30
    jitter_s: float = 0.15
    stride: int = 1

    def validate(self) -> "RunSpec":
        def num(name, lo, hi):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) \
                    or not lo <= v <= hi:
                raise ValueError(f"{name} must be a number in [{lo}, {hi}], got {v!r}")
        if self.control_mode not in CONTROL_MODES:
            raise ValueError(f"control_mode must be one of {CONTROL_MODES}")
        if str(self.formation).upper() not in FORMATIONS:
            raise ValueError(f"formation must be one of {FORMATIONS}")
        self.formation = str(self.formation).upper()
        if self.fault_profile not in PROFILE_NAMES:
            raise ValueError(f"fault_profile must be one of {PROFILE_NAMES}")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or not 0 <= self.seed < 2**31:
            raise ValueError("seed must be an integer in [0, 2^31)")
        if not isinstance(self.n_agents, int) or not 2 <= self.n_agents <= 12:
            raise ValueError("n_agents must be an integer in [2, 12]")
        if not isinstance(self.stride, int) or not 1 <= self.stride <= 100:
            raise ValueError("stride must be an integer in [1, 100]")
        num("duration", 1.0, 120.0)
        num("loss_scale", 0.0, 10.0)
        num("fault_start", 0.0, 600.0)
        num("fault_duration", 0.05, 600.0)
        num("fault_probability", 0.0, 1.0)
        num("extra_latency_s", 0.0, 5.0)
        num("jitter_s", 0.0, 5.0)
        if not isinstance(self.supervisor_enabled, bool):
            raise ValueError("supervisor_enabled must be a boolean")
        return self

    def build_fault_profile(self):
        return make_fault_profile(self.fault_profile, self.fault_start, self.fault_duration,
                                  probability=self.fault_probability,
                                  extra_latency_s=self.extra_latency_s, jitter_s=self.jitter_s)

    @classmethod
    def from_dict(cls, d: dict) -> "RunSpec":
        if not isinstance(d, dict):
            raise ValueError("run spec must be an object")
        known = {k: d[k] for k in asdict(cls()) if k in d}
        extra = set(d) - set(asdict(cls()))
        if extra:
            raise ValueError(f"unknown run-spec fields: {sorted(extra)}")
        return cls(**known).validate()


# ---------------------------------------------------------------------------
# Building a recording
# ---------------------------------------------------------------------------
def _r(a, nd=4):
    return np.round(np.asarray(a, dtype=float), nd).tolist()


def build_recording(sim, spec: RunSpec, stride: int = 1) -> dict:
    """Recording dict from a finished simulation created with record_history=True."""
    h = sim.history()
    idx = np.arange(0, len(h["t"]), max(1, int(stride)))
    f = {
        "t": _r(h["t"][idx], 4), "states": _r(h["states"][idx]), "targets": _r(h["targets"][idx]),
        "errors": _r(h["errors"][idx]), "formation_rms": _r(h["formation_rms"][idx]),
        "min_distance": _r(h["min_distance"][idx]),
        "communication_quality": _r(h["communication_quality"][idx], 3),
        "age": _r(h["blackout_age"][idx], 3),
        "supervisor_state": h["supervisor_state"][idx].astype(int).tolist(),
        "caution": _r(h["caution"][idx], 3), "v_cmd": _r(h["v_cmd"][idx]), "w_cmd": _r(h["w_cmd"][idx]),
        "n_isolated": h["n_isolated"][idx].astype(int).tolist(),
        "n_unreached": h["n_unreached"][idx].astype(int).tolist(),
        "n_components": h["n_components"][idx].astype(int).tolist(),
        "lambda2": _r(h["lambda2"][idx], 4), "heading_rms": _r(h["heading_rms"][idx]),
        "speed_std": _r(h["speed_std"][idx]),
        "downlink_up": h["downlink_up"][idx].astype(bool).tolist(),
        "fault_active": h["fault_active"][idx].astype(bool).tolist(),
    }
    trans = []
    for fid, sup in sim.supervisors.items():
        trans += [dict(r.as_dict(), agent=fid) for r in sup.transitions]
    trans.sort(key=lambda r: (r["t"], r["agent"]))
    events = {
        "supervisor_transitions": trans if sim.control_mode == "adaptive_comm" and sim.cfg.supervisor_enabled else [],
        "fault_intervals": [e for e in sim.network.fault_snapshot()["events"]],
        "connectivity_interruptions": summarize_series(h["t"], h["n_isolated"])["interruptions"],
        "closest_approach": dict(sim.closest_approach),
    }
    meta = {
        "run_spec": asdict(spec), "dt": sim.dt, "stride": int(stride), "n_agents": sim.n,
        "control_mode": sim.control_mode, "seed": spec.seed,
        "formation_offsets": sim.formation.tolist(),
        "world": {"x_min": sim.cfg.world_x_min, "x_max": sim.cfg.world_x_max,
                  "y_min": sim.cfg.world_y_min, "y_max": sim.cfg.world_y_max},
        "collision_distance": sim.cfg.collision_distance,
        "supervisor_enabled": bool(sim.cfg.supervisor_enabled),
        "fault_profile": sim.network.profile.as_dict(),
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "metrics": {k: float(v) for k, v in compute_metrics(h).items()},
        "note": ("Recorded timeline. Replay shows these saved frames; a rerun re-simulates "
                 "from run_spec and is only expected, not guaranteed, to match."),
    }
    rec = {"format": FORMAT, "version": VERSION, "meta": meta, "frames": f, "events": events}
    validate_recording(rec)
    return rec


def run_spec(spec: RunSpec) -> dict:
    """Run a headless simulation for `spec` and return its recording."""
    from .simulation import MultiAgentSimulation        # local import: avoid cycles
    spec.validate()
    cfg = Config().copy(supervisor_enabled=spec.supervisor_enabled)
    sim = MultiAgentSimulation(cfg, n_agents=spec.n_agents, control_mode=spec.control_mode,
                               seed=spec.seed, loss_scale=spec.loss_scale,
                               formation=spec.formation, record_history=True,
                               fault_profile=spec.build_fault_profile())
    sim.run(spec.duration)
    if sim.halted:
        raise RuntimeError(f"simulation halted: {sim.fault}")
    return build_recording(sim, spec, spec.stride)


# ---------------------------------------------------------------------------
# Validation / IO
# ---------------------------------------------------------------------------
def validate_recording(rec: Any) -> dict:
    """Validate structure and numeric sanity; returns `rec` or raises RecordingError."""
    if not isinstance(rec, dict):
        raise RecordingError("recording must be a JSON object")
    if rec.get("format") != FORMAT:
        raise RecordingError(f"not a ResilientSync recording (format={rec.get('format')!r})")
    ver = rec.get("version")
    if not isinstance(ver, int) or ver != VERSION:
        raise RecordingError(f"unsupported recording version {ver!r} (this build reads {VERSION})")
    for key in ("meta", "frames", "events"):
        if not isinstance(rec.get(key), dict):
            raise RecordingError(f"missing section '{key}'")
    meta, fr = rec["meta"], rec["frames"]
    n = meta.get("n_agents")
    if not isinstance(n, int) or not 2 <= n <= 12:
        raise RecordingError("meta.n_agents must be an integer in [2, 12]")
    for k in ("dt", "world", "run_spec"):
        if k not in meta:
            raise RecordingError(f"meta.{k} missing")
    t = fr.get("t")
    if not isinstance(t, list) or len(t) < 1:
        raise RecordingError("frames.t must be a non-empty list")
    m = len(t)
    for name, shape in FRAME_FIELDS.items():
        if name not in fr:
            raise RecordingError(f"frames.{name} missing")
        try:
            arr = np.asarray(fr[name], dtype=float)
        except (TypeError, ValueError):
            raise RecordingError(f"frames.{name} contains non-numeric values") from None
        want = {None: (m,), "n": (m, n), "f": (m, n - 1), "n5": (m, n, 5), "n2": (m, n, 2)}[shape]
        if arr.shape != want:
            raise RecordingError(f"frames.{name} has shape {arr.shape}, expected {want}")
        if not np.all(np.isfinite(arr)):
            raise RecordingError(f"frames.{name} contains NaN/Inf")
    if np.any(np.diff(np.asarray(t, float)) <= 0):
        raise RecordingError("frames.t must be strictly increasing")
    for k in ("supervisor_transitions", "fault_intervals", "connectivity_interruptions"):
        if not isinstance(rec["events"].get(k, []), list):
            raise RecordingError(f"events.{k} must be a list")
    return rec


def save_recording(rec: dict, path) -> Path:
    validate_recording(rec)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(rec, separators=(",", ":"), allow_nan=False)
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise RecordingError("recording exceeds the size limit; increase stride")
    path.write_text(text, encoding="utf-8")
    return path


def loads_recording(text: str) -> dict:
    if len(text.encode("utf-8", errors="ignore")) > MAX_BYTES:
        raise RecordingError("recording exceeds the size limit")
    try:
        rec = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise RecordingError(f"invalid JSON: {exc}") from None
    return validate_recording(rec)


def load_recording(path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise RecordingError(f"no such recording: {path.name}")
    if path.stat().st_size > MAX_BYTES:
        raise RecordingError("recording exceeds the size limit")
    try:
        return loads_recording(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        raise RecordingError("recording is not valid UTF-8 text") from None


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------
class Replay:
    """Seekable view over a validated recording (never simulates anything)."""

    def __init__(self, rec: dict):
        self.rec = validate_recording(rec)
        self.t = np.asarray(rec["frames"]["t"], float)
        self.n = rec["meta"]["n_agents"]
        self.i = 0
        self.playing = False

    def __len__(self) -> int:
        return len(self.t)

    @property
    def duration(self) -> float:
        return float(self.t[-1])

    def index_at(self, time: float) -> int:
        """Index of the recorded frame nearest to `time` (clamped to the run)."""
        if not isinstance(time, (int, float)) or not math.isfinite(time):
            raise ValueError("time must be a finite number")
        k = bisect.bisect_left(self.t.tolist(), time)
        if k <= 0:
            return 0
        if k >= len(self.t):
            return len(self.t) - 1
        return k if self.t[k] - time < time - self.t[k - 1] else k - 1

    def seek(self, time: float) -> dict:
        self.i = self.index_at(time)
        return self.frame(self.i)

    def step(self, k: int = 1) -> dict:
        self.i = int(min(max(self.i + int(k), 0), len(self.t) - 1))
        return self.frame(self.i)

    def frame(self, i: Optional[int] = None) -> dict:
        i = self.i if i is None else int(i)
        if not 0 <= i < len(self.t):
            raise IndexError("frame index out of range")
        f = self.rec["frames"]
        t = float(self.t[i])
        trans = [r for r in self.rec["events"].get("supervisor_transitions", []) if r["t"] <= t + 1e-9]
        active = [e for e in self.rec["events"].get("fault_intervals", [])
                  if e["start"] - 1e-9 <= t < (math.inf if e["end"] is None else e["end"])]
        out = {k: f[k][i] for k in f}
        out.update(index=i, supervisor_state_names=[STATE_NAMES[int(s)] for s in f["supervisor_state"][i]],
                   recent_transitions=trans[-8:], active_faults=active)
        return out

    # ---- investigation --------------------------------------------------------
    def max_error(self) -> dict:
        e = np.asarray(self.rec["frames"]["formation_rms"], float)
        k = int(np.argmax(e))
        return {"t": float(self.t[k]), "formation_rms": float(e[k]), "index": k}

    def min_separation(self) -> dict:
        d = np.asarray(self.rec["frames"]["min_distance"], float)
        k = int(np.argmin(d))
        S = np.asarray(self.rec["frames"]["states"][k], float)[:, :2]
        D = np.linalg.norm(S[:, None] - S[None], axis=2)
        D[np.diag_indices(self.n)] = np.inf
        a, b = divmod(int(np.argmin(D)), self.n)
        return {"t": float(self.t[k]), "distance": float(d[k]), "index": k,
                "pair": [min(a, b), max(a, b)],
                "below_collision_distance": bool(d[k] < self.rec["meta"]["collision_distance"])}

    def summary(self) -> dict:
        """Structured investigation summary built only from recorded data."""
        m, ev, fr = self.rec["meta"], self.rec["events"], self.rec["frames"]
        mx, ms = self.max_error(), self.min_separation()
        faults = ev.get("fault_intervals", [])
        conn = ev.get("connectivity_interruptions", [])
        trans = [r for r in ev.get("supervisor_transitions", []) if r.get("kind") == "transition"]
        sev = {"NORMAL": 0, "DEGRADED": 1, "RECOVERING": 2, "HOLD": 3}
        st = np.asarray(fr["supervisor_state"], int)
        time_in = {}
        dt = np.diff(self.t, append=self.t[-1])
        for code, name in STATE_NAMES.items():
            time_in[name] = float(np.sum(dt[:, None] * (st[:, 1:] == code)) / max(1, self.n - 1))
        lines = [f"Run: {m['control_mode']} (seed {m['seed']}, {self.duration:.1f} s, "
                 f"{self.n} agents, formation {m['run_spec'].get('formation', '?')}).",
                 f"Fault profile: {m['fault_profile']['name']}"
                 + "".join(f"; {e['kind']} {e['start']:.1f}-"
                           f"{'end' if e['end'] is None else format(e['end'], '.1f')} s" for e in faults) + "."]
        lines.append(f"Peak formation RMS error {mx['formation_rms']:.2f} m at t = {mx['t']:.2f} s"
                     + self._during(mx["t"], faults) + ".")
        lines.append(f"Minimum separation {ms['distance']:.2f} m at t = {ms['t']:.2f} s between "
                     f"agents {ms['pair'][0]} and {ms['pair'][1]}"
                     + (" (BELOW the collision distance)." if ms["below_collision_distance"]
                        else f" (collision distance {m['collision_distance']} m not breached)."))
        if conn:
            lines.append("Connectivity (leader->follower links) was interrupted "
                         + "; ".join(f"{c['start']:.1f}-{'end' if c['end'] is None else format(c['end'], '.1f')} s"
                                     for c in conn) + ".")
        else:
            lines.append("No follower lost its leader link long enough to count as a connectivity interruption.")
        if trans:
            lines.append(f"Supervisor: {len(trans)} transitions; first: t={trans[0]['t']:.2f} s "
                         f"agent {trans[0]['agent']} {trans[0]['from']}->{trans[0]['to']} ({trans[0]['reason']})")
        lines.append("Communication restoration, connectivity restoration, heading consensus and "
                     "formation recovery are separate events; see the plots/metrics for each.")
        return {"milestones": self.milestones(), "text": lines, "max_error": mx, "min_separation": ms, "time_in_state_s": time_in,
                "n_transitions": len(trans), "connectivity_interruptions": conn,
                "fault_intervals": faults, "metrics": m.get("metrics", {})}

    def milestones(self, fresh_age_s: float = 0.30) -> dict:
        """Four DIFFERENT restoration events after the fault window, each with its own status.

        communication  every follower's leader-message age <= fresh_age_s (first instant)
        connectivity   no follower isolated from the leader (end of last interruption)
        consensus      RMS heading disagreement <= tolerance, sustained (ConsensusTolerance)
        formation      sustained formation recovery (simulation.metrics.compute_recovery_metrics)

        Returns {"window": None, ...} when the run has no finite fault window.
        """
        ev = self.rec["events"]
        fin = [e for e in ev.get("fault_intervals", []) if e.get("end") is not None]
        if not fin:
            return {"window": None, "note": "no finite fault window in this recording"}
        w0, w1 = min(e["start"] for e in fin), max(e["end"] for e in fin)
        f = self.rec["frames"]
        age = np.asarray(f["age"], float).max(axis=1)
        out = {"window": [w0, w1]}
        after = self.t >= w1
        fresh = np.flatnonzero(after & (age <= fresh_age_s))
        out["communication"] = ({"status": "restored", "t": float(self.t[fresh[0]]),
                                 "lag_s": round(float(self.t[fresh[0]] - w1), 3)} if fresh.size else
                                {"status": "not_restored"})
        iv = [c for c in ev.get("connectivity_interruptions", [])
              if c["end"] is None or c["end"] > w0]
        if not iv:
            out["connectivity"] = {"status": "not_interrupted"}
        elif iv[-1]["end"] is None:
            out["connectivity"] = {"status": "not_restored"}
        else:
            out["connectivity"] = {"status": "restored", "t": round(iv[-1]["end"], 3),
                                   "lag_s": round(max(0.0, iv[-1]["end"] - w1), 3)}
        tol = ConsensusTolerance()
        ok = np.asarray(f["heading_rms"], float) <= tol.heading_rms_rad
        tc = first_sustained_time(self.t, ok, w1, tol.hold_s)
        out["consensus"] = ({"status": "achieved", "t": tc, "lag_s": round(tc - w1, 3),
                             "criterion": f"heading RMS <= {tol.heading_rms_rad} rad for {tol.hold_s} s"}
                            if tc is not None else
                            {"status": "not_achieved",
                             "criterion": f"heading RMS <= {tol.heading_rms_rad} rad for {tol.hold_s} s"})
        try:
            r = compute_recovery_metrics(self.t, f["formation_rms"], w0, w1)
            out["formation"] = {"status": "recovered" if r["recovered"] else "not_recovered",
                                "recovery_time_s": r["recovery_time_s"],
                                "threshold_m": r["recovery_threshold_m"],
                                "baseline_m": r["recovery_baseline_m"],
                                "post_fault_min_error_m": r["post_blackout_min_error_m"],
                                "final_error_m": r["final_error_m"]}
        except ValueError as exc:
            out["formation"] = {"status": "not_applicable", "reason": str(exc)}
        return out

    @staticmethod
    def _during(t: float, faults: List[dict]) -> str:
        for e in faults:
            end = math.inf if e["end"] is None else e["end"]
            if e["start"] <= t < end:
                return f" (during {e['kind']})"
            if end <= t < end + 3.0:
                return f" ({t - end:.1f} s after {e['kind']} ended)"
        return ""


def compare_rerun(rec: dict, atol: float = 1e-6) -> dict:
    """Re-simulate `rec`'s run spec and report how far the rerun deviates."""
    spec = RunSpec.from_dict(rec["meta"]["run_spec"])
    new = run_spec(spec)
    a = np.asarray(rec["frames"]["states"], float)
    b = np.asarray(new["frames"]["states"], float)
    if a.shape != b.shape:
        return {"identical": False, "reason": f"shape differs {a.shape} vs {b.shape}"}
    dev = float(np.max(np.abs(a - b))) if a.size else 0.0
    return {"identical": dev <= atol, "max_abs_state_deviation": dev}
