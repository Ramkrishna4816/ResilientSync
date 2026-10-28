"""Fault-injection tests: activation, expiry, reproducibility, edge cases."""
import math

import numpy as np
import pytest

from simulation.config import Config
from simulation.messages import POSE_UPDATE, MessageBus
from simulation.network import (FaultEvent, FaultProfile, Network,
                                make_fault_profile)
from simulation.simulation import MultiAgentSimulation

CFG = Config()
DT = CFG.dt


def make_net(profile=None, seed=7):
    net = Network(CFG, MessageBus(CFG.comm_log_size), seed)
    net.set_fault_profile(profile)
    return net


def send_stream(net, t0, t1, link=(0, 1)):
    """Send one pose packet per tick; return list of CommEvents."""
    evs, t = [], t0
    while t < t1 - 1e-9:
        net.update_faults(t)
        msg = net.bus.create(link[0], link[1], POSE_UPDATE, {}, t)
        evs.append(net.transmit(msg, t, DT))
        t += DT
    return evs


def lost(evs):
    return np.array([e.status == "LOST" for e in evs])


# --------------------------------------------------------------- defaults
def test_default_has_no_faults_and_matches_none_profile():
    a = MultiAgentSimulation(control_mode="pidr", seed=5, record_history=True)
    b = MultiAgentSimulation(control_mode="pidr", seed=5, record_history=True,
                             fault_profile="none")
    a.run(3.0); b.run(3.0)
    np.testing.assert_array_equal(a.history()["states"], b.history()["states"])
    assert a.network.fault_log == [] and a.network.profile.name == "none"


# --------------------------------------------------------------- blackout
def test_blackout_profile_is_identical_to_forced_loss_hook():
    ref = MultiAgentSimulation(control_mode="advanced", seed=11, record_history=True)
    ref.run(1.0); ref.network.set_forced_loss(True); ref.run(1.0)
    ref.network.set_forced_loss(False); ref.run(1.0)
    new = MultiAgentSimulation(control_mode="advanced", seed=11, record_history=True,
                               fault_profile=make_fault_profile("blackout", 1.0, 1.0))
    new.run(3.0)
    np.testing.assert_array_equal(ref.history()["formation_rms"], new.history()["formation_rms"])
    np.testing.assert_array_equal(ref.history()["packet_drop"], new.history()["packet_drop"])


def test_fault_activation_and_expiry_are_logged_with_times():
    sim = MultiAgentSimulation(control_mode="pidr", seed=3,
                               fault_profile=make_fault_profile("blackout", 1.0, 0.5))
    sim.run(2.0)
    log = sim.network.fault_log
    assert [e["action"] for e in log] == ["start", "end"]
    assert log[0]["t"] == pytest.approx(1.0, abs=1e-6)
    assert log[1]["t"] == pytest.approx(1.5, abs=1e-6)
    assert log[0]["profile"] == "blackout"


def test_blackout_drops_everything_inside_window_and_nothing_outside():
    net = make_net(make_fault_profile("blackout", 1.0, 1.0), seed=1)
    evs = send_stream(net, 0.0, 3.0)
    t = np.arange(len(evs)) * DT
    inside = (t >= 1.0 - 1e-9) & (t < 2.0 - 1e-9)
    assert lost(evs)[inside].all()
    assert lost(evs)[~inside].mean() < 0.5     # base Gilbert-Elliott loss only


def test_zero_duration_event_never_activates():
    net = make_net(FaultProfile("z", (FaultEvent("blackout", 1.0, 0.0),)))
    send_stream(net, 0.0, 2.0)
    assert net.fault_log == []


def test_infinite_duration_event_stays_active():
    net = make_net(FaultProfile("inf", (FaultEvent("blackout", 0.5, math.inf),)))
    evs = send_stream(net, 0.0, 5.0)
    assert lost(evs)[12:].all() and [e["action"] for e in net.fault_log] == ["start"]


# ------------------------------------------------------------ random loss
def test_random_loss_rate_matches_probability_and_respects_window():
    p = 0.3
    base = lost(send_stream(make_net(None, seed=2), 0.0, 100.0)).mean()
    net = make_net(make_fault_profile("random_loss", 10.0, 80.0, probability=p), seed=2)
    evs = send_stream(net, 0.0, 100.0)
    t = np.arange(len(evs)) * DT
    inside = (t >= 10.0) & (t < 90.0)
    rate_in = lost(evs)[inside].mean()
    expected = 1 - (1 - p) * (1 - base)
    assert abs(rate_in - expected) < 0.03
    assert net.fault_counts["dropped_by_fault"] > 0
    assert lost(evs)[~inside].mean() == pytest.approx(base, abs=0.03)


@pytest.mark.parametrize("p", [0.0, 1.0])
def test_random_loss_edge_probabilities(p):
    net = make_net(FaultProfile("e", (FaultEvent("random_loss", 0.0, 50.0, probability=p),)))
    evs = send_stream(net, 0.0, 20.0)
    if p == 1.0:
        assert lost(evs).all()
    else:
        assert net.fault_counts["dropped_by_fault"] == 0


# -------------------------------------------------------------- burst loss
def longest_run(x):
    best = cur = 0
    for v in x:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def test_burst_loss_is_more_correlated_than_independent_loss_at_equal_rate():
    burst = FaultProfile("b", (FaultEvent("burst_loss", 0.0, 400.0, p_good_to_bad=0.05,
                                          p_bad_to_good=0.20),))
    nb = make_net(burst, seed=4)
    lb = lost(send_stream(nb, 0.0, 200.0))
    rate = nb.fault_counts["dropped_by_fault"] / len(lb)
    ind = FaultProfile("i", (FaultEvent("random_loss", 0.0, 400.0, probability=rate),))
    li = lost(send_stream(make_net(ind, seed=4), 0.0, 200.0))
    assert longest_run(lb) > longest_run(li)


