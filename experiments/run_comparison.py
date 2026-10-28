"""Reproducible controller comparison with a forced communication blackout.

Run from the repository root:
    python -m experiments.run_comparison --duration 18 --seeds 42 43 44

Outputs are written to experiments/results/. This is an engineering benchmark,
not a claim that adaptive_comm outperforms the baselines.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from simulation.metrics import compute_metrics, compute_recovery_metrics
from simulation.simulation import CONTROL_MODES, MultiAgentSimulation

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "results"


def run_scenario(mode: str, seed: int, duration: float, blackout_start: float,
                 blackout_duration: float, loss_scale: float) -> dict:
    if duration <= 0:
        raise ValueError("duration must be positive")
    if not 0 <= blackout_start < duration:
        raise ValueError("blackout_start must be inside the simulation duration")
    if blackout_duration < 0 or blackout_start + blackout_duration > duration:
        raise ValueError("blackout window must fit inside the simulation duration")

    sim = MultiAgentSimulation(control_mode=mode, seed=seed, loss_scale=loss_scale,
                               record_history=True)
    sim.run(blackout_start)
    if blackout_duration > 0:
        sim.network.set_forced_loss(True)
        sim.run(blackout_duration)
        sim.network.set_forced_loss(False)
        sim.run(duration - blackout_start - blackout_duration)
    else:
        sim.run(duration - blackout_start)
    h = sim.history()
    metrics = compute_metrics(h)
    
    metrics.update({
        "mode": mode,
        "seed": seed,
        "duration_s": duration,
        "blackout_start_s": blackout_start,
        "blackout_duration_s": blackout_duration,
        "mean_quality": float(np.mean(h["communication_quality"][:, 1:])),
        "min_quality": float(np.min(h["communication_quality"][:, 1:])),
    })

    if blackout_duration > 0:
        metrics.update(compute_recovery_metrics(
            h["t"],
            h["formation_rms"],
            blackout_start=blackout_start,
            blackout_end=blackout_start + blackout_duration,
        ))
    else:
        metrics.update({
            "recovery_baseline_m": None,
            "recovery_threshold_m": None,
            "recovered": None,
            "recovery_time_s": None,
        })

    return h, metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=18.0)
    parser.add_argument("--blackout-start", type=float, default=5.0)
    parser.add_argument("--blackout-duration", type=float, default=3.0)
    parser.add_argument("--loss-scale", type=float, default=1.0)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    parser.add_argument("--modes", nargs="+", choices=CONTROL_MODES, default=list(CONTROL_MODES))
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    plot_histories = {}
    for mode in args.modes:
        for seed in args.seeds:
            print(f"Running mode={mode}, seed={seed} ...", flush=True)
            history, metrics = run_scenario(
                mode, seed, args.duration, args.blackout_start,
                args.blackout_duration, args.loss_scale)
            rows.append(metrics)
            if seed == args.seeds[0]:
                plot_histories[mode] = history
            print("  RMSE={RMSE:.4f} m | peak={Peak:.4f} m | min separation={MinSep:.3f} m | collisions={Collision:.2f}%".format(**metrics))

    csv_path = OUT / "controller_comparison.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for mode, h in plot_histories.items():
        ax.plot(h["t"], h["formation_rms"], label=mode)
    ax.axvspan(args.blackout_start, args.blackout_start + args.blackout_duration,
               alpha=0.16, label="forced blackout")
    ax.set_xlabel("Simulation time (s)")
    ax.set_ylabel("Formation RMS error (m)")
    ax.set_title(f"Controller comparison (seed={args.seeds[0]})")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    plot_path = OUT / "formation_error_blackout.png"
    fig.savefig(plot_path, dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    h = plot_histories.get("adaptive_comm")
    if h is not None:
        q = h["communication_quality"][:, 1:]
        ax.plot(h["t"], np.mean(q, axis=1), label="mean follower quality")
        ax.plot(h["t"], np.min(q, axis=1), label="worst follower quality", alpha=0.8)
        ax.axvspan(args.blackout_start, args.blackout_start + args.blackout_duration,
                   alpha=0.16, label="forced blackout")
        ax.set_xlabel("Simulation time (s)")
        ax.set_ylabel("Estimated communication quality (0–1)")
        ax.set_ylim(-0.03, 1.03)
        ax.set_title("Receiver-side communication-quality estimate")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        quality_path = OUT / "communication_quality.png"
        fig.savefig(quality_path, dpi=180)
    else:
        quality_path = None
    plt.close(fig)

    print(f"\nSaved: {csv_path.relative_to(ROOT)}")
    print(f"Saved: {plot_path.relative_to(ROOT)}")
    if quality_path:
        print(f"Saved: {quality_path.relative_to(ROOT)}")
    print("Review the measured results; this script does not assume adaptive_comm is best.")


if __name__ == "__main__":
    main()
