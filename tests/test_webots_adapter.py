"""Adapter behaviour: external-plant hook, frame invariance, crash reporting, cross-checks."""
import numpy as np
import pytest
from resilientsync_webots.testing import SC, run_short
from experiments.run_benchmark import ARMS
from resilientsync_webots.adapter import WebotsAdapter
from resilientsync_webots.analysis import python_reference, run_metrics
from resilientsync_webots.frames import FrameMap
from resilientsync_webots.standin import EngineKinematicsPlant, StandInPlant
from simulation.simulation import MultiAgentSimulation


def test_default_engine_path_is_unchanged_by_the_hook():
    # two native runs (hook present, external_plant False) are identical, and the plant is still RK4
    cfg = ARMS["adaptive_supervisor"].build_cfg()
    a = MultiAgentSimulation(cfg=cfg, control_mode="adaptive_comm", seed=7); a.run(5.0)
    b = MultiAgentSimulation(cfg=cfg, control_mode="adaptive_comm", seed=7); b.run(5.0)
    assert not a.external_plant and np.array_equal(a.states(), b.states())
    assert a.states()[0, 0] > 1.0                                    # the leader actually moved


def test_external_mode_does_not_integrate_or_clamp_and_stores_commands():
    ad = WebotsAdapter(SC["nominal_gentle"], ARMS["adaptive_supervisor"], seed=1, n_agents=5)
    S = ad.initial_states(); S[2, 0] = 999.0                       # absurd, outside the world: must not be clamped
    before = S.copy()
    out = ad.step(0.0, S)
    assert np.array_equal(ad.sim.states(), before)                   # engine never rewrote the measured poses
    assert out.commands.shape == (5, 2) and np.isfinite(out.commands).all()
    assert set(ad.sim.cmd_out) == set(range(5))


def test_set_measured_states_validates_shape():
    ad = WebotsAdapter(SC["nominal"], ARMS["pidr"], seed=1, n_agents=3)
    with pytest.raises(ValueError):
        ad.sim.set_measured_states(np.zeros((4, 5)))


def test_results_invariant_to_world_frame_offset_and_rotation():
    a, _ = run_short("blackout_gentle", duration=10.0, plant=StandInPlant(5, FrameMap()))
    b, _ = run_short("blackout_gentle", duration=10.0, plant=StandInPlant(5, FrameMap(3.0, -2.0, 0.5)))
    assert np.allclose(a["steps"].formation_rms, b["steps"].formation_rms, atol=1e-6)
    assert np.allclose(a["steps"].gt_x_1, b["steps"].gt_x_1, atol=1e-6)       # logged in the RS frame


def test_engine_plant_cross_check_against_native_simulator():
    # same engine, same seed, same scenario, same plant model: only the adapter's ordering differs
    for seed in (100, 101):
        ref = python_reference(SC["nominal_gentle"], ARMS["adaptive_supervisor"], seed)
        run, _ = run_short("nominal_gentle", seed=seed, duration=18.0, plant=EngineKinematicsPlant(5))
        m = run_metrics(run)
        assert abs(m["RMSE"] - ref["RMSE"]) < 0.03
        assert abs(m["MinSep"] - ref["MinSep"]) < 0.1


def test_controller_exception_is_reported_not_hidden():
    class Boom(StandInPlant):
        def measure(self):
            if self.t > 1.0:
                raise RuntimeError("synthetic failure")
            return super().measure()
    run, meta = run_short("nominal", duration=5.0, plant=Boom(5))
    assert meta["status"] == "controller_error" and "synthetic failure" in meta["error"]


def test_all_four_arms_run_through_the_same_interface():
    for arm in ("pidr", "advanced", "adaptive_legacy", "adaptive_supervisor"):
        run, meta = run_short("blackout_gentle", arm=arm, duration=10.0)
        assert meta["status"] == "completed", arm
        assert run["meta"]["supervisor_active"] == (arm == "adaptive_supervisor")


def test_clock_skew_is_zero_for_standin_and_reported():
    _, meta = run_short("nominal", duration=3.0)
    assert meta["max_time_skew_s"] < 1e-6
