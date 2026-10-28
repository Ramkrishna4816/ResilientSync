"""Stages A-F of the validation plan on the STAND-IN plant (not Webots).

Tuning/debug seeds 100-104 (stage F, small); final evaluation seeds 42-51 = the project's declared evaluation seeds.
No parameter was changed between the two.  Output: results/standin/{debug,eval}/
"""
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
ALL = ["pidr", "advanced", "adaptive_legacy", "adaptive_supervisor"]

def run(args):
    print(">>", " ".join(args)); subprocess.run([PY, str(ROOT / "scripts" / "run_standin_trials.py"), *args], check=True)

stage = sys.argv[1] if len(sys.argv) > 1 else "all"
o = ROOT / "results" / "standin"
if stage in ("A", "all"):      # smoke: 3-robot formation, 4 s
    run(["--scenarios", "nominal", "--arms", "adaptive_supervisor", "--seeds", "100", "--n-agents", "3", "--duration", "4", "--out", str(o / "A_smoke")])
if stage in ("B", "all"):      # nominal
    run(["--scenarios", "nominal_gentle", "nominal", "--arms", "adaptive_supervisor", "--seeds", "100", "--out", str(o / "B_nominal")])
if stage in ("C", "all"):      # blackout
    run(["--scenarios", "blackout_gentle", "blackout_3s", "--arms", "adaptive_supervisor", "--seeds", "100", "--out", str(o / "C_blackout")])
if stage in ("D", "all"):      # packet loss
    run(["--scenarios", "random_loss_30", "burst_loss", "latency_jitter", "--arms", "adaptive_supervisor", "--seeds", "100", "--out", str(o / "D_loss")])
if stage in ("E", "all"):      # controller comparison (debug seeds)
    run(["--scenarios", "blackout_gentle", "--arms", *ALL, "--seeds", "100", "--out", str(o / "E_compare")])
if stage in ("F", "all"):      # repeated trials: debug seeds, then evaluation seeds
    run(["--scenarios", "nominal_gentle", "blackout_gentle", "random_loss_30", "burst_loss", "--arms", *ALL,
         "--seeds", "100", "101", "102", "103", "104", "--out", str(o / "F_debug")])
if stage in ("eval", "all"):
    run(["--scenarios", "nominal_gentle", "blackout_gentle", "blackout_3s", "random_loss_30", "burst_loss", "latency_jitter", "--arms", *ALL,
         "--seeds", *[str(s) for s in range(42, 52)], "--out", str(o / "eval")])
