"""Diagnose ONE run directory: did the robots really move, did the pipeline behave?

Implements the "verify the robot motion" checklist.  Works on Webots and stand-in runs; a
stand-in run is reported as such and can never be mistaken for Webots evidence.
Levels: PASS / INFO / WARN / FAIL.  Verdict = worst level (INFO/PASS -> OK).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

DT = 0.05
V_MAX = 1.25


def _n_robots(df):
    return len([c for c in df.columns if c.startswith("gt_x_")])


def native_leader_path(scenario_name: str, arm_name: str, seed: int, duration: float, n: int) -> np.ndarray:
    """Leader (x, y) per tick in the NATIVE Python simulator (same seed/scenario)."""
    from experiments.run_benchmark import ARMS
    from simulation.simulation import MultiAgentSimulation
    from .faults import load_scenarios
    sc, arm = load_scenarios()[scenario_name], ARMS[arm_name]
    sim = MultiAgentSimulation(cfg=arm.build_cfg().copy(n_agents=n), control_mode=arm.mode, seed=seed,
                               fault_profile=sc.profile, leader_trajectory=sc.trajectory)
    out = []
    for _ in range(int(round(duration / DT))):
        out.append(sim.states()[0, :2].copy())
        sim.step()
    return np.array(out)


def diagnose(run_dir, with_native_reference: bool = True) -> dict:
    d = Path(run_dir)
    checks = []

    def add(level, cid, msg, value=None):
        checks.append({"level": level, "id": cid, "msg": msg, "value": value})

    for f in ("meta.json", "steps.csv", "comm_events.csv", "deliveries.csv", "transitions.json", "faults.json"):
        if not (d / f).exists():
            add("FAIL", "files", f"missing {f}")
    if (d / "coordinator_error.txt").exists():
        add("FAIL", "coordinator_error", "coordinator_error.txt present:\n" + (d / "coordinator_error.txt").read_text()[-1500:])
    if not (d / "meta.json").exists() or not (d / "steps.csv").exists():
        return _finish(d, checks)
    meta = json.loads((d / "meta.json").read_text())
    df = pd.read_csv(d / "steps.csv")
    spec = meta["spec"]
    n = _n_robots(df)
    add("INFO", "plant", f"plant={spec['plant']}  scenario={spec['scenario']}  arm={spec['arm']}  seed={spec['seed']}  robots={n}")
    if spec["plant"] != "webots":
        add("WARN", "not_webots", "this run used the STAND-IN plant; it is not Webots evidence")
    elif meta.get("webots_version"):
        add("INFO", "webots_version", f"Webots {meta['webots_version']}, basicTimeStep {meta.get('basic_time_step_ms')} ms")
    add("PASS" if meta["status"] == "completed" else "FAIL", "status", f"run status = {meta['status']} {meta.get('error') or ''}")

    # --- clock -------------------------------------------------------------
    exp = int(round(spec["duration_s"] / DT))
    add("PASS" if len(df) == exp else "FAIL", "steps", f"{len(df)} ticks logged, expected {exp}")
    dts = np.diff(df.t.to_numpy())
    add("PASS" if len(dts) and np.allclose(dts, DT, atol=1e-6) else "FAIL", "tick", f"engine tick spacing {dts.min():.4f}-{dts.max():.4f} s" if len(dts) else "no ticks")
    skew = np.abs(df.t_plant.to_numpy() - df.t.to_numpy())
    off = float(np.median(df.t_plant - df.t))
    sk = float(np.max(np.abs(df.t_plant - df.t - off)))
    add("PASS" if sk < 0.005 else "WARN" if sk < 0.025 else "FAIL", "clock_sync",
        f"plant clock vs engine clock: constant offset {off:+.3f} s, drift/jitter max {sk*1000:.1f} ms; meta max_time_skew {meta.get('max_time_skew_s')}", sk)

    # --- finite values -----------------------------------------------------
    num = df.select_dtypes("number")
    bad_cols = [c for c in num.columns if not np.isfinite(num[c]).all() and not c.startswith("loss_est")]
    add("FAIL" if bad_cols else "PASS", "finite", f"non-finite values in {bad_cols[:6]}" if bad_cols else "all logged values finite")

    X = np.stack([df[f"gt_x_{i}"] for i in range(n)], 1)
    Y = np.stack([df[f"gt_y_{i}"] for i in range(n)], 1)
    names = ["leader"] + [f"follower {i}" for i in range(1, n)]

    # --- motion ------------------------------------------------------------
    for i in range(n):
        disp = float(math.hypot(X[-1, i] - X[0, i], Y[-1, i] - Y[0, i]))
        need = 1.0 if i == 0 else 0.5
        add("PASS" if disp >= need else "FAIL", f"moved_{i}", f"{names[i]} net displacement {disp:.2f} m", disp)
    jump = np.hypot(np.diff(X, axis=0), np.diff(Y, axis=0))
    mj = float(jump.max()) if len(jump) else 0.0
    where = np.unravel_index(np.argmax(jump), jump.shape) if len(jump) else (0, 0)
    add("PASS" if mj < 0.2 else "FAIL", "teleport", f"largest one-tick jump {mj:.3f} m ({names[where[1]]} at t={df.t.iloc[where[0]]:.2f} s); physical max ~{V_MAX*DT:.3f} m", mj)
    for i in range(n):
        # smoothed over 0.5 s: follower commands chatter tick-to-tick, so an instantaneous test would miss a frozen robot
        cmd_sm = df[f"cmd_v_{i}"].abs().rolling(10, min_periods=1).mean()
        spd_sm = df[f"gt_v_{i}"].abs().rolling(10, min_periods=1).mean()
        slow = (spd_sm < 0.02) & (cmd_sm > 0.2)
        run = best = 0
        for s in slow.to_numpy():
            run = run + 1 if s else 0; best = max(best, run)
        if best * DT >= 2.0:
            add("FAIL", f"frozen_{i}", f"{names[i]} commanded to move but stationary for {best*DT:.1f} s (frozen wheels / blocked?)")
    # --- does the command reach the motion? ---------------------------------
    m = df.t > 1.0
    cl, gl = df.loc[m, "cmd_v_0"].mean(), df.loc[m, "gt_v_0"].mean()
    ratio = gl / cl if abs(cl) > 1e-6 else float("nan")
    add("PASS" if 0.8 <= ratio <= 1.2 else "WARN" if 0.5 <= ratio <= 1.5 else "FAIL", "leader_tracking_ratio",
        f"leader mean measured speed / commanded speed = {ratio:.3f}", ratio)
    for i in range(1, n):
        a, b = df[f"cmd_v_{i}"].to_numpy()[:-2], df[f"gt_v_{i}"].to_numpy()[2:]
        c = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else float("nan")
        add("PASS" if c > 0.3 else "WARN", f"cmd_to_motion_{i}", f"{names[i]} corr(commanded v, measured v two ticks later) = {c:.2f}", c)
    # --- wheels / actuators --------------------------------------------------
    sat = int(sum(df[f"sat_{i}"].sum() for i in range(n)))
    add("PASS" if sat == 0 else "WARN", "saturation", f"{sat} wheel-saturation samples")
    dv = float(np.mean([np.abs(np.diff(df[f"cmd_v_{i}"])).mean() for i in range(1, n)]))
    dw = float(np.mean([np.abs(np.diff(df[f"cmd_w_{i}"])).mean() for i in range(1, n)]))
    add("WARN" if dv > 0.3 else "INFO", "command_chatter", f"mean |dv| per tick {dv:.2f} m/s, |dw| {dw:.2f} rad/s (stand-in runs were ~0.58 / 1.85)", dv)
    # --- height / tilt (caster check) ---------------------------------------
    if "pitch_0" in df.columns:
        tilt = max(float(np.degrees(np.abs(df[[f"{k}_{i}" for i in range(n) for k in ("roll", "pitch")]]).max().max())), 0.0)
        z = np.stack([df[f"gt_z_{i}"] for i in range(n)], 1)
        zdev = float(np.abs(z - 0.0975).max())
        add("PASS" if tilt < 3 else "WARN" if tilt < 10 else "FAIL", "tilt", f"max |roll|,|pitch| = {tilt:.1f} deg (0 expected on flat floor)", tilt)
        add("PASS" if zdev < 0.01 else "WARN" if zdev < 0.03 else "FAIL", "height", f"max |z - 0.0975| = {zdev*1000:.1f} mm (axle height; larger = sinking/lifting/tipping)", zdev)
    else:
        add("WARN", "tilt", "no tilt/height columns in this log (run was produced before tilt logging existed)")
    # --- leader vs native reference -------------------------------------------
    if with_native_reference:
        try:
            ref = native_leader_path(spec["scenario"], spec["arm"], spec["seed"], spec["duration_s"], n)[:len(df)]
            dev = np.hypot(X[:len(ref), 0] - ref[:, 0], Y[:len(ref), 0] - ref[:, 1])
            add("PASS" if dev.max() < 0.5 else "WARN" if dev.max() < 1.5 else "FAIL", "leader_vs_reference",
                f"leader deviates from the native-simulator reference path by max {dev.max():.2f} m, final {dev[-1]:.2f} m", float(dev.max()))
        except Exception as e:
            add("WARN", "leader_vs_reference", f"could not compute native reference: {type(e).__name__}: {e}")
    # --- formation + comms ------------------------------------------------------
    e = df.formation_rms.to_numpy()
    add("INFO", "formation", f"formation RMS: overall {np.sqrt(np.mean(e**2)):.3f} m, peak {e.max():.3f} m, last 2 s {np.sqrt(np.mean(e[-40:]**2)):.3f} m, min separation {df.min_sep.min():.2f} m")
    win = meta.get("scenario_window")
    if win and (d / "deliveries.csv").exists():
        dl = pd.read_csv(d / "deliveries.csv")
        prof = json.loads((d / "faults.json").read_text())["profile"]["events"]
        if any(ev["kind"] == "blackout" for ev in prof):
            acc = dl[dl.accepted]
            inside = acc[(acc.t_delivered > win[0] + 0.5) & (acc.t_delivered < win[1])]
            add("PASS" if len(inside) == 0 else "FAIL", "blackout_effective", f"{len(inside)} accepted deliveries during the blackout (0 expected)", len(inside))
            after = acc[acc.t_delivered >= win[1]]
            add("PASS" if len(after) else "FAIL", "restoration", f"deliveries resume at t={after.t_delivered.min():.2f} s" if len(after) else "no delivery after blackout")
    tr = json.loads((d / "transitions.json").read_text()) if (d / "transitions.json").exists() else []
    if meta.get("supervisor_active"):
        codes = np.unique(np.stack([df[f"sup_state_{i}"] for i in range(1, n)]))
        add("INFO", "supervisor_states", f"states reached: {[['NORMAL','DEGRADED','HOLD','RECOVERING'][int(c)] for c in codes]}; {len(tr)} transitions")
    return _finish(d, checks)


def _finish(d, checks):
    order = {"PASS": 0, "INFO": 0, "WARN": 1, "FAIL": 2}
    worst = max((order[c["level"]] for c in checks), default=2)
    res = {"run_dir": str(d), "verdict": ["OK", "WARN", "FAIL"][worst], "checks": checks}
    try:
        (d / "diagnosis.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    except OSError:
        pass
    return res
