"""Print markdown tables from results/standin_report/eval (used to fill docs/WEBOTS_VALIDATION.md)."""
import pandas as pd
from pathlib import Path
R = Path(__file__).resolve().parents[1] / "results" / "standin_report" / "eval"
s = pd.read_csv(R / "summary_by_scenario_arm.csv"); p = pd.read_csv(R / "per_run_metrics.csv")
order = ["pidr", "advanced", "adaptive_legacy", "adaptive_supervisor"]
print("| scenario | arm | runs ok | RMSE mean ± sd [m] | peak [m] | min sep [m] | collisions | recovered | time to all-NORMAL [s] | stand-in − native RMSE |")
print("|---|---|---|---|---|---|---|---|---|---|")
for sc in ["nominal_gentle", "blackout_gentle", "blackout_3s", "random_loss_30", "burst_loss", "latency_jitter"]:
    for a in order:
        r = s[(s.scenario == sc) & (s.arm == a)].iloc[0]
        rec = f"{int(r.recovered)}/{int(r.recovery_applicable)}" if r.recovery_applicable else "n/a"
        tn = f"{r.time_to_all_normal_s:.2f}" if pd.notna(r.time_to_all_normal_s) else "–"
        print(f"| {sc} | {a} | {int(r.completed)}/{int(r.runs)} | {r.RMSE_mean:.3f} ± {r.RMSE_sd:.3f} | {r.Peak_mean:.2f} | {r.MinSep_min:.2f} | {int(r.collision_runs)} | {rec} | {tn} | {r.RMSE_minus_python:+.3f} |")
