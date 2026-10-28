"""Reproducible resilience benchmark (matched seeds, fault scenarios, ablation).

    python -m experiments.run_benchmark                         # full evaluation
    python -m experiments.run_benchmark --quick                 # fast smoke run
    python -m experiments.run_benchmark --seeds 42 43 --scenarios blackout_3s \
                                        --arms pidr adaptive_supervisor

Every (arm, scenario, seed) triple is one simulation.  For a given seed and
scenario all arms start from the same initial conditions, use the same
channel RNG streams and see the same fault schedule, so differences between
arms are paired differences.

Outputs go to  experiments/results_resilience/<tag>/  (never to
experiments/results/, which holds the original baseline):

    per_run.csv      one row per run (arm, scenario, seed, metrics, status)
    aggregate.csv    mean / std / n per (scenario, arm, metric)
    summary.json     configuration, aggregates, paired ablation statistics
    report.md        machine-generated report (strengths / weaknesses / trade-offs)
    plots/*.png      formation error + supervisor timeline per scenario

This script does not assume any controller wins; the report is generated
from the measured numbers only.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import math
import platform
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

from simulation.config import Config
from simulation.connectivity import ConsensusTolerance, first_sustained_time, summarize_series
from simulation.controller import auto_leader_command
from simulation.metrics import compute_metrics, compute_recovery_metrics
from simulation.network import FaultEvent, FaultProfile, make_fault_profile
from simulation.simulation import MultiAgentSimulation
from simulation.supervisor import STATE_NAMES, SupervisorConfig

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "experiments" / "results_resilience"

EVAL_SEEDS = list(range(42, 52))          # held-out evaluation seeds
TUNING_SEEDS = list(range(100, 110))      # used ONLY for choosing supervisor defaults
DURATION = 18.0


# ---------------------------------------------------------------------------
# Leader trajectories (module level -> picklable for worker processes)
# ---------------------------------------------------------------------------
def maneuver_trajectory(t: float) -> np.ndarray:
    """AUTO trajectory with an abrupt stop (5.5-6.5 s) then a sharp turn
    (6.5-7.5 s): dead reckoning of the stale leader pose is wrong exactly when
    communication is down."""
    v, w = auto_leader_command(t)
    if 5.5 <= t < 6.5:
        return np.array([0.0, 0.0])
    if 6.5 <= t < 7.5:
        return np.array([0.4, 1.2])
    return np.array([v, w])


def gentle_trajectory(t: float) -> np.ndarray:
    """Low-curvature leader path (v = 0.8 m/s, |omega| <= 0.1 rad/s).

    Added BEFORE any results were inspected, as a feasibility control: with the
    default AUTO path the outer wedge slots need more than max_v (the nominal
    formation error is already ~1.5 m), so sustained recovery to a tight band
    cannot be expected in any arm.  Verified afterwards: pidr RMSE 0.07 m on this path vs
    1.49 m on the default path (docs/EXPERIMENT_PROTOCOL.md, 'Audit findings').
    """
    return np.array([0.8, 0.1 * np.sin(0.24 * t)])


# ---------------------------------------------------------------------------
# Arms (controller configurations)
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Arm:
    name: str
    mode: str
    description: str
    cfg_overrides: dict = dataclasses.field(default_factory=dict)
    sup_overrides: dict = dataclasses.field(default_factory=dict)
    uses_supervisor: bool = False

    def build_cfg(self) -> Config:
        cfg = Config(**self.cfg_overrides)
        if self.sup_overrides:
            cfg = cfg.copy(supervisor=dataclasses.replace(cfg.supervisor, **self.sup_overrides))
        return cfg


ARMS: Dict[str, Arm] = {a.name: a for a in [
    Arm("zoh", "zoh", "zero-order hold of the last leader packet (baseline)"),
    Arm("pidr", "pidr", "PID + dead-reckoning of the leader (baseline)"),
    Arm("advanced", "advanced", "PIDR + neighbour coupling + avoidance + gain scheduling (baseline)"),
    Arm("adaptive_capped", "adaptive_comm",
        "adaptive_comm, no supervisor, TOTAL speed cap (the earlier prototype, kept for the "
        "discrepancy record)", {"supervisor_enabled": False, "adaptive_comm_total_speed_cap": True}),
    Arm("adaptive_legacy", "adaptive_comm",
        "adaptive_comm, no supervisor (quality-threshold feed-forward scaling only)",
        {"supervisor_enabled": False}),
    Arm("adaptive_supervisor", "adaptive_comm",
        "adaptive_comm + resilience supervisor (default fallback)", {}, {}, True),
    Arm("sup_observe_only", "adaptive_comm",
        "supervisor runs but all caution modifiers are neutral (ablation control)",
        {}, {"hold_ff_scale": 1.0, "hold_speed_frac": 1.0, "hold_avoid_scale": 1.0}, True),
    Arm("sup_no_ff", "adaptive_comm", "supervisor without feed-forward scaling",
        {}, {"hold_ff_scale": 1.0}, True),
    Arm("sup_speedlimit", "adaptive_comm",
        "supervisor + HOLD speed limit of 0.8 x max speed (the first design; measured harmful)",
        {}, {"hold_speed_frac": 0.8}, True),
    Arm("sup_no_avoid", "adaptive_comm", "supervisor without avoidance boost",
        {}, {"hold_avoid_scale": 1.0}, True),
]}
DEFAULT_ARMS = ["zoh", "pidr", "advanced", "adaptive_legacy", "adaptive_capped",
                "adaptive_supervisor", "sup_observe_only", "sup_no_ff",
                "sup_speedlimit", "sup_no_avoid"]


# ---------------------------------------------------------------------------
# Scenarios (fault schedule + optional leader trajectory)
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    profile: FaultProfile
    trajectory: Optional[Callable] = None

    @property
    def window(self):
        """(start, end) of the disturbance used for recovery metrics, or None."""
        evs = [e for e in self.profile.events if math.isfinite(e.end)]
        if not evs:
            return None
        return min(e.start for e in evs), max(e.end for e in evs)


SCENARIOS: Dict[str, Scenario] = {s.name: s for s in [
    Scenario("nominal", "no injected fault (default channel only)", make_fault_profile("none")),
    Scenario("blackout_3s", "3 s total blackout at t=5 s (the original benchmark)",
             make_fault_profile("blackout", 5.0, 3.0)),
    Scenario("blackout_6s", "6 s total blackout at t=4 s", make_fault_profile("blackout", 4.0, 6.0)),
    Scenario("blackout_maneuver",
             "3 s blackout at t=5 s while the leader stops and turns abruptly",
             make_fault_profile("blackout", 5.0, 3.0), maneuver_trajectory),
    Scenario("random_loss_30", "independent 30 % extra packet loss, t=4-12 s",
             make_fault_profile("random_loss", 4.0, 8.0, probability=0.30)),
    Scenario("burst_loss", "correlated burst loss (mean ~50 %, mean burst ~6.7 packets), t=4-12 s",
             make_fault_profile("burst_loss", 4.0, 8.0, p_good_to_bad=0.15, p_bad_to_good=0.15)),
    Scenario("latency_jitter", "+0.4 s latency with +-0.2 s jitter, t=4-12 s",
             make_fault_profile("latency_jitter", 4.0, 8.0, extra_latency_s=0.4, jitter_s=0.2)),
    Scenario("latency_then_blackout", "+0.3 s latency/jitter for 3 s then a 3 s blackout (t=3-9 s)",
             make_fault_profile("blackout_latency", 3.0, 3.0, extra_latency_s=0.3, jitter_s=0.15)),
    Scenario("nominal_gentle", "no fault, low-curvature leader path (feasibility control)",
             make_fault_profile("none"), gentle_trajectory),
    Scenario("blackout_gentle", "3 s blackout at t=5 s, low-curvature leader path (feasibility control)",
             make_fault_profile("blackout", 5.0, 3.0), gentle_trajectory),
]}
DEFAULT_SCENARIOS = list(SCENARIOS)

# metric name -> (direction, label); direction +1 higher better, -1 lower better
METRICS = {
    "RMSE": (-1, "formation RMSE [m]"),
    "Peak": (-1, "peak formation error [m]"),
    "MinSep": (+1, "minimum separation [m]"),
    "Collision": (-1, "collision samples [%]"),
    "collision_events": (-1, "collision events [count]"),
    "post_fault_min_error_m": (-1, "post-fault minimum error [m]"),
    "final_error_m": (-1, "final formation error [m]"),
    "recovery_time_s": (-1, "recovery time [s] (recovered runs only)"),
    "cmd_dv_mean": (-1, "mean |dv_cmd| per step [m/s]"),
    "cmd_dw_mean": (-1, "mean |dw_cmd| per step [rad/s]"),
    "Effort": (-1, "mean control effort"),
    "conn_interruption_s": (-1, "connectivity interruption [s]"),
    "isolated_s_max": (-1, "max isolated time of one follower [s]"),
    "conn_restore_lag_s": (-1, "connectivity restoration lag after fault end [s]"),
    "lambda2_min": (+1, "min algebraic connectivity"),
    "heading_rms_mean": (-1, "mean heading disagreement [rad]"),
    "heading_rms_max": (-1, "max heading disagreement [rad]"),
    "consensus_frac": (+1, "fraction of time in heading consensus"),
    "consensus_time_s": (-1, "time to sustained heading consensus [s]"),
    "sat_frac": (-1, "fraction of follower commands at the speed limit (includes derivative-noise chatter)"),
}


# ---------------------------------------------------------------------------
# One run
# ---------------------------------------------------------------------------
def count_events(flags: np.ndarray) -> int:
    flags = np.asarray(flags, bool)
    if flags.size == 0:
        return 0
    return int(flags[0]) + int(np.sum(flags[1:] & ~flags[:-1]))


def run_one(arm_name: str, scenario_name: str, seed: int, duration: float = DURATION,
            keep_series: bool = False) -> dict:
    """Run one simulation; never raises (failures become a `run_status` row)."""
    arm, sc = ARMS[arm_name], SCENARIOS[scenario_name]
    row: dict = {"arm": arm_name, "mode": arm.mode, "scenario": scenario_name,
                 "fault_profile": sc.profile.name, "seed": seed, "duration_s": duration,
                 "run_status": "ok", "error": ""}
    try:
        cfg = arm.build_cfg()
        sim = MultiAgentSimulation(cfg=cfg, control_mode=arm.mode, seed=seed,
                                   record_history=True, fault_profile=sc.profile,
                                   leader_trajectory=sc.trajectory)
        sim.run(duration)
        if sim.halted:
            row.update(run_status="halted", error=str(sim.fault))
        h = sim.history()
        m = compute_metrics(h)
        n_f = cfg.n_agents - 1
        dv = np.abs(np.diff(h["v_cmd"][:, 1:], axis=0)).mean() if len(h["t"]) > 1 else float("nan")
        dw = np.abs(np.diff(h["w_cmd"][:, 1:], axis=0)).mean() if len(h["t"]) > 1 else float("nan")
        row.update({k: m[k] for k in ("RMSE", "Peak", "MinSep", "Collision", "Effort", "Loss")})
        row.update(collision_events=count_events(h["collision"]),
                   cmd_dv_mean=float(dv), cmd_dw_mean=float(dw),
                   mean_quality=float(h["communication_quality"][:, 1:].mean()),
                   min_quality=float(h["communication_quality"][:, 1:].min()),
                   max_message_age_s=float(h["blackout_age"].max()))
        win = sc.window
        rec = dict(recovery_status="not_applicable", recovered=None, recovery_time_s=None,
                   recovery_baseline_m=None, recovery_threshold_m=None,
                   post_fault_min_error_m=None, final_error_m=float(h["formation_rms"][-1]))
        if win is not None and win[0] >= 1.0 and win[1] < duration - 0.5:
            r = compute_recovery_metrics(h["t"], h["formation_rms"], win[0], win[1])
            rec.update(recovery_status="recovered" if r["recovered"] else "not_recovered",
                       recovered=bool(r["recovered"]), recovery_time_s=r["recovery_time_s"],
                       recovery_baseline_m=r["recovery_baseline_m"],
                       recovery_threshold_m=r["recovery_threshold_m"],
                       post_fault_min_error_m=r["post_blackout_min_error_m"],
                       final_error_m=r["final_error_m"])
        row.update(rec)
        # ---- connectivity / consensus / saturation (global diagnostics) ----
        tol = ConsensusTolerance()
        ci = summarize_series(h["t"], h["n_isolated"])
        row.update(conn_interruptions=ci["n_interruptions"],
                   conn_interruption_s=ci["interruption_total_s"],
                   isolated_s_max=float(sim.conn_tracker.summary()["isolated_s_max"]),
                   lambda2_min=float(h["lambda2"].min()),
                   heading_rms_mean=float(h["heading_rms"].mean()),
                   heading_rms_max=float(h["heading_rms"].max()),
                   speed_std_mean=float(h["speed_std"].mean()),
                   sat_frac=float(np.mean(np.abs(h["v_cmd"][:, 1:]) >= cfg.max_v - 1e-9)))
        ivs = ci["interruptions"]
        if win is not None and ivs:
            after = [iv for iv in ivs if iv["end"] is None or iv["end"] > win[0]]
            if after and after[-1]["end"] is not None:
                row.update(conn_status="restored", conn_restore_lag_s=after[-1]["end"] - win[1])
            elif after:
                row.update(conn_status="not_restored", conn_restore_lag_s=None)
            else:
                row.update(conn_status="not_interrupted", conn_restore_lag_s=None)
        else:
            row.update(conn_status="not_interrupted" if not ivs else "interrupted_no_window",
                       conn_restore_lag_s=None)
        ok_c = h["heading_rms"] <= tol.heading_rms_rad
        row["consensus_frac"] = float(ok_c.mean())
        t_c = first_sustained_time(h["t"], ok_c, win[1] if win else 0.0, tol.hold_s)
        row.update(consensus_status="achieved" if t_c is not None else "not_achieved",
                   consensus_time_s=None if t_c is None else t_c - (win[1] if win else 0.0))
        row["fault_start_s"] = None if win is None else win[0]
        row["fault_end_s"] = None if win is None else win[1]
        row["fault_log"] = json.dumps(sim.network.fault_log)
        # supervisor statistics (only meaningful when it actually drove the controller)
        if arm.mode == "adaptive_comm" and cfg.supervisor_enabled:
            sups = list(sim.supervisors.values())
            row["sup_transitions"] = sum(len(s.transitions) for s in sups) / n_f
            for st in STATE_NAMES:
                row[f"sec_{st}"] = sum(s.durations[st] for s in sups) / n_f
            row["sup_hold_entries"] = sum(
                sum(1 for r in s.transitions if r.dst == "HOLD") for s in sups) / n_f
            row["sup_log"] = json.dumps(
                [r.as_dict() for r in sim.supervisors[1].transitions])
        else:
            row["sup_transitions"] = None
            for st in STATE_NAMES:
                row[f"sec_{st}"] = None
            row["sup_hold_entries"] = None
            row["sup_log"] = ""
        if keep_series:
            row["_series"] = {
                "t": h["t"].tolist(), "rms": h["formation_rms"].tolist(),
                "min_dist": h["min_distance"].tolist(),
                "heading_rms": h["heading_rms"].tolist(), "n_isolated": h["n_isolated"].tolist(),
                "sup_state_f1": h["supervisor_state"][:, 1].tolist(),
                "quality_f1": h["communication_quality"][:, 1].tolist()}
    except Exception as exc:                                    # pragma: no cover
        row.update(run_status="failed", error=f"{type(exc).__name__}: {exc}")
    return row


def _job(args):
    return run_one(*args)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def _stats(vals) -> dict:
    v = np.array([x for x in vals if x is not None and np.isfinite(x)], float)
    n = int(v.size)
    return {"n": n,
            "mean": float(v.mean()) if n else None,
            "std": float(v.std(ddof=1)) if n > 1 else (0.0 if n == 1 else None),
            "min": float(v.min()) if n else None, "max": float(v.max()) if n else None}


def aggregate(rows: List[dict]) -> List[dict]:
    out = []
    keys = sorted({(r["scenario"], r["arm"]) for r in rows},
                  key=lambda k: (list(SCENARIOS).index(k[0]), list(ARMS).index(k[1])))
    for sc, arm in keys:
        rs = [r for r in rows if r["scenario"] == sc and r["arm"] == arm]
        ok = [r for r in rs if r["run_status"] == "ok"]
        base = {"scenario": sc, "arm": arm, "runs": len(rs), "ok_runs": len(ok),
                "failed_or_halted": len(rs) - len(ok)}
        rec = [r for r in ok if r["recovery_status"] != "not_applicable"]
        base["recovery_applicable_runs"] = len(rec)
        base["recovered_runs"] = sum(1 for r in rec if r["recovered"])
        base["consensus_reached_runs"] = sum(1 for r in ok if r.get("consensus_status") == "achieved")
        base["conn_restored_runs"] = sum(1 for r in ok if r.get("conn_status") == "restored")
        for m in list(METRICS) + ["mean_quality", "speed_std_mean", "sup_transitions", "sup_hold_entries"] \
                + [f"sec_{s}" for s in STATE_NAMES]:
            st = _stats([r.get(m) for r in ok])
            base[f"{m}_mean"], base[f"{m}_std"], base[f"{m}_n"] = st["mean"], st["std"], st["n"]
        out.append(base)
    return out


def paired_comparison(rows: List[dict], ref: str, other: str, scenario: str, metric: str) -> dict:
    """Paired (same seed) difference other - ref with consistency + significance."""
    a = {r["seed"]: r.get(metric) for r in rows
         if r["arm"] == ref and r["scenario"] == scenario and r["run_status"] == "ok"}
    b = {r["seed"]: r.get(metric) for r in rows
         if r["arm"] == other and r["scenario"] == scenario and r["run_status"] == "ok"}
    seeds = sorted(s for s in a if s in b and a[s] is not None and b[s] is not None
                   and np.isfinite(a[s]) and np.isfinite(b[s]))
    res = {"ref": ref, "other": other, "scenario": scenario, "metric": metric, "n": len(seeds)}
    if len(seeds) < 3:
        res.update(verdict="insufficient_data")
        return res
    d = np.array([b[s] - a[s] for s in seeds])
    direction = METRICS[metric][0] if metric in METRICS else -1
    improved = int(np.sum(d * direction > 1e-12))
    worsened = int(np.sum(d * direction < -1e-12))
    sd = float(d.std(ddof=1))
    res.update(mean_diff=float(d.mean()), std_diff=sd, improved_seeds=improved,
               worsened_seeds=worsened, direction="higher_better" if direction > 0 else "lower_better")
    p_t = p_w = None
    if sd > 1e-15:
        try:
            from scipy import stats
            p_t = float(stats.ttest_rel([b[s] for s in seeds], [a[s] for s in seeds]).pvalue)
            if np.any(np.abs(d) > 1e-15):
                p_w = float(stats.wilcoxon(d).pvalue)
        except Exception:                                       # pragma: no cover
            pass
    res.update(p_ttest=p_t, p_wilcoxon=p_w, cohens_dz=float(d.mean() / sd) if sd > 1e-15 else None)
    better = d.mean() * direction > 0
    consistent = (improved if better else worsened) / len(seeds) >= 0.8
    if np.all(np.abs(d) <= 1e-12):
        res["verdict"] = "identical"
    elif p_t is not None and p_t < 0.05 and consistent:
        res["verdict"] = "better_significant" if better else "worse_significant"
    else:
        res["verdict"] = "better_inconclusive" if better else "worse_inconclusive"
    return res


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def _f(x, nd=3):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x + 0.0:.{nd}f}"


def build_report(meta: dict, agg: List[dict], paired: List[dict], rows: List[dict]) -> str:
    L: List[str] = []
    L.append(f"# Resilience benchmark report — `{meta['tag']}`\n")
    L.append("_Machine-generated from the measured per-run results; no value is edited by hand._\n")
    L.append(f"- seeds ({len(meta['seeds'])}): {meta['seeds']}")
    L.append(f"- duration per run: {meta['duration_s']} s, dt = {meta['config']['dt']} s")
    L.append(f"- arms: {', '.join(meta['arms'])}")
    L.append(f"- scenarios: {', '.join(meta['scenarios'])}")
    nfail = sum(1 for r in rows if r['run_status'] != 'ok')
    L.append(f"- runs: {len(rows)} ({nfail} failed or halted)\n")

    L.append("## Scenario definitions\n")
    for s in meta["scenarios"]:
        L.append(f"- **{s}** — {SCENARIOS[s].description}")
    L.append("\n## Arm definitions\n")
    for a in meta["arms"]:
        L.append(f"- **{a}** — {ARMS[a].description}")

    for sc in meta["scenarios"]:
        L.append(f"\n## Scenario `{sc}` (mean ± std over seeds)\n")
        L.append("| arm | RMSE [m] | peak [m] | min sep [m] | collisions [%] | post-fault min [m] "
                 "| final [m] | recovered | recovery time [s] | transitions | s in HOLD |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in [a for a in agg if a["scenario"] == sc]:
            def ms(k, nd=3):
                return f"{_f(r[k + '_mean'], nd)} ± {_f(r[k + '_std'], nd)}"
            rec = (f"{r['recovered_runs']}/{r['recovery_applicable_runs']}"
                   if r["recovery_applicable_runs"] else "n/a")
            L.append(f"| {r['arm']} | {ms('RMSE')} | {ms('Peak')} | {ms('MinSep')} | "
                     f"{_f(r['Collision_mean'], 2)} | {_f(r['post_fault_min_error_m_mean'])} | "
                     f"{_f(r['final_error_m_mean'])} | {rec} | {_f(r['recovery_time_s_mean'])} "
                     f"(n={r['recovery_time_s_n']}) | {_f(r['sup_transitions_mean'], 1)} | "
                     f"{_f(r['sec_HOLD_mean'], 2)} |")
    L.append("\n### Connectivity, consensus and saturation (global diagnostics)\n")
    L.append("Separate from formation tracking: connectivity = leader->follower links alive; "
             "consensus = RMS heading disagreement <= "
             f"{ConsensusTolerance().heading_rms_rad} rad sustained {ConsensusTolerance().hold_s} s "
             "(measured from fault end, or t=0 without a fault).\n")
    for sc in meta["scenarios"]:
        L.append(f"\n**`{sc}`**\n")
        L.append("| arm | conn. interruption [s] | max isolated [s] | restore lag [s] | min lambda2 "
                 "| heading RMS mean [rad] | in consensus [% time] | consensus reached | "
                 "commands at speed limit [%] |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for r in [a for a in agg if a["scenario"] == sc]:
            cons = f"{r['consensus_reached_runs']}/{r['ok_runs']}"
            L.append(f"| {r['arm']} | {_f(r['conn_interruption_s_mean'], 2)} | "
                     f"{_f(r['isolated_s_max_mean'], 2)} | {_f(r['conn_restore_lag_s_mean'], 2)} "
                     f"(n={r['conn_restore_lag_s_n']}) | {_f(r['lambda2_min_mean'], 2)} | "
                     f"{_f(r['heading_rms_mean_mean'], 3)} | "
                     f"{_f(None if r['consensus_frac_mean'] is None else 100 * r['consensus_frac_mean'], 1)} | "
                     f"{cons} | {_f(None if r['sat_frac_mean'] is None else 100 * r['sat_frac_mean'], 1)} |")
    L.append("\n_Commands at the speed limit_ counts follower ticks with |v_cmd| = max_v. It mixes two causes: "
             "genuine infeasibility (outer wedge slots need more than max_v on the default curved path) and "
             "chatter from the derivative term on noisy error measurements (sensor sigma 0.025 m). "
             "See docs/EXPERIMENT_PROTOCOL.md, section 'Audit findings'.\n")
    L.append("\n`n/a` = metric not applicable (e.g. recovery without a finite fault window, "
             "supervisor statistics for controllers without a supervisor). Recovery time is "
             "averaged over recovered runs only; the recovered column shows how many runs "
             "satisfied the sustained-recovery criterion (unchanged from `simulation/metrics.py`).\n")

    # strengths / weaknesses from data (mean across scenarios of per-scenario means)
    L.append("## Strengths and weaknesses per arm (computed)\n")
    arms = meta["arms"]
    ranks: Dict[str, Dict[str, int]] = {a: {} for a in arms}
    for m in ("RMSE", "Peak", "MinSep", "Collision", "cmd_dv_mean", "cmd_dw_mean", "Effort"):
        vals = {}
        for a in arms:
            xs = [r[f"{m}_mean"] for r in agg if r["arm"] == a and r[f"{m}_mean"] is not None]
            if xs:
                vals[a] = float(np.mean(xs))
        order = sorted(vals, key=lambda a: -METRICS[m][0] * vals[a])
        for i, a in enumerate(order):
            ranks[a][m] = i + 1
    for a in arms:
        best = [f"{METRICS[m][1]} (rank {r}/{len(arms)})" for m, r in ranks[a].items() if r <= 2]
        worst = [f"{METRICS[m][1]} (rank {r}/{len(arms)})" for m, r in ranks[a].items()
                 if r >= len(arms) - 1]
        L.append(f"- **{a}** — strengths: {', '.join(best) or 'none in the top two'}; "
                 f"weaknesses: {', '.join(worst) or 'none in the bottom two'}.")
    L.append("\n_Ranks are by the mean over scenarios of each scenario's seed-mean; they are "
             "descriptive, not significance tests._\n")

    L.append("## Paired comparisons (same seeds, other − reference)\n")
    L.append("Verdict rules: `*_significant` needs paired-t p < 0.05 and ≥ 80 % of seeds moving "
             "in the same direction; otherwise `*_inconclusive`. p-values are uncorrected for "
             f"the {len(paired)} comparisons shown, and n is small — treat them as indicative.\n")
    L.append("| scenario | metric | reference → other | mean diff | improved/worsened seeds | p (t) | p (Wilcoxon) | verdict |")
    L.append("|---|---|---|---|---|---|---|---|")
    for p in paired:
        if p.get("verdict") == "insufficient_data":
            continue
        L.append(f"| {p['scenario']} | {p['metric']} | {p['ref']} → {p['other']} | "
                 f"{_f(p['mean_diff'], 4)} | {p['improved_seeds']}/{p['worsened_seeds']} of {p['n']} | "
                 f"{_f(p['p_ttest'], 4)} | {_f(p['p_wilcoxon'], 4)} | {p['verdict']} |")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------
def make_plots(out: Path, series: Dict[tuple, dict], meta: dict) -> List[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    paths = []
    plots_dir = out / "plots"
    plots_dir.mkdir(exist_ok=True)
    show = [a for a in ("pidr", "advanced", "adaptive_legacy", "adaptive_supervisor")
            if a in meta["arms"]]
    names = ["NORMAL", "DEGRADED", "HOLD", "RECOVERING"]
    for sc in meta["scenarios"]:
        fig, (ax, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 8.2), sharex=True,
                                           gridspec_kw={"height_ratios": [3, 1.2, 1.6]})
        for a in show:
            s = series.get((a, sc))
            if s:
                ax.plot(s["t"], s["rms"], label=a, lw=1.6 if a == "adaptive_supervisor" else 1.1)
        for e in SCENARIOS[sc].profile.events:
            end = min(e.end, meta["duration_s"])
            ax.axvspan(e.start, end, alpha=0.12, color="tab:red" if e.kind == "blackout" else "tab:orange")
            ax2.axvspan(e.start, end, alpha=0.12, color="tab:red" if e.kind == "blackout" else "tab:orange")
            ax3.axvspan(e.start, end, alpha=0.12, color="tab:red" if e.kind == "blackout" else "tab:orange")
        ax.set_ylabel("formation RMS error [m]")
        ax.set_title(f"{sc} — seed {meta['plot_seed']} (shaded = injected fault)")
        ax.grid(alpha=0.3); ax.legend(fontsize=8)
        s = series.get(("adaptive_supervisor", sc))
        if s:
            ax2.step(s["t"], s["sup_state_f1"], where="post", color="k")
            ax2.set_yticks(range(4)); ax2.set_yticklabels(names, fontsize=7)
        ax2.set_ylabel("supervisor\n(follower 1)"); ax2.grid(alpha=0.3)
        for a in show:
            s2 = series.get((a, sc))
            if s2:
                ax3.plot(s2["t"], s2["heading_rms"], label=a, lw=1.0)
        s2 = series.get(("adaptive_supervisor", sc)) or series.get(("pidr", sc))
        if s2:
            ax3b = ax3.twinx()
            ax3b.step(s2["t"], s2["n_isolated"], where="post", color="k", lw=0.8, alpha=0.6)
            ax3b.set_ylabel("isolated\nfollowers (black)", fontsize=7)
        ax3.axhline(ConsensusTolerance().heading_rms_rad, color="gray", ls=":", lw=0.8)
        ax3.set_ylabel("heading RMS\ndisagreement [rad]"); ax3.set_xlabel("time [s]")
        ax3.grid(alpha=0.3)
        fig.tight_layout()
        p = plots_dir / f"timeline_{sc}.png"
        fig.savefig(p, dpi=130); plt.close(fig)
        paths.append(str(p.relative_to(out)))

    # summary bars: RMSE and min separation per scenario/arm
    for metric, ylabel in (("RMSE", "formation RMSE [m]"), ("MinSep", "min separation [m]")):
        fig, ax = plt.subplots(figsize=(11, 4.6))
        scs, arms = meta["scenarios"], [a for a in show if a in meta["arms"]]
        w = 0.8 / max(len(arms), 1)
        for j, a in enumerate(arms):
            means, errs = [], []
            for sc in scs:
                r = next((x for x in meta["_agg"] if x["scenario"] == sc and x["arm"] == a), None)
                means.append(np.nan if r is None or r[f"{metric}_mean"] is None else r[f"{metric}_mean"])
                errs.append(0 if r is None or r[f"{metric}_std"] is None else r[f"{metric}_std"])
            ax.bar(np.arange(len(scs)) + j * w, means, w, yerr=errs, label=a, capsize=2)
        ax.set_xticks(np.arange(len(scs)) + 0.4 - w / 2)
        ax.set_xticklabels(scs, rotation=20, ha="right", fontsize=8)
        ax.set_ylabel(ylabel); ax.grid(axis="y", alpha=0.3); ax.legend(fontsize=8)
        ax.set_title(f"{ylabel}: mean ± std over {len(meta['seeds'])} seeds")
        fig.tight_layout()
        p = plots_dir / f"summary_{metric}.png"
        fig.savefig(p, dpi=130); plt.close(fig)
        paths.append(str(p.relative_to(out)))
    return paths


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def run_benchmark(arms, scenarios, seeds, duration=DURATION, workers=1, tag="run",
                  out_root: Path = OUT_ROOT, plots=True, reference="adaptive_legacy",
                  progress=True, overwrite=False) -> dict:
    if (Path(out_root) / tag / "per_run.csv").exists() and not overwrite:
        raise FileExistsError(
            f"results already exist in {Path(out_root) / tag}; choose another --tag or pass "
            f"--overwrite (historical results are never replaced silently)")
    for a in arms:
        if a not in ARMS:
            raise ValueError(f"unknown arm {a!r}; choose from {list(ARMS)}")
    for s in scenarios:
        if s not in SCENARIOS:
            raise ValueError(f"unknown scenario {s!r}; choose from {list(SCENARIOS)}")
    if duration <= 0 or not seeds:
        raise ValueError("duration must be positive and at least one seed is required")
    plot_seed = seeds[0]
    jobs = [(a, s, seed, duration, plots and seed == plot_seed)
            for s in scenarios for a in arms for seed in seeds]
    if progress:
        print(f"running {len(jobs)} simulations ({len(arms)} arms x {len(scenarios)} scenarios "
              f"x {len(seeds)} seeds, workers={workers}) ...", flush=True)
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            rows = list(ex.map(_job, jobs, chunksize=4))
    else:
        rows = [_job(j) for j in jobs]

    series = {}
    for r in rows:
        s = r.pop("_series", None)
        if s is not None:
            series[(r["arm"], r["scenario"])] = s

    agg = aggregate(rows)
    paired = []
    for sc in scenarios:
        for other, ref in (("adaptive_supervisor", reference), ("adaptive_supervisor", "pidr"),
                           ("adaptive_supervisor", "sup_observe_only"),
                           ("sup_no_ff", "adaptive_supervisor"), ("sup_speedlimit", "adaptive_supervisor"),
                           ("sup_no_avoid", "adaptive_supervisor"), ("adaptive_legacy", "pidr")):
            if other in arms and ref in arms and other != ref:
                for m in ("RMSE", "Peak", "MinSep", "final_error_m", "cmd_dv_mean"):
                    paired.append(paired_comparison(rows, ref, other, sc, m))

    out = Path(out_root) / tag
    out.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0]) if rows else []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with (out / "per_run.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    with (out / "aggregate.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(agg[0]))
        w.writeheader()
        w.writerows(agg)

    cfg0 = Config()
    meta = {
        "tag": tag, "seeds": list(seeds), "arms": list(arms), "scenarios": list(scenarios),
        "duration_s": duration, "plot_seed": plot_seed, "reference_arm": reference,
        "config": dataclasses.asdict(cfg0),
        "arm_definitions": {a: {"mode": ARMS[a].mode, "description": ARMS[a].description,
                                "cfg_overrides": ARMS[a].cfg_overrides,
                                "supervisor_overrides": ARMS[a].sup_overrides} for a in arms},
        "scenario_definitions": {s: {"description": SCENARIOS[s].description,
                                     "profile": SCENARIOS[s].profile.as_dict(),
                                     "custom_leader_trajectory": SCENARIOS[s].trajectory is not None}
                                 for s in scenarios},
        "recovery_criterion": {"function": "simulation.metrics.compute_recovery_metrics",
                               "absolute_tolerance_m": 0.5, "relative_tolerance": 1.25,
                               "sustain_duration_s": 0.5, "baseline_window_s": 1.0},
        "collision_definition": f"min inter-agent distance < {cfg0.collision_distance} m",
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "platform": platform.platform()},
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": " ".join(sys.argv),
    }
    meta["_agg"] = agg
    report = build_report(meta, agg, paired, rows)
    plot_files = make_plots(out, series, meta) if plots else []
    meta.pop("_agg")
    summary = {"meta": meta, "aggregate": agg, "paired": paired,
               "failed_runs": [{k: r[k] for k in ("arm", "scenario", "seed", "run_status", "error")}
                               for r in rows if r["run_status"] != "ok"],
               "plots": plot_files}
    with (out / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=float)
    (out / "report.md").write_text(report, encoding="utf-8")
    if progress:
        print(f"wrote {out}/ (per_run.csv, aggregate.csv, summary.json, report.md"
              f"{', plots/' if plots else ''})")
    return {"out": out, "rows": rows, "aggregate": agg, "paired": paired, "summary": summary}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, nargs="+", default=EVAL_SEEDS)
    ap.add_argument("--arms", nargs="+", default=DEFAULT_ARMS, choices=list(ARMS))
    ap.add_argument("--scenarios", nargs="+", default=DEFAULT_SCENARIOS, choices=list(SCENARIOS))
    ap.add_argument("--duration", type=float, default=DURATION)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--tag", default="eval_v2",
                    help="output folder name under results_resilience/ (default eval_v2; "
                         "'eval' holds the first-round results and is protected)")
    ap.add_argument("--overwrite", action="store_true", help="replace an existing tag")
    ap.add_argument("--out", type=Path, default=OUT_ROOT)
    ap.add_argument("--reference", default="adaptive_legacy", choices=list(ARMS))
    ap.add_argument("--no-plots", action="store_true")
    ap.add_argument("--quick", action="store_true",
                    help="3 seeds, 3 scenarios, 4 arms (smoke test, ~20 s)")
    a = ap.parse_args(argv)
    if a.quick:
        a.seeds, a.tag = a.seeds[:3], (a.tag if a.tag != "eval_v2" else "quick")
        a.scenarios = ["nominal", "blackout_3s", "blackout_maneuver"]
        a.arms = ["pidr", "adaptive_legacy", "adaptive_supervisor", "sup_observe_only"]
    run_benchmark(a.arms, a.scenarios, a.seeds, a.duration, a.workers, a.tag, a.out,
                  not a.no_plots, a.reference, overwrite=a.overwrite)


if __name__ == "__main__":
    main()