# ----------------------------------------------------------------- latency
def test_latency_fault_adds_delay_and_jitter_is_bounded():
    prof = FaultProfile("l", (FaultEvent("latency", 2.0, 2.0, extra_latency_s=0.3, jitter_s=0.1),))
    base = send_stream(make_net(None, seed=9), 0.0, 6.0)
    flt = send_stream(make_net(prof, seed=9), 0.0, 6.0)
    t = np.arange(len(base)) * DT
    inside = (t >= 2.0) & (t < 4.0)
    for b, f, ins, lo in zip(base, flt, inside, lost(base)):
        if f.status == "LOST" or b.status == "LOST":
            continue
        d = f.latency - b.latency
        if ins:
            assert 0.2 - 1e-9 <= d <= 0.4 + 1e-9
        else:
            assert d == pytest.approx(0.0, abs=1e-12)


def test_latency_without_jitter_is_deterministic_constant_shift_and_never_negative():
    prof = FaultProfile("l", (FaultEvent("latency", 0.0, 5.0, extra_latency_s=0.25),))
    evs = send_stream(make_net(prof), 0.0, 5.0)
    base = send_stream(make_net(None), 0.0, 5.0)
    for f, b in zip(evs, base):
        if f.status != "LOST" and b.status != "LOST":
            assert f.latency == pytest.approx(b.latency + 0.25)
        assert f.latency >= 0.0


def test_delayed_packets_are_delivered_late_by_the_extra_latency():
    prof = FaultProfile("l", (FaultEvent("latency", 0.0, 5.0, extra_latency_s=0.5),))
    net = make_net(prof)
    net.update_faults(0.0)
    msg = net.bus.create(0, 1, POSE_UPDATE, {}, 0.0)
    ev = net.transmit(msg, 0.0, DT)
    if ev.status != "LOST":
        assert net.poll(0.4) == []
        assert len(net.poll(0.0 + ev.latency + 1e-6)) == 1


# --------------------------------------------------------- reproducibility
def test_same_seed_same_losses_different_seed_differs():
    prof = make_fault_profile("random_loss", 0.0, 50.0, probability=0.4)
    a = lost(send_stream(make_net(prof, seed=21), 0.0, 30.0))
    b = lost(send_stream(make_net(prof, seed=21), 0.0, 30.0))
    c = lost(send_stream(make_net(prof, seed=22), 0.0, 30.0))
    assert (a == b).all() and not (a == c).all()


def test_all_controllers_see_identical_fault_realisation():
    prof = make_fault_profile("random_loss", 1.0, 4.0, probability=0.4)
    counts = []
    for mode in ("pidr", "advanced", "adaptive_comm"):
        sim = MultiAgentSimulation(control_mode=mode, seed=8, fault_profile=prof)
        sim.run(6.0)
        counts.append((sim.network.fault_counts["dropped_by_fault"],
                       sim.network.snapshot()["lost"]))
    assert counts[0] == counts[1] == counts[2]


# -------------------------------------------------------------- validation
@pytest.mark.parametrize("kwargs", [
    dict(kind="nope", start=0, duration=1),
    dict(kind="random_loss", start=0, duration=1, probability=1.2),
    dict(kind="random_loss", start=0, duration=1, probability=-0.1),
    dict(kind="random_loss", start=0, duration=1, probability=float("nan")),
    dict(kind="blackout", start=-1, duration=1),
    dict(kind="blackout", start=0, duration=-1),
    dict(kind="blackout", start=0, duration=float("nan")),
    dict(kind="latency", start=0, duration=1),                       # no effect
    dict(kind="latency", start=0, duration=1, extra_latency_s=-0.1),
    dict(kind="latency", start=0, duration=1, jitter_s=float("inf")),
    dict(kind="burst_loss", start=0, duration=1, p_good_to_bad=0.1, p_bad_to_good=0.0),
])
def test_invalid_fault_parameters_are_rejected(kwargs):
    with pytest.raises(ValueError):
        FaultEvent(**kwargs)


def test_unknown_profile_and_wrong_type_rejected():
    with pytest.raises(ValueError):
        make_fault_profile("nope")
    with pytest.raises(TypeError):
        make_net().set_fault_profile(42)


def test_per_link_forced_loss_hook_still_works_with_fault_layer():
    net = make_net(None)
    net.set_forced_loss(True, link=(0, 2))
    a = lost(send_stream(net, 0.0, 2.0, link=(0, 2)))
    b = lost(send_stream(net, 0.0, 2.0, link=(0, 1)))
    assert a.all() and not b.all()
    net.set_forced_loss(False, link=(0, 2))
    assert not lost(send_stream(net, 2.0, 4.0, link=(0, 2))).all()


def test_snapshot_exposes_profile_and_active_state_for_the_dashboard():
    sim = MultiAgentSimulation(control_mode="pidr", seed=3,
                               fault_profile=make_fault_profile("blackout", 0.5, 1.0))
    sim.run(1.0)
    snap = sim.network.snapshot()["faults"]
    assert snap["profile"] == "blackout" and snap["blackout_active"] is True
    assert snap["active"][0]["kind"] == "blackout"
    sim.run(1.0)
    assert sim.network.snapshot()["faults"]["blackout_active"] is False
