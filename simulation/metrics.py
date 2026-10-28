
from __future__ import annotations

from typing import Callable, Dict, Iterable

import numpy as np

from .config import CFG, Config

_trapz = getattr(np, "trapezoid", None) or np.trapz  # NumPy 1.x / 2.x


# ---------------------------------------------------------------------------
# Per-run metrics
# ---------------------------------------------------------------------------
def compute_metrics(h: dict) -> Dict[str, float]:
    """Metrics of one run history (dict as returned by `simulate`)."""
    t, e = h["t"], h["formation_rms"]
    return dict(
        ITAE=float(_trapz(t * e, t)),
        RMSE=float(np.sqrt(np.mean(e ** 2))),
        Peak=float(np.max(e)),
        Effort=float(np.mean(h["control_effort"])),
        MinSep=float(np.min(h["min_distance"])),
        Loss=float(np.mean(h["packet_drop"]) * 100),
        Collision=float(np.mean(h["collision"]) * 100),
    )


# ---------------------------------------------------------------------------
# Recovery metrics
# ---------------------------------------------------------------------------
def compute_recovery_metrics(
    t,
    formation_rms,
    blackout_start: float,
    blackout_end: float,
    absolute_tolerance: float = 0.5,
    relative_tolerance: float = 1.25,
    sustain_duration: float = 0.5,
    baseline_window: float = 1.0,
) -> Dict[str, float | bool | None]:
    """
    Measure sustained formation recovery after a communication blackout.

    Recovery occurs when formation error remains below the recovery threshold
    for the required sustain duration after the blackout ends.

    Also reports the minimum formation error after the blackout and the
    formation error at the end of the simulation.
    """
    t = np.asarray(t, dtype=float)
    error = np.asarray(formation_rms, dtype=float)

    # Validate input arrays.
    if t.ndim != 1 or error.ndim != 1 or len(t) != len(error):
        raise ValueError("t and formation_rms must be equal-length 1D arrays")

    if len(t) < 2 or not np.isfinite(t).all() or not np.isfinite(error).all():
        raise ValueError("at least two finite time and error samples are required")

    if np.any(np.diff(t) <= 0):
        raise ValueError("t must be strictly increasing")

    if not (0 <= blackout_start < blackout_end):
        raise ValueError("blackout_end must be greater than blackout_start")

    if absolute_tolerance < 0 or relative_tolerance <= 0:
        raise ValueError(
            "tolerances must be non-negative and relative tolerance positive"
        )

    if sustain_duration < 0 or baseline_window <= 0:
        raise ValueError(
            "sustain_duration must be non-negative and baseline_window positive"
        )

    # Estimate normal formation error immediately before the blackout.
    before = (
        (t < blackout_start)
        & (t >= blackout_start - baseline_window)
    )

    if not np.any(before):
        raise ValueError(
            "no samples available before blackout to estimate baseline"
        )

    baseline = float(np.median(error[before]))

    # Diagnose post-blackout behavior.
    post_blackout = t >= blackout_end

    if not np.any(post_blackout):
        raise ValueError("no samples available after blackout")

    post_blackout_min_error = float(np.min(error[post_blackout]))
    final_error = float(error[-1])

    # Do not allow the recovery threshold to be lower than the absolute
    # tolerance, even when the pre-blackout baseline is close to zero.
    threshold = max(
        absolute_tolerance,
        baseline * relative_tolerance,
    )

    recovery_time = None

    # Find the earliest post-blackout point that stays below the threshold
    # for the entire required duration.
    for i in np.flatnonzero(t >= blackout_end):
        if error[i] > threshold:
            continue

        end_time = t[i] + sustain_duration
        j = int(np.searchsorted(t, end_time, side="left"))

        # Require recorded samples covering the full sustain interval.
        if j >= len(t):
            continue

        if np.all(error[i : j + 1] <= threshold):
            recovery_time = float(t[i] - blackout_end)
            break

    return {
        "recovery_baseline_m": baseline,
        "recovery_threshold_m": float(threshold),
        "recovered": recovery_time is not None,
        "recovery_time_s": recovery_time,
        "post_blackout_min_error_m": post_blackout_min_error,
        "final_error_m": final_error,
    }


def improvement_pct(baseline: float, other: float) -> float:
    """Percentage improvement of `other` over `baseline` (positive = better)."""
    return 100.0 * (baseline - other) / baseline if baseline else 0.0


