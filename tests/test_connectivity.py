"""Connectivity graph, consensus metrics and simulator integration."""
import math

import numpy as np
import pytest

from simulation.connectivity import (ConnectivityTracker, algebraic_connectivity, bidirectional,
                                     circular_mean, connected_components, directed_adjacency,
                                     edge_disagreement, evaluate_topology, first_sustained_time,
                                     heading_disagreement, laplacian, reachable_from,
                                     speed_disagreement, summarize_series)
from simulation.network import make_fault_profile
from simulation.simulation import MultiAgentSimulation


def star(n, leaves=None, both=True):
    leaves = range(1, n) if leaves is None else leaves
    links = [(0, i) for i in leaves] + ([(i, 0) for i in leaves] if both else [])
    return directed_adjacency(n, links)


# ---- graph primitives --------------------------------------------------------
def test_star_fiedler_value_is_one():
    # Laplacian spectrum of a star K_{1,n-1}: {0, 1 (n-2 times), n}
    for n in (3, 5, 8):
        assert algebraic_connectivity(bidirectional(star(n))) == pytest.approx(1.0)


def test_path_graph_fiedler_value_known():
    # path P_n: lambda2 = 2 (1 - cos(pi/n))
    n = 5
    A = np.zeros((n, n))
    for i in range(n - 1):
        A[i, i + 1] = A[i + 1, i] = 1
    assert algebraic_connectivity(A) == pytest.approx(2 * (1 - math.cos(math.pi / n)))


def test_complete_graph_fiedler_value_is_n():
    n = 4
    A = np.ones((n, n)) - np.eye(n)
    assert algebraic_connectivity(A) == pytest.approx(n)


def test_disconnected_graph_has_zero_fiedler_value():
    A = bidirectional(star(5, leaves=[1, 2]))      # agents 3, 4 isolated
    assert algebraic_connectivity(A) == 0.0
    assert connected_components(A) == [[0, 1, 2], [3], [4]]


def test_small_graphs_and_edge_cases():
    assert algebraic_connectivity(np.zeros((1, 1))) == 0.0
    assert algebraic_connectivity(np.array([[0, 1.0], [1.0, 0]])) == pytest.approx(2.0)
    assert connected_components(np.zeros((1, 1))) == [[0]]
    assert connected_components(np.zeros((3, 3))) == [[0], [1], [2]]


def test_weighted_laplacian_rows_sum_to_zero():
    A = np.array([[0, 2.0, 0], [2.0, 0, 3.0], [0, 3.0, 0]])
    assert np.allclose(laplacian(A).sum(axis=1), 0.0)


def test_invalid_graph_input_rejected():
    with pytest.raises(ValueError):
        laplacian(np.array([[0, 1.0], [0.0, 0]]))        # directed -> no Laplacian conclusions
    with pytest.raises(ValueError):
        algebraic_connectivity(np.array([[0, -1.0], [-1.0, 0]]))
    with pytest.raises(ValueError):
        algebraic_connectivity(np.array([[0, np.nan], [np.nan, 0]]))
    with pytest.raises(ValueError):
        algebraic_connectivity(np.zeros((2, 3)))
    with pytest.raises(ValueError):
        directed_adjacency(3, [(0, 7)])


def test_bidirectional_drops_one_way_links():
    A = directed_adjacency(3, [(0, 1), (1, 0), (0, 2)])    # 2 only hears the leader
    U = bidirectional(A)
    assert U[0, 1] == 1 and U[0, 2] == 0
    topo = evaluate_topology(A)                             # conservative view
    assert topo["isolated_from_leader"] == [2]
    assert topo["unreached_by_leader"] == []                # directed reachability still ok


def test_union_view_for_downlink_only_graph():
    A = directed_adjacency(4, [(0, 1), (0, 2)])             # leader -> 1, 2 only
    topo = evaluate_topology(A, view="union")
    assert topo["components"] == [[0, 1, 2], [3]]
    assert topo["isolated_from_leader"] == [3]
    assert topo["algebraic_connectivity"] == 0.0
    assert evaluate_topology(A)["algebraic_connectivity"] == 0.0   # bidirectional: no links
    with pytest.raises(ValueError):
        evaluate_topology(A, view="nonsense")


def test_reachability_is_directed():
    A = directed_adjacency(3, [(1, 0), (2, 1)])             # edges point INTO the leader
    assert reachable_from(A, 0) == [0]
    assert reachable_from(A, 2) == [0, 1, 2]


# ---- consensus metrics -------------------------------------------------------
def test_heading_disagreement_zero_when_equal():
    assert heading_disagreement([0.3, 0.3, 0.3]) == {"rms": 0.0, "max": 0.0}


def test_heading_wraparound_is_not_a_large_disagreement():
    # +179 deg and -179 deg are 2 deg apart, not 358 deg
    hd = heading_disagreement([math.radians(179), math.radians(-179)])
    assert hd["max"] == pytest.approx(math.radians(2), abs=1e-9)
    assert hd["rms"] == pytest.approx(math.radians(1), abs=1e-9)
    assert circular_mean([math.pi - 0.1, -math.pi + 0.1]) == pytest.approx(math.pi, abs=1e-9) \
        or circular_mean([math.pi - 0.1, -math.pi + 0.1]) == pytest.approx(-math.pi, abs=1e-9)


