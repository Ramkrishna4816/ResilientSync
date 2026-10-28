"""Aggregate run directories (Webots or stand-in) into metrics tables and plots.

    python scripts/analyze_runs.py --runs results/standin --out results/standin_report [--reference]
--reference also runs the native Python simulator with the SAME scenario/arm/seed for a matched comparison.
"""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from experiments.run_benchmark import ARMS
from resilientsync_webots.analysis import load_run, plot_run, plot_trajectory_3d, python_reference, run_metrics
from resilientsync_webots.faults import load_scenarios

ap = argparse.ArgumentParser()
ap.add_argument("--runs", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--reference", action="store_true")
ap.add_argument("--plot-seed", type=int, default=None, help="seed of the run to plot in detail (default: first)")
a = ap.parse_args()
out = Path(a.out); (out / "plots").mkdir(parents=True, exist_ok=True)
dirs = sorted(p for p in Path(a.runs).iterdir() if (p / "meta.json").exists())
runs = [load_run(d) for d in dirs]
rows = []
for r in runs:
    m = run_metrics(r)
    if a.reference and r["meta"]["status"] == "completed":
        sc = load_scenarios()[m["scenario"]]
        ref = python_reference(sc, ARMS[m["arm"]], m["seed"], r["meta"]["spec"]["duration_s"], r["meta"]["spec"]["n_agents"])
        m.update(py_RMSE=ref["RMSE"], py_MinSep=ref["MinSep"], py_recovered=ref.get("recovered"))
    rows.append(m)
df = pd.DataFrame(rows); df.to_csv(out / "per_run_metrics.csv", index=False)

g = df.groupby(["scenario", "arm"])
agg = g.agg(runs=("seed", "count"), completed=("status", lambda s: int((s == "completed").sum())),
            RMSE_mean=("RMSE", "mean"), RMSE_sd=("RMSE", "std"), Peak_mean=("Peak", "mean"),
            MinSep_min=("MinSep", "min"), collision_runs=("collision_events", lambda s: int((s > 0).sum())),
            saturated_samples=("saturated_samples", "sum"), pose_loss_pct=("pose_loss_pct", "mean"),
            max_age_s=("max_age_s", "max"),
            recovered=("recovered", lambda s: int(s.fillna(False).astype(bool).sum())),
            recovery_applicable=("recovery_status", lambda s: int((s != "not_applicable").sum())),
            recovery_time_mean=("recovery_time_s", "mean")).reset_index()
if "time_to_all_normal_s" in df:
    agg = agg.merge(g["time_to_all_normal_s"].mean().reset_index(), on=["scenario", "arm"], how="left")
if a.reference:
    agg = agg.merge(g.apply(lambda x: float((x.RMSE - x.py_RMSE).mean())).rename("RMSE_minus_python").reset_index(), on=["scenario", "arm"])
agg.to_csv(out / "summary_by_scenario_arm.csv", index=False)
states = df[df.arm == "adaptive_supervisor"].groupby("scenario")["states_reached"].agg(lambda s: sorted(set(",".join(s).split(","))))
(out / "supervisor_states_reached.txt").write_text("\n".join(f"{k}: {v}" for k, v in states.items()) + "\n")

# detailed plots: one run per scenario for the supervisor arm, plus an all-arms overlay
seed0 = a.plot_seed if a.plot_seed is not None else int(df.seed.min())
for r in runs:
    s = r["meta"]["spec"]
    if s["arm"] == "adaptive_supervisor" and s["seed"] == seed0:
        plot_run(r, out / "plots" / f"{Path(r['dir']).name}.png"); plot_trajectory_3d(r, out / "plots" / f"{Path(r['dir']).name}_3d.png")
for sc in sorted(df.scenario.unique()):
    fig, ax = plt.subplots(figsize=(10, 4))
    for r in runs:
        s = r["meta"]["spec"]
        if s["scenario"] == sc and s["seed"] == seed0:
            ax.plot(r["steps"].t, r["steps"].formation_rms, label=s["arm"], lw=1.3)
            win = r["meta"].get("scenario_window")
    if "win" in dir() and win:
        ax.axvspan(win[0], win[1], color="tab:red", alpha=.15, label="injected fault")
    ax.set_title(f"{sc}: formation RMS by controller, seed {seed0}  [plant: {df.plant.iloc[0].upper()}]")
    ax.set_xlabel("t [s]"); ax.set_ylabel("m"); ax.legend(fontsize=8); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(out / "plots" / f"compare_arms_{sc}.png", dpi=110); plt.close(fig)
print(agg.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
print("\nstates reached (supervisor arm):"); print((out / "supervisor_states_reached.txt").read_text())
print("failures:", df[df.status != "completed"][["run_id", "status"]].to_string(index=False) if (df.status != "completed").any() else "none (all runs completed)")