# ---------------------------------------------------------------------------
# Routh-Hurwitz gain screening (Eq. 21-22 of the report)
# ---------------------------------------------------------------------------
def routh_hurwitz_cubic(a3, a2, a1, a0):
    """Stability of a3*s^3 + a2*s^2 + a1*s + a0.

    Returns (stable: bool, margin: float).
    """
    stable = (
        a3 > 0
        and a2 > 0
        and a1 > 0
        and a0 > 0
        and a2 * a1 > a3 * a0
    )
    return stable, min(a3, a2, a1, a0, a2 * a1 - a3 * a0)


def pid_coefficients(kp, ki, kd, tau=CFG.tau_motor):
    """Characteristic-polynomial coefficients (as used in the notebook)."""
    return tau, 1 + tau * kd, kp + kd, ki


def stability_scan(
    cfg: Config | None = None,
    n: int = 16,
    kp_range=(0.5, 3.2),
    kd_range=(0.15, 1.5),
) -> dict:
    """Grid-screen (Kp, Kd) with Ki fixed; select the largest stable margin."""
    cfg = cfg or CFG
    kp_grid = np.linspace(*kp_range, n)
    kd_grid = np.linspace(*kd_range, n)
    stable = np.zeros((n, n))
    margin = np.zeros((n, n))

    for a, kp in enumerate(kp_grid):
        for b, kd in enumerate(kd_grid):
            stable[a, b], margin[a, b] = routh_hurwitz_cubic(
                *pid_coefficients(kp, cfg.ki, kd, cfg.tau_motor)
            )

    idx = np.unravel_index(
        np.argmax(np.where(stable > 0, margin, -np.inf)),
        margin.shape,
    )

    return dict(
        kp_grid=kp_grid,
        kd_grid=kd_grid,
        stable_map=stable,
        margin_map=margin,
        best_kp=float(kp_grid[idx[0]]),
        best_kd=float(kd_grid[idx[1]]),
        ki=cfg.ki,
    )


# ---------------------------------------------------------------------------
# Sweeps
# ---------------------------------------------------------------------------
SimulateFn = Callable[..., dict]


def robustness_sweep(
    simulate_fn: SimulateFn,
    loss_levels: Iterable[float] = (0, .5, 1, 1.5, 2, 2.5, 3),
    runs_per_level: int = 5,
    base_seed: int = 300,
    mode: str = "advanced",
) -> np.ndarray:
    """Columns: [RMSE, peak error, min separation, packet loss %] per level."""
    rows = []

    for scale in loss_levels:
        vals = []

        for s in range(runs_per_level):
            h = simulate_fn(mode, base_seed + s, loss_scale=scale)
            vals.append([
                np.sqrt(np.mean(h["formation_rms"] ** 2)),
                np.max(h["formation_rms"]),
                np.min(h["min_distance"]),
                np.mean(h["packet_drop"]) * 100,
            ])

        rows.append(np.mean(vals, axis=0))

    return np.array(rows)


def monte_carlo(
    simulate_fn: SimulateFn,
    runs: int = 30,
    mode: str = "advanced",
    base_seed: int = 1000,
) -> np.ndarray:
    """Columns: [RMSE, peak, min separation, packet loss %, control effort]."""
    out = []

    for s in range(runs):
        loss = np.random.default_rng(5000 + s).uniform(.6, 2.8)
        sigma = np.random.default_rng(6000 + s).uniform(.015, .07)

        h = simulate_fn(
            mode,
            base_seed + s,
            loss_scale=loss,
            sensor_sigma=sigma,
        )

        out.append([
            np.sqrt(np.mean(h["formation_rms"] ** 2)),
            np.max(h["formation_rms"]),
            np.min(h["min_distance"]),
            np.mean(h["packet_drop"]) * 100,
            np.mean(h["control_effort"]),
        ])

    return np.array(out)


def summarize_monte_carlo(results: np.ndarray) -> Dict[str, float]:
    return dict(
        mean_rmse=float(results[:, 0].mean()),
        p95_rmse=float(np.percentile(results[:, 0], 95)),
        worst_peak=float(results[:, 1].max()),
        worst_min_separation=float(results[:, 2].min()),
        mean_packet_loss=float(results[:, 3].mean()),
        mean_effort=float(results[:, 4].mean()),
    )