def test_heading_disagreement_known_example():
    hd = heading_disagreement([0.0, 0.2])                   # circular mean 0.1
    assert hd["rms"] == pytest.approx(0.1)
    assert hd["max"] == pytest.approx(0.2)


def test_speed_disagreement_known_example():
    sd = speed_disagreement([1.0, 3.0])
    assert sd["std"] == pytest.approx(1.0) and sd["spread"] == pytest.approx(2.0)
    assert speed_disagreement([2.0]) == {"std": 0.0, "spread": 0.0}


def test_edge_disagreement_uses_only_graph_edges():
    th, v = [0.0, 0.5, 3.0], [1.0, 1.2, 9.0]
    A = bidirectional(directed_adjacency(3, [(0, 1), (1, 0)]))    # agent 2 not connected
    ed = edge_disagreement(th, v, A)
    assert ed["edges"] == 1
    assert ed["heading"] == pytest.approx(0.5) and ed["speed"] == pytest.approx(0.2)
    none = edge_disagreement(th, v, np.zeros((3, 3)))
    assert none["heading"] is None and none["edges"] == 0
    with pytest.raises(ValueError):
        edge_disagreement([0, 1], v, A)


def test_first_sustained_time():
    t = np.arange(0, 10, 0.5)
    ok = (t >= 4) & ~((t >= 6) & (t < 6.5))                  # blip at 6.0
    assert first_sustained_time(t, ok, after=0, hold_s=1.0) == 4.0
    # 4.0..5.5 holds only 1.5 s and the blip at 6.0 resets the window, so the
    # first 3 s-long run starts at 6.5
    assert first_sustained_time(t, ok, after=0, hold_s=3.0) == 6.5
    assert first_sustained_time(t, ok, after=6.0, hold_s=3.0) == 6.5     # window 6.5..9.5 is exactly 3.0 s
    assert first_sustained_time(t, ok, after=5, hold_s=0.5) == 5.0   # 5.0..5.5 qualifies at 0.5 s
    assert first_sustained_time(t, ok, after=5, hold_s=1.0) == 6.5
    assert first_sustained_time(t, ok, after=6.0, hold_s=3.5) is None    # run ends before 3.5 s
    assert first_sustained_time([], [], 0, 1.0) is None


# ---- tracker -----------------------------------------------------------------
def test_tracker_intervals_and_isolation_time():
    tr = ConnectivityTracker(n=4)
    for k, iso in enumerate([[], [], [2], [2, 3], [3], [], []]):
        tr.update(k * 1.0, iso)
    s = tr.summary()
    assert s["n_interruptions"] == 1
    assert s["interruptions"][0]["start"] == 2.0 and s["interruptions"][0]["end"] == 5.0
    assert s["interruption_total_s"] == pytest.approx(3.0)
    assert s["isolated_s_per_agent"][2] == pytest.approx(2.0)     # held over [2,4)
    assert s["isolated_s_per_agent"][3] == pytest.approx(2.0)     # held over [3,5)
    assert not s["currently_interrupted"]


def test_tracker_open_interval_and_restoration_counts():
    tr = ConnectivityTracker(n=3)
    for k, iso in enumerate([[], [1], [1], [], [2]]):
        tr.update(float(k), iso)
    s = tr.summary()
    assert s["n_interruptions"] == 2 and s["currently_interrupted"]
    assert s["interruptions"][1]["end"] is None


def test_summarize_series_matches_tracker():
    t = np.arange(0, 7.0)
    k = np.array([0, 0, 1, 2, 1, 0, 0])
    s = summarize_series(t, k)
    assert s["n_interruptions"] == 1
    assert s["interruption_total_s"] == pytest.approx(3.0)
    assert s["interruptions"][0]["end"] == 5.0
    assert summarize_series([], [])["n_interruptions"] == 0


# ---- simulator integration ---------------------------------------------------
def _run(profile=None, seed=42, duration=14.0, mode="adaptive_comm"):
    sim = MultiAgentSimulation(control_mode=mode, seed=seed, record_history=True,
                               fault_profile=profile)
    sim.run(duration)
    return sim, sim.history()


def test_blackout_isolates_everyone_then_restores():
    sim, h = _run(make_fault_profile("blackout", 5.0, 3.0))
    assert h["n_isolated"][h["t"] < 5.5].max() == 0            # connected before the fault
    assert h["n_isolated"][(h["t"] > 6.2) & (h["t"] < 7.8)].min() == sim.n - 1
    assert h["n_components"][(h["t"] > 6.2) & (h["t"] < 7.8)].min() == sim.n
    assert h["lambda2"][(h["t"] > 6.2) & (h["t"] < 7.8)].max() == 0.0
    after = h["t"] > 8.5
    assert h["n_isolated"][after].max() == 0
    assert h["lambda2"][after].min() == pytest.approx(1.0)      # star, unit weights
    iv = sim.conn_tracker.summary()["interruptions"]
    assert len(iv) == 1 and 5.0 < iv[0]["start"] <= 6.2 and 7.9 <= iv[0]["end"] <= 8.3


