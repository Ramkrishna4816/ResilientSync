"""Deterministic tests of the per-follower rolling loss estimator (simulation._deliver / _link_quality).

These PIN the audited behaviour documented in docs/ROLLING_WINDOW_AUDIT.md.  Two pinned properties are
*limitations*, not endorsements: the window is delivery-driven (frozen during a total outage; age carries
the outage) and it pads the denominator to `supervisor_min_loss_window` in adaptive_comm.
"""
import numpy as np

from simulation.config import Config
from simulation.messages import POSE_UPDATE
from simulation.simulation import MultiAgentSimulation


def _sim(mode="adaptive_comm", seed=1, **kw):
    cfg = Config()
    for k, v in kw.items():
        setattr(cfg, k, v)
    return MultiAgentSimulation(control_mode=mode, seed=seed, record_history=False, cfg=cfg)


def _pose(sim, fid, sample_seq, link_seq, t):
    """Deliver a POSE_UPDATE for sample `sample_seq` carrying bus sequence `link_seq` at time t."""
    m = sim.bus.create(0, fid, POSE_UPDATE, {"state": np.zeros(4), "pose_seq": sample_seq}, t)
    m.sequence = link_seq
    sim._deliver(m, t, sim.cfg.dt)


def _loss(sim, f, now):
    age, loss, q = sim._link_quality(f, now)
    return age, loss, q


def test_empty_window_reports_zero_loss_and_is_bounded():
    sim = _sim(); f = sim.followers[0]
    age, loss, q = _loss(sim, f, 0.0)
    assert loss == 0.0 and 0.0 <= q <= 1.0 and np.isfinite(age)


def test_warmup_padding_underestimates_observed_loss_in_adaptive_comm_only():
    # one inferred miss then one hit: observed loss is 1/2
    a = _sim("adaptive_comm"); fa = a.followers[0]; _pose(a, fa.id, 2, 1, 0.1)
    assert list(fa.pose_delivery_window) == [True, False]
    assert _loss(a, fa, 0.1)[1] == 1 / a.cfg.supervisor_min_loss_window          # 0.05: padded (deliberate smoothing)
    z = _sim("zoh"); fz = z.followers[0]; _pose(z, fz.id, 2, 1, 0.1)
    assert _loss(z, fz, 0.1)[1] == 0.5                                           # unpadded elsewhere
    p = _sim("adaptive_comm", supervisor_min_loss_window=1); fp = p.followers[0]; _pose(p, fp.id, 2, 1, 0.1)
    assert _loss(p, fp, 0.1)[1] == 0.5                                           # padding is configurable


def test_all_success_window_has_zero_loss():
    sim = _sim(); f = sim.followers[0]
    for k in range(1, 61):
        _pose(sim, f.id, k, k, 0.05 * k)
    assert sum(f.pose_delivery_window) == 0 and len(f.pose_delivery_window) == f.pose_delivery_window.maxlen
    assert _loss(sim, f, 3.0)[1] == 0.0


def test_long_gap_saturates_at_window_length_then_evicts_after_recovery():
    sim = _sim(); f = sim.followers[0]; W = f.pose_delivery_window.maxlen
    _pose(sim, f.id, 1, 1, 0.05)
    _pose(sim, f.id, 200, 2, 10.0)                       # 198 samples missed in a gap
    assert len(f.pose_delivery_window) == W and sum(f.pose_delivery_window) == W - 1
    assert _loss(sim, f, 10.0)[1] == (W - 1) / W
    for k in range(1, W + 1):                            # W consecutive successes evict every miss
        _pose(sim, f.id, 200 + k, 2 + k, 10.0 + 0.05 * k)
    assert sum(f.pose_delivery_window) == 0 and _loss(sim, f, 12.0)[1] == 0.0


def test_burst_is_counted_exactly_and_partially_evicted():
    sim = _sim(); f = sim.followers[0]
    for k in range(1, 11):
        _pose(sim, f.id, k, k, 0.05 * k)
    _pose(sim, f.id, 16, 11, 0.8)                        # samples 11..15 lost (burst of 5)
    assert sum(f.pose_delivery_window) == 5 and len(f.pose_delivery_window) == 16


def test_duplicate_and_out_of_order_packets_are_ignored_not_double_counted():
    sim = _sim(); f = sim.followers[0]
    _pose(sim, f.id, 5, 5, 0.25)
    snap = (list(f.pose_delivery_window), f.rx_seq, f.rx_time)
    _pose(sim, f.id, 5, 5, 0.30)                         # duplicate
    _pose(sim, f.id, 3, 3, 0.35)                         # late (older) packet
    assert (list(f.pose_delivery_window), f.rx_seq, f.rx_time) == snap
    # a late packet was already counted as a miss when its successor arrived (loss = "not received in order")
    assert sum(f.pose_delivery_window) == 4


def test_followers_are_isolated():
    sim = _sim(); f1, f2 = sim.followers[0], sim.followers[1]
    for k in range(1, 6):
        _pose(sim, f2.id, k, k, 0.05 * k)
    _pose(sim, f1.id, 30, 1, 1.5)                        # only follower 1 has a gap
    assert sum(f1.pose_delivery_window) > 0 and sum(f2.pose_delivery_window) == 0
    assert _loss(sim, f2, 1.5)[1] == 0.0


def test_loss_and_quality_always_finite_and_in_unit_interval():
    rng = np.random.default_rng(0); sim = _sim(); f = sim.followers[0]; seq = 0; link = 0
    for k in range(400):
        seq += int(rng.integers(1, 7)); link += 1
        if rng.random() < 0.8:
            _pose(sim, f.id, seq, link, 0.05 * k)
        age, loss, q = _loss(sim, f, 0.05 * k + float(rng.random() * 5))
        assert np.isfinite([age, loss, q]).all() and 0 <= loss <= 1 and 0 <= q <= 1


def test_PINNED_LIMITATION_window_is_frozen_during_total_outage_age_carries_it():
    sim = _sim(seed=23)
    sim.run(5.0)
    sim.network.set_forced_loss(True)
    sim.run(0.5)                                         # let in-flight packets (<= 4 steps latency) drain
    f = sim.followers[0]
    w0, ages0 = list(f.pose_delivery_window), _loss(sim, f, sim.t)[0]
    sim.run(2.0)
    assert list(f.pose_delivery_window) == w0            # no new observation during the outage (documented limitation)
    assert _loss(sim, f, sim.t)[0] > ages0 + 1.9         # message age does grow, and quality falls with it
    assert _loss(sim, f, sim.t)[2] < 0.1
