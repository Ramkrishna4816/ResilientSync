"""Metrics, comparison and plots from run directories (identical for Webots and stand-in runs).

Metric formulas are the Python benchmark's own (`simulation.metrics.compute_metrics`,
`compute_recovery_metrics`), applied to the logged ground-truth formation error.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from simulation.metrics import compute_recovery_metrics
from simulation.supervisor import STATE_NAMES

STATE_LABELS = {i: n for i, n in enumerate(STATE_NAMES)}     # 0 NORMAL 1 DEGRADED 2 HOLD 3 RECOVERING


def load_run(d) -> dict:
    d = Path(d)
    out = {"dir": d, "steps": pd.read_csv(d / "steps.csv"),
           "meta": json.loads((d / "meta.json").read_text()),
           "transitions": json.loads((d / "transitions.json").read_text()),
           "faults": json.loads((d / "faults.json").read_text())}
    for name in ("comm_events", "deliveries"):
        p = d / f"{name}.csv"
        out[name] = pd.read_csv(p) if p.exists() and p.stat().st_size else pd.DataFrame()
    return out


def _events(mask: np.ndarray) -> int:
    m = np.asarray(mask, bool)
    return int(m[0]) + int(np.sum(m[1:] & ~m[:-1])) if len(m) else 0


def follower_ids(df) -> List[int]:
    return sorted(int(c.split("_")[-1]) for c in df.columns if c.startswith("true_slot_err_"))


def run_metrics(run: dict) -> dict:
    df, meta = run["steps"], run["meta"]
    t, e, ms = df["t"].to_numpy(), df["formation_rms"].to_numpy(), df["min_sep"].to_numpy()
    fids = follower_ids(df)
    cd = meta.get("collision_distance_m", 0.38)
    m = {"run_id": Path(run["dir"]).name, **{k: meta["spec"][k] for k in ("scenario", "arm", "seed", "plant")},
         "status": meta["status"], "steps": len(df), "duration_s": float(t[-1]) if len(t) else 0.0,
         "RMSE": float(np.sqrt(np.mean(e ** 2))), "Peak": float(e.max()), "MinSep": float(ms.min()),
         "collision_pct": float(np.mean(ms < cd) * 100), "collision_events": _events(ms < cd),
         "max_time_skew_s": meta.get("max_time_skew_s")}
    # recovery: same rule as the benchmark (finite window, >=1 s of baseline, >=0.5 s after)
    win = meta.get("scenario_window")
    m.update(recovery_status="not_applicable", recovered=None, recovery_time_s=None)
    if win and win[0] >= 1.0 and win[1] < m["duration_s"] - 0.5 and meta["status"] == "completed":
        r = compute_recovery_metrics(t, e, win[0], win[1])
        m.update(recovery_status="recovered" if r["recovered"] else "not_recovered", recovered=bool(r["recovered"]),
                 recovery_time_s=r["recovery_time_s"], recovery_baseline_m=r["recovery_baseline_m"],
                 recovery_threshold_m=r["recovery_threshold_m"], post_fault_min_error_m=r["post_blackout_min_error_m"])
    # actuators
    sat = np.stack([df[f"sat_{i}"].to_numpy() for i in range(len(fids) + 1)], 1)
    m["saturated_samples"] = int(sat.sum())
    # communication (per follower, from the logged counters)
    sent = sum(df[f"sent_{i}"].iloc[-1] for i in fids); lost = sum(df[f"lost_{i}"].iloc[-1] for i in fids)
    m.update(pose_sent=int(sent), pose_lost=int(lost), pose_loss_pct=100.0 * lost / sent if sent else 0.0,
             max_age_s=float(max(df[f"age_{i}"].max() for i in fids)),
             mean_age_s=float(np.mean([df[f"age_{i}"].mean() for i in fids])))
    # supervisor
    if meta.get("supervisor_active"):
        codes = np.stack([df[f"sup_state_{i}"].to_numpy() for i in fids], 1)
        for c, nme in STATE_LABELS.items():
            m[f"frac_{nme}"] = float(np.mean(codes == c))
        m["states_reached"] = ",".join(n for c, n in STATE_LABELS.items() if (codes == c).any())
        m["transitions"] = len(run["transitions"])
        # first time ALL followers are back in NORMAL after the fault window
        if win:
            after = (t >= win[1])
            allnorm = (codes == 0).all(axis=1) & after
            idx = np.flatnonzero(allnorm)
            m["time_to_all_normal_s"] = float(t[idx[0]] - win[1]) if len(idx) else None
    else:
        m["states_reached"] = "n/a (no supervisor in this arm)"
    return m


def python_reference(scenario, arm, seed, duration=18.0, n_agents=5) -> dict:
    """Native Python simulator run (the existing engine, its own plant) with matched seed/scenario."""
    from simulation.metrics import compute_metrics
    from simulation.simulation import MultiAgentSimulation
    cfg = arm.build_cfg().copy(n_agents=n_agents)
    sim = MultiAgentSimulation(cfg=cfg, control_mode=arm.mode, seed=seed, record_history=True,
                               fault_profile=scenario.profile, leader_trajectory=scenario.trajectory)
    sim.run(duration)
    h = sim.history()
    m = compute_metrics(h)
    out = {k: m[k] for k in ("RMSE", "Peak", "MinSep", "Collision")}
    win = scenario.window
    if win and win[0] >= 1.0 and win[1] < duration - 0.5:
        r = compute_recovery_metrics(h["t"], h["formation_rms"], win[0], win[1])
        out.update(recovered=bool(r["recovered"]), recovery_time_s=r["recovery_time_s"])
    out["t"], out["formation_rms"] = h["t"], h["formation_rms"]
    return out


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------
def _shade(ax, faults):
    labelled = False
    for ev in faults["profile"]["events"]:
        end = ev["end"] if ev["end"] is not None else ax.get_xlim()[1]
        ax.axvspan(ev["start"], end, color="tab:red" if ev["kind"] == "blackout" else "tab:orange",
                   alpha=0.15, label=None if labelled else "injected fault", lw=0)
        labelled = True
        ax.axvline(ev["start"], color="k", ls="--", lw=0.8)
        ax.axvline(end, color="k", ls=":", lw=0.8)


def plot_run(run: dict, out_png) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    df, meta = run["steps"], run["meta"]
    t = df["t"].to_numpy()
    fids = follower_ids(df)
    n = len(fids) + 1
    fig, ax = plt.subplots(3, 2, figsize=(14, 12))
    plant = meta["spec"]["plant"].upper()
    fig.suptitle(f"{Path(run['dir']).name}   [plant: {plant}]", fontsize=12)

    a = ax[0, 0]
    for i in range(n):
        a.plot(df[f"gt_x_{i}"], df[f"gt_y_{i}"], lw=1.4, label="Leader" if i == 0 else f"F{i}")
        a.plot(df[f"gt_x_{i}"].iloc[0], df[f"gt_y_{i}"].iloc[0], "o", ms=4, color=a.lines[-1].get_color())
    a.set_aspect("equal"); a.set_title("Ground-truth trajectories (x-y), dots = start"); a.legend(fontsize=7); a.grid(alpha=.3)

    a = ax[0, 1]
    for i in fids:
        a.plot(t, df[f"true_slot_err_{i}"], lw=0.9, label=f"F{i}")
    a.plot(t, df["formation_rms"], "k", lw=1.8, label="formation RMS")
    a.set_title("Formation error vs time (ground truth)"); a.set_ylabel("m"); _shade(a, run["faults"]); a.legend(fontsize=7, ncol=3)

    a = ax[1, 0]
    a.plot(t, df["min_sep"], lw=1.4)
    a.axhline(meta.get("collision_distance_m", 0.38), color="r", ls="--", label="collision threshold")
    a.set_title("Minimum inter-robot separation (centre-to-centre)"); a.set_ylabel("m"); _shade(a, run["faults"]); a.legend(fontsize=7)

    a = ax[1, 1]
    for i in fids:
        a.plot(t, df[f"age_{i}"], lw=0.9, label=f"age F{i}")
    a2 = a.twinx()
    loss = np.mean([df[f"lost_{i}"].diff().fillna(0).rolling(20, min_periods=1).mean() for i in fids], axis=0)
    a2.plot(t, loss, "k--", lw=1.2, label="pose loss (20-tick mean)"); a2.set_ylim(0, 1.05); a2.set_ylabel("loss fraction")
    a.set_title("Communication: message age (solid) and measured loss (dashed)"); a.set_ylabel("age [s]"); _shade(a, run["faults"]); a.legend(fontsize=7, loc="upper left")

    a = ax[2, 0]
    if meta.get("supervisor_active"):
        for k, i in enumerate(fids):
            a.step(t, df[f"sup_state_{i}"] + 0.06 * k, where="post", lw=1, label=f"F{i}")
        a.set_yticks(range(4)); a.set_yticklabels(STATE_NAMES)
        a.legend(fontsize=7, ncol=4)
    else:
        a.text(0.5, 0.5, "no supervisor in this controller arm", ha="center", transform=a.transAxes)
    a.set_title("Supervisor state per follower (offset for visibility)"); _shade(a, run["faults"])

    a = ax[2, 1]
    a.plot(t, df["cmd_v_0"], label="leader v cmd"); a.plot(t, df["cmd_v_1"], label="F1 v cmd")
    a.plot(t, df["wheel_l_1"] * 0.0975, ":", label="F1 left wheel (m/s)"); a.plot(t, df["wheel_r_1"] * 0.0975, ":", label="F1 right wheel (m/s)")
    s = df[[f"sat_{i}" for i in range(n)]].sum(axis=1) > 0
    if s.any():
        a.plot(t[s], np.zeros(s.sum()), "rx", label="wheel saturation")
    a.set_title("Velocity / wheel commands"); a.set_xlabel("t [s]"); _shade(a, run["faults"]); a.legend(fontsize=7, ncol=2)
    for x in ax.ravel():
        if x is not ax[0, 0]:
            x.set_xlabel("t [s]"); x.grid(alpha=.3)
    fig.tight_layout(); out_png = Path(out_png); fig.savefig(out_png, dpi=110); plt.close(fig)
    return out_png


def plot_trajectory_3d(run: dict, out_png) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    df = run["steps"]; n = len(follower_ids(df)) + 1
    fig = plt.figure(figsize=(9, 7)); ax = fig.add_subplot(111, projection="3d")
    for i in range(n):
        ax.plot(df[f"gt_x_{i}"], df[f"gt_y_{i}"], df["t"], lw=1.3, label="Leader" if i == 0 else f"F{i}")
    for ev in run["faults"]["profile"]["events"]:
        for tt in (ev["start"], ev["end"]):
            if tt is not None:
                ax.plot([df["gt_x_0"].min()] * 2, [df["gt_y_0"].min()] * 2, [tt, tt], "k:", lw=.5)
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.set_zlabel("t [s]")
    ax.set_title(f"Space-time trajectories  [plant: {run['meta']['spec']['plant'].upper()}]"); ax.legend(fontsize=7)
    fig.tight_layout(); out_png = Path(out_png); fig.savefig(out_png, dpi=110); plt.close(fig)
    return out_png