def test_diagnostics_do_not_change_the_dynamics():
    # pinned in test_supervisor_integration too: same seed, same RMSE as before diagnostics
    sim, h = _run(None, duration=5.0)
    assert np.all(np.isfinite(h["heading_rms"])) and np.all(np.isfinite(h["lambda2"]))


def test_nominal_run_is_connected_and_summary_is_serialisable():
    import json
    sim, h = _run(None, seed=43, duration=10.0)
    assert h["n_isolated"].max() == 0
    c = sim.connectivity_summary()
    json.dumps(c)                                              # must be JSON-safe
    assert c["connected"] and c["scope"].startswith("global diagnostic")
    assert c["closest_approach"]["distance"] is not None and len(c["closest_approach"]["pair"]) == 2


def test_closest_approach_matches_history_minimum():
    sim, h = _run(None, seed=44, duration=8.0)
    assert sim.closest_approach["distance"] == pytest.approx(h["min_distance"].min(), abs=1e-9)


def test_fault_active_flag_follows_schedule():
    sim, h = _run(make_fault_profile("blackout", 5.0, 3.0))
    act = h["fault_active"]
    assert not act[h["t"] < 4.9].any() and act[(h["t"] > 5.1) & (h["t"] < 7.9)].all()
    assert not act[h["t"] > 8.1].any()


def test_heading_wrap_in_sim_state_is_handled():
    sim = MultiAgentSimulation(control_mode="pidr", seed=1)
    sim.step()
    sim._S[:, 2] = np.array([math.pi - 0.01, -math.pi + 0.01, math.pi, -math.pi, 3.14])
    tick = {}
    sim._diagnostics(sim.t, {"n_isolated": 0})
    sim._diagnostics(sim.t, tick)
    assert tick["heading_rms"] < 0.05


# ---- audit findings pinned as tests (docs/EXPERIMENT_PROTOCOL.md, "Audit findings") ----------
def test_known_limitation_adjacent_seeds_share_shifted_channel_streams():
    """Channel seed = seed + offset + follower, so seed s / follower k == seed s+1 / follower k-1.
    Matched-seed comparisons are valid (same streams for every arm) but adjacent seeds are NOT
    independent samples.  Changing this would change every historical result, so it is documented."""
    from simulation.config import Config
    from simulation.messages import MessageBus
    from simulation.network import Network
    a = Network(Config(), MessageBus(10), seed=50)._channel((0, 2))
    b = Network(Config(), MessageBus(10), seed=51)._channel((0, 1))
    assert [a.rng.random() for _ in range(5)] == [b.rng.random() for _ in range(5)]


def test_sparse_uplink_sees_longer_silences_in_seconds_than_downlink():
    """The Gilbert-Elliott chain advances per packet, so a burst of N packets lasts N periods:
    0.05 s per packet on the pose downlink but 0.5 s per packet on the heartbeat uplink.
    Hence a diagnostic graph must use per-direction timeouts (config.connectivity_*_timeout_s)."""
    down, up = [], []
    for seed in range(42, 47):
        sim = MultiAgentSimulation(control_mode="pidr", seed=seed)
        for _ in range(int(30 / sim.dt)):
            sim.step()
            for f in range(1, sim.n):
                st_d, st_u = sim.network._stats.get((0, f)), sim.network._stats.get((f, 0))
                if st_d is None or st_u is None:
                    continue
                down.append(sim.t - st_d.last_rx_time)
                up.append(sim.t - st_u.last_rx_time)
    assert max(up) > 1.0 > 0 and max(up) > 2 * max(down)
    assert max(down) < sim.cfg.connectivity_downlink_timeout_s * 1.5      # downlink timeout is sane
    assert sim.cfg.heartbeat_period / sim.dt == pytest.approx(10.0)


def test_derivative_term_makes_command_chatter_with_sensor_noise():
    """Audit finding: with sensor sigma 0.025 m the speed command chatters between the rails;
    with sigma = 0 it is smooth.  Not 'fixed' (would change the published model)."""
    from experiments.run_benchmark import gentle_trajectory
    out = {}
    for sig in (None, 0.0):
        sim = MultiAgentSimulation(control_mode="pidr", seed=42, record_history=True,
                                   leader_trajectory=gentle_trajectory, sensor_sigma=sig)
        sim.run(10.0)
        v = sim.history()["v_cmd"][:, 1:]
        out[sig] = (float(np.abs(np.diff(v, axis=0)).mean()), float(np.mean(np.abs(v) >= sim.cfg.max_v - 1e-9)))
    assert out[None][0] > 5 * out[0.0][0]
    assert out[0.0][1] < 0.02 < out[None][1]
