"""Fault injection through the adapter: faults must change what the controller actually receives."""
import json
import numpy as np
import pytest
from resilientsync_webots.testing import SC, run_short
from experiments.run_benchmark import SCENARIOS, gentle_trajectory, maneuver_trajectory
from resilientsync_webots.faults import event_from_dict, load_scenarios, scenario_from_dict, scenario_to_dict


def test_json_scenarios_match_benchmark_definitions():
    assert set(SC) == set(SCENARIOS)
    for name, s in SCENARIOS.items():
        assert SC[name].profile.events == s.profile.events, name
        want = {None: "default", gentle_trajectory: "gentle", maneuver_trajectory: "maneuver"}[s.trajectory]
        assert SC[name].trajectory_name == want
        assert SC[name].trajectory is s.trajectory
        assert SC[name].window == s.window


def test_scenario_dict_roundtrip():
    for s in SC.values():
        assert scenario_from_dict(s.name, scenario_to_dict(s)).profile.events == s.profile.events


def test_invalid_fault_config_is_rejected():
    with pytest.raises(ValueError):
        event_from_dict({"kind": "blackout", "start": 1.0, "duration": 1.0, "bogus": 1})
    with pytest.raises(Exception):
        event_from_dict({"kind": "random_loss", "start": 1.0, "duration": 1.0, "probability": 1.7})
    with pytest.raises(Exception):
        event_from_dict({"kind": "not_a_fault", "start": 1.0, "duration": 1.0})


def test_blackout_removes_messages_the_controller_receives():
    run, meta = run_short("blackout_gentle")                      # blackout 5-8 s
    assert meta["status"] == "completed"
    ev, dl, st = run["comm_events"], run["deliveries"], run["steps"]
    pose = ev[ev.type == "POSE_UPDATE"]
    inside = pose[(pose.t_sent >= 5.0) & (pose.t_sent < 8.0)]
    assert len(inside) > 100 and (inside.status == "LOST").all()          # every message dropped
    assert not (pose[pose.t_sent < 5.0].status == "LOST").all()           # channel works before
    acc = dl[dl.accepted]
    assert len(acc[(acc.t_delivered > 5.5) & (acc.t_delivered < 8.0)]) == 0   # nothing reaches a controller
    assert acc[acc.t_delivered >= 8.0].t_delivered.min() < 8.5               # restored right after
    # controller-visible effect: message age grows across the outage, then collapses
    for i in range(1, 5):
        a = st.set_index("t")[f"age_{i}"]
        assert a.loc[7.9] > 2.4 and a.loc[8.5] < 1.0
    # fault markers are logged
    assert st[(st.t >= 5.0) & (st.t < 8.0)].blackout_active.eq(1).all()
    assert st[(st.t < 4.9) | (st.t > 8.1)].blackout_active.eq(0).all()
    edges = run["faults"]["edges"]
    assert any(abs(e["t"] - 5.0) < 0.06 for e in edges) and any(abs(e["t"] - 8.0) < 0.06 for e in edges)


def test_random_loss_raises_measured_loss_inside_window_only():
    run, _ = run_short("random_loss_30", duration=16.0)
    ev = run["comm_events"]; p = ev[ev.type == "POSE_UPDATE"]
    start, end = SC["random_loss_30"].window
    inside = (p[(p.t_sent >= start) & (p.t_sent < end)].status == "LOST").mean()
    outside = (p[(p.t_sent < start) | (p.t_sent >= end + 1.0)].status == "LOST").mean()
    assert inside > outside + 0.05


def test_burst_loss_produces_consecutive_drops():
    run, _ = run_short("burst_loss", duration=16.0)
    ev = run["comm_events"]; p = ev[(ev.type == "POSE_UPDATE") & (ev.receiver == 1)].sort_values("t_sent")
    start, end = SC["burst_loss"].window
    w = (p[(p.t_sent >= start) & (p.t_sent < end)].status == "LOST").to_numpy()
    longest = max((len(x) for x in "".join("1" if v else "0" for v in w).split("0")), default=0)
    assert longest >= 3                                                   # bursts, not isolated drops


def test_latency_fault_increases_delivery_latency():
    run, _ = run_short("latency_jitter", duration=16.0)
    ev = run["comm_events"]; p = ev[(ev.type == "POSE_UPDATE") & (ev.status != "LOST")]
    start, end = SC["latency_jitter"].window
    inside = p[(p.t_sent >= start) & (p.t_sent < end)].latency_s.mean()
    outside = p[(p.t_sent < start)].latency_s.mean()
    assert inside > outside + 0.05


def test_same_seed_reproduces_logs_exactly_and_other_seed_differs():
    a, _ = run_short("blackout_gentle", seed=100, duration=8.0)
    b, _ = run_short("blackout_gentle", seed=100, duration=8.0)
    c, _ = run_short("blackout_gentle", seed=101, duration=8.0)
    assert a["steps"].equals(b["steps"]) and a["comm_events"].equals(b["comm_events"])
    assert not a["comm_events"].equals(c["comm_events"])
