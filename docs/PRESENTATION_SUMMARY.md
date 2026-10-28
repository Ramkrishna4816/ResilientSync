# ResilientSync — technical summary for presentation

**Problem.** Leader–follower formations depend on a lossy radio link. Most simulators model packet loss but the controller never *knows* the link is bad.

**Contribution (all in this repo, all tested).**
1. **Explainable supervisor** — a deterministic 4-state machine (NORMAL / DEGRADED / HOLD / RECOVERING) per follower with hysteresis, dwell times, validated legal transitions and a generated reason for every transition, e.g. *"Entered HOLD because leader information age 1.30s exceeded the maximum permitted age 1.25s."*
2. **Reproducible fault injection** inside the existing network model: blackout, independent loss, burst loss, latency + jitter, with seeded RNG and a logged fault timeline.
3. **Matched-seed benchmark + ablation** (10 arms × 8 scenarios × 10 seeds = 800 runs) with paired statistics.
4. **Live dashboard**: supervisor state, explanation, transition history, message age, fault status, formation-error chart with fault bands.

**Honest results (eval seeds 42–51).**
* PIDR still has the lowest RMSE in every scenario (e.g. blackout 3 s: 1.537 m vs 1.664 m for the supervised controller).
* Supervisor vs the same controller with a neutral supervisor: +0.02 m (3 s blackout) to +0.05 m (6 s blackout) minimum separation, statistically consistent across seeds but practically small; RMSE changes by < 0.01 m.
* A first-design HOLD speed limit (0.8×) hurt RMSE by 0.17–0.25 m in blackouts and was switched off — an ablation-driven finding.
* The earlier total-speed cap roughly doubled the error (2.29 m vs 1.67 m, seeds 42–44); explains the "unchanged results" discrepancy.
* The sustained-recovery criterion is not met in most scenarios (criterion unchanged).

**Limits.** single plant/trajectory, partly centralised sim, heuristic quality, small effects.
