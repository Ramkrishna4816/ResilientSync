"""Compare loss-estimator variants on identical seeds / fault schedules (engine code untouched; variants are
monkeypatched here).  Tuning seeds 100-109 (NOT the 42-51 evaluation seeds).  EXPLORATORY, uncorrected."""
import sys, json, numpy as np
from scipy import stats
sys.path.insert(0, ".")
from simulation.config import Config
from simulation.controller import estimate_communication_quality
from simulation.simulation import MultiAgentSimulation

GRACE = 4   # steps of in-flight latency tolerated before a sample counts as overdue (nominal latency is 1-4 steps)
orig = MultiAgentSimulation._link_quality

def realtime(self, a, now):
    """Delivery window + overdue samples counted as pending misses, so a silent link is visible immediately."""
    age = max(0.0, now - a.rx_time); win = list(a.pose_delivery_window)
    pending = max(0, self.step_count - a.last_pose_sample_seq - GRACE)
    maxlen = a.pose_delivery_window.maxlen or 40
    w = (win + [True] * min(pending, maxlen))[-maxlen:]
    denom = max(len(w), min(self.cfg.supervisor_min_loss_window, maxlen)) if w else 0
    loss = sum(w) / denom if denom else 0.0
    return age, loss, estimate_communication_quality(age, loss, self.cfg.adaptive_comm_age_tau)

def run(variant, seed, blackout, T=14.0, b0=5.0, b1=8.0):
    cfg = Config()
    if variant == "nopad": cfg.supervisor_min_loss_window = 1
    MultiAgentSimulation._link_quality = realtime if variant == "realtime" else orig
    sim = MultiAgentSimulation(control_mode="adaptive_comm", seed=seed, record_history=True, cfg=cfg)
    while sim.t < T - 1e-9:
        if blackout: sim.network.set_forced_loss(b0 <= sim.t < b1)
        if not sim.step(): break
    h = sim.history(); t = np.asarray(h["t"]); rms = np.asarray(h["formation_rms"]); sep = np.asarray(h["min_distance"])
    sup = np.asarray(h["supervisor_state"])[:, 1:]; q = np.asarray(h["communication_quality"])[:, 1:]
    out = dict(rms=float(np.sqrt(np.mean(rms ** 2))), min_sep=float(sep.min()), mean_q=float(q.mean()),
               hold_frac=float((sup == 2).mean()), collisions=int((sep < sim.cfg.collision_distance).sum()) if hasattr(sim.cfg, "collision_distance") else -1)
    if blackout:
        post = t >= b1
        normal_all = (sup == 0).all(axis=1) & post
        idx = np.where(normal_all)[0]
        out["t_normal_after_restore"] = float(t[idx[0]] - b1) if len(idx) else float("nan")
        m = (t >= b1) & (t < b1 + 4); out["rms_post4s"] = float(np.sqrt(np.mean(rms[m] ** 2)))
    return out

if __name__ == "__main__":
    seeds = range(100, 110); res = {}
    for scen, bl in (("nominal", False), ("blackout_3s", True)):
        for v in ("current", "nopad", "realtime"):
            res[f"{scen}/{v}"] = [run(v, s, bl) for s in seeds]
    MultiAgentSimulation._link_quality = orig
    json.dump(res, open("docs/evidence/estimator_compare.json", "w"), indent=1)
    for scen in ("nominal", "blackout_3s"):
        print(f"\n== {scen}  (mean over 10 seeds; paired diff vs current: mean [95% CI], n wins)")
        keys = [k for k in res[f"{scen}/current"][0] if k != "collisions"]
        for v in ("current", "nopad", "realtime"):
            row = []
            for k in keys:
                a = np.array([r[k] for r in res[f"{scen}/{v}"]]); c = np.array([r[k] for r in res[f"{scen}/current"]])
                if v == "current": row.append(f"{k}={np.nanmean(a):.3f}")
                else:
                    d = a - c; d = d[np.isfinite(d)]
                    if len(d) > 1 and d.std() > 0:
                        ci = stats.t.interval(0.95, len(d) - 1, d.mean(), stats.sem(d)); row.append(f"{k}={np.nanmean(a):.3f} d={d.mean():+.3f}[{ci[0]:+.3f},{ci[1]:+.3f}]")
                    else: row.append(f"{k}={np.nanmean(a):.3f} d=0")
            print(f"{v:9s}", " | ".join(row))
        print("collision samples (sum over seeds):", {v: sum(r["collisions"] for r in res[f'{scen}/{v}']) for v in ("current", "nopad", "realtime")})
