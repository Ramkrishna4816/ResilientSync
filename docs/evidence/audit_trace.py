"""Trace the rolling loss estimator of follower 1 through a forced blackout (adaptive_comm, supervisor on)."""
import sys, json, numpy as np
sys.path.insert(0, ".")
from simulation.config import Config
from simulation.simulation import MultiAgentSimulation

def trace(seed=42, b0=5.0, b1=8.0, T=14.0, pad=None):
    cfg = Config()
    if pad is not None: cfg.supervisor_min_loss_window = pad
    sim = MultiAgentSimulation(control_mode="adaptive_comm", seed=seed, record_history=False, cfg=cfg)
    f = sim.followers[0]; rows = []
    while sim.t < T - 1e-9:
        sim.network.set_forced_loss(b0 <= sim.t < b1)
        sim.step()
        age, loss, q = sim._link_quality(f, sim.t)
        w = f.pose_delivery_window
        raw = (sum(w) / len(w)) if len(w) else 0.0
        rows.append(dict(t=round(sim.t, 3), n=len(w), raw=raw, loss=loss, age=age, q=q,
                         state=getattr(sim.supervisors[f.id].state,'name',str(sim.supervisors[f.id].state))))
    return rows

if __name__ == "__main__":
    rows = trace()
    def at(t): return min(rows, key=lambda r: abs(r["t"] - t))
    print("t     n  rawloss paddedloss  age    q    state")
    for t in (1.0, 4.95, 5.05, 5.5, 6.0, 7.0, 7.95, 8.0, 8.05, 8.1, 8.3, 8.5, 9.0, 9.5, 10.0, 11.0, 12.0):
        r = at(t); print(f"{r['t']:5.2f} {r['n']:3d}  {r['raw']:.2f}   {r['loss']:.2f}     {r['age']:.2f}  {r['q']:.2f}  {r['state']}")
    json.dump(rows, open("docs/evidence/audit_trace.json", "w"))
