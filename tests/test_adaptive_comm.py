import numpy as np
import pytest

from simulation.config import Config
from simulation.controller import (
    FollowerController,
    estimate_communication_quality,
)
from simulation.simulation import CONTROL_MODES, MultiAgentSimulation, simulate


def test_communication_quality_is_bounded_and_decreases_with_age_and_loss():
    fresh = estimate_communication_quality(age=0.0, loss_rate=0.0, age_tau=0.8)
    stale = estimate_communication_quality(age=1.6, loss_rate=0.0, age_tau=0.8)
    lossy = estimate_communication_quality(age=0.0, loss_rate=0.5, age_tau=0.8)

    assert fresh == pytest.approx(1.0)
    assert 0.0 <= stale < fresh
    assert lossy == pytest.approx(0.5)
    assert estimate_communication_quality(float("inf"), 0.0) == 0.0
    assert estimate_communication_quality(0.0, 2.0) == 0.0


def test_adaptive_comm_is_registered_and_existing_modes_remain_available():
    assert CONTROL_MODES == ("zoh", "pidr", "advanced", "adaptive_comm")
    for mode in ("zoh", "pidr", "advanced", "adaptive_comm"):
        history = simulate(mode=mode, seed=17, duration=1.0, legacy=False)
        assert history["states"].shape[1] == Config().n_agents
        assert np.isfinite(history["formation_rms"]).all()


def test_adaptive_comm_history_contains_finite_quality_scores():
    history = simulate(mode="adaptive_comm", seed=42, duration=2.0, legacy=False)
    quality = history["communication_quality"]
    assert quality.shape[0] == len(history["t"])
    assert np.isfinite(quality).all()
    assert ((quality >= 0.0) & (quality <= 1.0)).all()


def test_receiver_infers_missing_pose_sequences_during_forced_blackout():
    sim = MultiAgentSimulation(control_mode="adaptive_comm", seed=23,
                               record_history=True, cfg=Config())
    sim.run(1.0)
    quality_before = np.mean([estimate_communication_quality(
        max(0.0, sim.t - f.rx_time),
        sum(f.pose_delivery_window) / len(f.pose_delivery_window)
        if f.pose_delivery_window else 0.0,
        sim.cfg.adaptive_comm_age_tau) for f in sim.followers])

    sim.network.set_forced_loss(True)
    sim.run(1.5)
    quality_after = np.mean([estimate_communication_quality(
        max(0.0, sim.t - f.rx_time),
        sum(f.pose_delivery_window) / len(f.pose_delivery_window)
        if f.pose_delivery_window else 0.0,
        sim.cfg.adaptive_comm_age_tau) for f in sim.followers])

    assert quality_after < quality_before
    assert all(len(f.pose_delivery_window) > 0 for f in sim.followers)


def test_existing_advanced_mode_is_deterministic_for_fixed_seed():
    a = simulate(mode="advanced", seed=42, duration=2.0, loss_scale=1.0, legacy=False)
    b = simulate(mode="advanced", seed=42, duration=2.0, loss_scale=1.0, legacy=False)
    np.testing.assert_array_equal(a["states"], b["states"])
    np.testing.assert_array_equal(a["formation_rms"], b["formation_rms"])


def test_web_api_accepts_adaptive_comm_mode():
    from fastapi.testclient import TestClient
    from web.app import create_app

    with TestClient(create_app()) as client:
        response = client.post("/sim/reset", json={"control_mode": "adaptive_comm", "seed": 42})
        assert response.status_code == 200
        assert response.json()["ok"] is True
        state = client.get("/state").json()
        assert state["control_mode"] == "adaptive_comm"
        assert "communication_quality" in state["agents"][1]

def test_adaptive_comm_caps_total_speed_when_communication_is_stale():
    # The total-speed cap is now an explicit opt-in (it was removed from the
    # default path; see HANDOFF.md).  This test pins the opt-in behaviour.
    cfg = Config(adaptive_comm_total_speed_cap=True)
    controller = FollowerController(cfg)

    state = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
    target = np.array([10.0, 0.0])
    zero_vector = np.zeros(2)
    leader_est = np.array([0.0, 0.0, 0.0, cfg.max_v, 0.0])
    leader_xy_true = np.array([100.0, 100.0])

    v_cmd, _, _, _ = controller.formation_command(
        state=state,
        target=target,
        neighbor_force=zero_vector,
        avoid=zero_vector,
        leader_est=leader_est,
        leader_xy_true=leader_xy_true,
        advanced=False,
        rng=np.random.default_rng(42),
        sigma=0.0,
        dt=0.1,
        communication_quality=0.0,
        adaptive_comm=True,
    )

    expected_cap = cfg.max_v * cfg.adaptive_comm_min_speed_scale

    assert np.isfinite(v_cmd)
    assert abs(v_cmd) <= expected_cap + 1e-9


def test_total_speed_cap_is_off_by_default_and_feedforward_is_scaled_instead():
    cfg = Config()
    assert cfg.adaptive_comm_total_speed_cap is False
    controller = FollowerController(cfg)
    state = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
    zero = np.zeros(2)
    v_cmd, _, _, _ = controller.formation_command(
        state=state, target=np.array([10.0, 0.0]), neighbor_force=zero, avoid=zero,
        leader_est=np.array([0.0, 0.0, 0.0, cfg.max_v, 0.0]),
        leader_xy_true=np.array([100.0, 100.0]), advanced=False,
        rng=np.random.default_rng(42), sigma=0.0, dt=0.1,
        communication_quality=0.0, adaptive_comm=True)
    assert v_cmd > cfg.max_v * cfg.adaptive_comm_min_speed_scale
    assert v_cmd <= cfg.max_v + 1e-12
