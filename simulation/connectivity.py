"""
connectivity.py -- communication topology, consensus metrics, connectivity tracking.

Three distinct concepts are measured here and must not be conflated:

1. Formation tracking   how close robots are to their formation slots
                        (metrics.py / formation_rms).  NOT computed here.
2. Consensus            whether *state variables* (heading, speed) agree.
3. Connectivity         whether the *communication graph* allows information
                        to flow.

Graph model
-----------
Nodes are agents (0 = leader).  A directed edge i -> j means "agent j has
received a packet from agent i within `link_timeout_s`".  It is derived from
the real `Network` delivery statistics, never from physical proximity.
In the current simulator all traffic goes through the leader (star topology:
pose broadcast L -> Fi, heartbeat/ACK Fi -> L); followers do not exchange
packets with each other, so there are no follower-follower links.

* Directed reachability (who can the leader's information reach?) is the
  quantity that matters for formation control and is computed on the directed
  graph with `reachable_from`.
* Components and algebraic connectivity are defined for UNDIRECTED graphs.
  We build the undirected graph from the *bidirectional* links only
  (A_und[i, j] = min(A[i, j], A[j, i])), which is a conservative choice and is
  stated wherever it is used.  Algebraic connectivity (Fiedler value) is the
  second-smallest eigenvalue of the Laplacian L = D - A of a symmetric,
  non-negative weight matrix; it is > 0 iff the graph is connected.
  Numerical tolerance: eigenvalues below `tol` (default 1e-9) are reported as 0.

Global vs. local information
----------------------------
Everything in this module is a *global diagnostic* computed by the simulator
(or the analyst).  A real follower cannot observe the whole graph; it only
knows its own message age.  Nothing here is fed back into the controllers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from .kinematics import wrap_angle

# ---------------------------------------------------------------------------
# Graph primitives
# ---------------------------------------------------------------------------
def _as_matrix(A) -> np.ndarray:
    A = np.array(A, dtype=float)
    if A.ndim != 2 or A.shape[0] != A.shape[1]:
        raise ValueError(f"adjacency must be a square matrix, got shape {A.shape}")
    if not np.all(np.isfinite(A)):
        raise ValueError("adjacency contains non-finite values")
    if np.any(A < 0):
        raise ValueError("adjacency weights must be non-negative")
    return A


def directed_adjacency(n: int, up: Iterable[Tuple[int, int]]) -> np.ndarray:
    """Binary directed adjacency; A[i, j] = 1 iff the link i -> j is up."""
    A = np.zeros((n, n))
    for i, j in up:
        if not (0 <= i < n and 0 <= j < n):
            raise ValueError(f"link ({i}, {j}) outside 0..{n - 1}")
        if i != j:
            A[i, j] = 1.0
    return A


def bidirectional(A) -> np.ndarray:
    """Undirected graph keeping only links that work in BOTH directions."""
    A = _as_matrix(A)
    np.fill_diagonal(A, 0.0)
    return np.minimum(A, A.T)


def is_symmetric(A, tol: float = 1e-12) -> bool:
    A = np.asarray(A, float)
    return A.ndim == 2 and A.shape[0] == A.shape[1] and bool(np.allclose(A, A.T, atol=tol))


def laplacian(A) -> np.ndarray:
    """Graph Laplacian D - A of a symmetric non-negative weight matrix."""
    A = _as_matrix(A)
    if not is_symmetric(A):
        raise ValueError("Laplacian / algebraic connectivity require a symmetric "
                         "(undirected) graph; use bidirectional(A) or reachable_from()")
    A = A.copy()
    np.fill_diagonal(A, 0.0)
    return np.diag(A.sum(axis=1)) - A


def connected_components(A) -> List[List[int]]:
    """Connected components of the undirected graph (A is symmetrised by max)."""
    A = _as_matrix(A)
    n = A.shape[0]
    U = np.maximum(A, A.T) > 0
    seen = [False] * n
    comps: List[List[int]] = []
    for s in range(n):
        if seen[s]:
            continue
        stack, comp = [s], []
        seen[s] = True
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in np.nonzero(U[u])[0]:
                if not seen[v]:
                    seen[v] = True
                    stack.append(int(v))
        comps.append(sorted(comp))
    return sorted(comps, key=lambda c: c[0])


def reachable_from(A, root: int = 0) -> List[int]:
    """Nodes reachable from `root` following directed edges i -> j."""
    A = _as_matrix(A)
    n = A.shape[0]
    if not 0 <= root < n:
        raise ValueError("root out of range")
    seen = {root}
    stack = [root]
    while stack:
        u = stack.pop()
        for v in np.nonzero(A[u] > 0)[0]:
            if int(v) not in seen:
                seen.add(int(v))
                stack.append(int(v))
    return sorted(seen)


def algebraic_connectivity(A, tol: float = 1e-9) -> float:
    """Second-smallest Laplacian eigenvalue (Fiedler value) of an undirected graph.

    n < 2 returns 0.0 (a single node has no second eigenvalue; treated as
    "no connectivity to speak of").  Raises ValueError for asymmetric input.
    """
    A = _as_matrix(A)
    if A.shape[0] < 2:
        return 0.0
    lam = np.linalg.eigvalsh(laplacian(A))
    val = float(lam[1])
    return 0.0 if val < tol else val


def isolated_nodes(A) -> List[int]:
    """Nodes with no bidirectional link at all (degree 0)."""
    A = bidirectional(A)
    return [i for i in range(A.shape[0]) if not np.any(A[i] > 0)]


# ---------------------------------------------------------------------------
# Consensus metrics
# ---------------------------------------------------------------------------
def circular_mean(theta: Sequence[float]) -> float:
    th = np.asarray(theta, float)
    if th.size == 0:
        return 0.0
    return float(math.atan2(np.sin(th).mean(), np.cos(th).mean()))


def heading_disagreement(theta: Sequence[float]) -> Dict[str, float]:
    """Heading disagreement [rad] with angular wrap-around handled.

    rms   sqrt(mean(wrap(theta_i - circular_mean)^2))
    max   largest pairwise angular distance |wrap(theta_i - theta_j)|
    """
    th = np.asarray(theta, float)
    if th.size < 2:
        return {"rms": 0.0, "max": 0.0}
    m = circular_mean(th)
    dev = np.array([wrap_angle(t - m) for t in th])
    mx = 0.0
    for i in range(th.size):
        for j in range(i + 1, th.size):
            mx = max(mx, abs(wrap_angle(th[i] - th[j])))
    return {"rms": float(np.sqrt(np.mean(dev ** 2))), "max": float(mx)}


def speed_disagreement(v: Sequence[float]) -> Dict[str, float]:
    """Linear-speed disagreement [m/s]: population std and max-min spread."""
    v = np.asarray(v, float)
    if v.size < 2:
        return {"std": 0.0, "spread": 0.0}
    return {"std": float(np.std(v)), "spread": float(v.max() - v.min())}


def edge_disagreement(theta: Sequence[float], v: Sequence[float],
                      A) -> Dict[str, Optional[float]]:
    """Mean neighbour-to-neighbour disagreement over the UNDIRECTED edges of A.

    heading [rad] = mean |wrap(theta_i - theta_j)|,  speed [m/s] = mean |v_i - v_j|.
    Returns None values when the graph has no edges (nothing to compare).
    """
    A = _as_matrix(A)
    th, v = np.asarray(theta, float), np.asarray(v, float)
    if th.size != A.shape[0] or v.size != A.shape[0]:
        raise ValueError("state vectors must have one entry per node")
    h, s = [], []
    for i in range(A.shape[0]):
        for j in range(i + 1, A.shape[0]):
            if A[i, j] > 0 or A[j, i] > 0:
                h.append(abs(wrap_angle(th[i] - th[j])))
                s.append(abs(v[i] - v[j]))
    if not h:
        return {"heading": None, "speed": None, "edges": 0}
    return {"heading": float(np.mean(h)), "speed": float(np.mean(s)), "edges": len(h)}


@dataclass(frozen=True)
class ConsensusTolerance:
    """Documented consensus criterion (heading only by default).

    Heading consensus holds when the RMS heading disagreement is <= heading_rms_rad.
    NOTE: speed is NOT part of the default criterion because robots holding a
    rigid formation through a turn legitimately have different speeds
    (v_i = v_leader + omega x offset); see docs/EXPERIMENT_PROTOCOL.md.
    """
    heading_rms_rad: float = 0.25
    hold_s: float = 1.0


def first_sustained_time(t: Sequence[float], ok: Sequence[bool], after: float,
                         hold_s: float) -> Optional[float]:
    """First time >= `after` from which `ok` stays True for at least `hold_s`.

    Returns the START of that window or None (never achieved / run too short).
    """
    t = np.asarray(t, float)
    ok = np.asarray(ok, bool)
    if t.size == 0:
        return None
    run_start = None
    for k in range(t.size):
        if t[k] < after:
            continue
        if ok[k]:
            if run_start is None:
                run_start = t[k]
            if t[k] - run_start >= hold_s - 1e-9:
                return float(run_start)
        else:
            run_start = None
    return None


# ---------------------------------------------------------------------------
# Per-tick evaluation + tracking
# ---------------------------------------------------------------------------
def evaluate_topology(A_directed, root: int = 0, view: str = "bidirectional") -> dict:
    """Full diagnostic snapshot of a directed link matrix (see module docstring).

    view="bidirectional"  undirected graph = links working in BOTH directions
                          (conservative; needs uplink and downlink).
    view="union"          undirected graph = a link exists if EITHER direction
                          works.  Pass a matrix that holds only the links that
                          carry the information of interest (e.g. leader->follower
                          pose links) so the result means "information can flow".
    """
    A = _as_matrix(A_directed)
    n = A.shape[0]
    if view == "bidirectional":
        U = bidirectional(A)
    elif view == "union":
        U = np.maximum(A, A.T)
        np.fill_diagonal(U, 0.0)
    else:
        raise ValueError("view must be 'bidirectional' or 'union'")
    comps = connected_components(U)
    lead_comp = next(c for c in comps if root in c)
    reach = reachable_from(A, root)
    return {
        "n": n,
        "view": view,
        "links": [[i, j] for i in range(n) for j in range(i + 1, n) if U[i, j] > 0],
        "components": comps,
        "n_components": len(comps),
        "connected": len(comps) == 1,
        "leader_component": lead_comp,
        # followers with no path to the leader in the chosen undirected view
        "isolated_from_leader": [i for i in range(n) if i != root and i not in lead_comp],
        # followers the leader's data cannot reach following directed edges
        "unreached_by_leader": [i for i in range(n) if i != root and i not in reach],
        "algebraic_connectivity": algebraic_connectivity(U),
    }


@dataclass
class ConnectivityTracker:
    """Accumulates connectivity interruptions and isolation time over a run.

    An *interruption* is a maximal interval during which at least one follower
    has no bidirectional path to the leader.  Its end is the moment everybody
    is connected again (connectivity restoration).  Isolation time is
    accumulated with a left Riemann sum: the state seen at sample k is held
    over [t_k, t_{k+1}).
    """
    n: int
    interruptions: List[List[Optional[float]]] = field(default_factory=list)  # [start, end|None]
    isolated_s: np.ndarray = field(default=None)
    last_t: Optional[float] = None
    _open: bool = False
    _prev_iso: List[int] = field(default_factory=list)

    def __post_init__(self):
        self.isolated_s = np.zeros(self.n)

    def update(self, t: float, isolated: Iterable[int]) -> None:
        iso = sorted(set(int(i) for i in isolated))
        if self.last_t is not None:
            dt = max(0.0, t - self.last_t)
            for i in self._prev_iso:
                self.isolated_s[i] += dt
        if iso and not self._open:
            self.interruptions.append([t, None])
            self._open = True
        elif not iso and self._open:
            self.interruptions[-1][1] = t
            self._open = False
        self._prev_iso = iso
        self.last_t = t

    def summary(self, t_now: Optional[float] = None) -> dict:
        t_now = self.last_t if t_now is None else t_now
        total, out = 0.0, []
        for s, e in self.interruptions:
            end = t_now if e is None else e
            total += max(0.0, end - s)
            out.append({"start": s, "end": e, "duration": max(0.0, end - s)})
        return {"n_interruptions": len(self.interruptions),
                "interruption_total_s": total,
                "interruptions": out,
                "currently_interrupted": self._open,
                "isolated_s_per_agent": [float(x) for x in self.isolated_s],
                "isolated_s_max": float(self.isolated_s.max()) if self.n else 0.0}


def summarize_series(t: np.ndarray, n_isolated: np.ndarray) -> dict:
    """Interruption statistics from a recorded series (used by the benchmark).

    `n_isolated[k]` = number of followers disconnected from the leader at t[k].
    Each sample is held until the next one (left Riemann sum).
    """
    t = np.asarray(t, float)
    k = np.asarray(n_isolated, float)
    if t.size == 0:
        return {"n_interruptions": 0, "interruption_total_s": 0.0, "interruptions": []}
    iv: List[List[Optional[float]]] = []
    open_ = False
    total = 0.0
    for i in range(t.size):
        bad = k[i] > 0
        if bad and not open_:
            iv.append([float(t[i]), None])
            open_ = True
        elif not bad and open_:
            iv[-1][1] = float(t[i])
            open_ = False
        if i + 1 < t.size and bad:
            total += t[i + 1] - t[i]
    return {"n_interruptions": len(iv), "interruption_total_s": float(total),
            "interruptions": [{"start": s, "end": e,
                               "duration": (t[-1] if e is None else e) - s} for s, e in iv]}
