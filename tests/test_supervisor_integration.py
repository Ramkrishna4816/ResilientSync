"""Supervisor <-> adaptive_comm integration and regression tests."""
import numpy as np
import pytest

from simulation.agent import AgentMode
from simulation.config import Config
from simulation.metrics import compute_metrics
from simulation.network import make_fault_profile
from simulation.simulation import CONTROL_MODES, MultiAgentSimulation
from simulation.supervisor import STATE_CODES, SupervisorConfig

BLACKOUT = make_fault_profile("blackout", 5.0, 3.0)


def run(mode, seed=42, duration=18.0, sup=True, profile=BLACKOUT, **kw):
    sim = MultiAgentSimulation(control_mode=mode, seed=seed, record_history=True,
                               cfg=Config(supervisor_enabled=sup), fault_profile=profile, **kw)
    sim.run(duration)
    return sim, sim.history()


# Values measured on the unmodified controller path (pre-supervisor) with the
# original forced-loss runner; the blackout profile reproduces that RNG stream.
PRE_SUPERVISOR_ADAPTIVE_RMSE_SEED42 = 1.6854586513790624
BASELINE_PIDR_RMSE_SEED42 = 1.5434555195362332    # == experiments/results CSV


def test_supervisor_disabled_reproduces_pre_supervisor_adaptive_controller():
    _, h = run("adaptive_comm", sup=False)
    assert compute_metrics(h)["RMSE"] == pytest.approx(PRE_SUPERVISOR_ADAPTIVE_RMSE_SEED42, abs=1e-9)


def test_other_controllers_are_untouched_and_match_the_committed_baseline():
    _, h = run("pidr")
    assert compute_metrics(h)["RMSE"] == pytest.approx(BASELINE_PIDR_RMSE_SEED42, abs=1e-9)


@pytest.mark.parametrize("mode", [m for m in CONTROL_MODES if m != "adaptive_comm"])
def test_supervisor_is_inert_for_baseline_controllers(mode):
    sim, h = run(mode, duration=8.0, sup=True)
    assert (h["supervisor_state"] == 0).all()
    assert all(s.transitions == [] for s in sim.supervisors.values())
    _, h2 = run(mode, duration=8.0, sup=False)
    np.testing.assert_array_equal(h["states"], h2["states"])      # flag has no effect


def test_supervisor_goes_normal_hold_recovering_normal_through_a_blackout():
    sim, h = run("adaptive_comm")
    for sup in sim.supervisors.values():
        seq = [(r.src, r.dst) for r in sup.transitions]
        assert ("NORMAL", "HOLD") in seq or ("DEGRADED", "HOLD") in seq
        assert ("HOLD", "RECOVERING") in seq
        assert ("RECOVERING", "NORMAL") in seq                      # ramp completed
        hold = next(r for r in sup.transitions if r.dst == "HOLD")
        assert 5.0 <= hold.t <= 7.5                                 # during the blackout
        rec = next(r for r in sup.transitions if r.dst == "RECOVERING")
        assert rec.t >= 8.0                                         # only after it ends
        assert all(r.reason for r in sup.transitions)
    assert (h["supervisor_state"][:100, 1:] <= 1).all()             # no HOLD/RECOVERING before t = 5 s


def test_transition_reasons_describe_the_real_values():
    sim, _ = run("adaptive_comm")
    sup = sim.supervisors[1]
    hold = next(r for r in sup.transitions if r.dst == "HOLD")
    assert "maximum permitted age" in hold.reason
    assert f"{hold.age:.2f}" in hold.reason


def test_commands_stay_within_actuator_limits_with_supervisor_active():
    cfg = Config()
    _, h = run("adaptive_comm", profile=make_fault_profile("blackout", 3.0, 6.0))
    v, w = h["v_cmd"][:, 1:], h["w_cmd"][:, 1:]
    assert np.isfinite(v).all() and np.isfinite(w).all()
    assert v.max() <= cfg.max_v + 1e-12 and v.min() >= -0.25 - 1e-12
    assert np.abs(w).max() <= cfg.max_w + 1e-12


def test_hold_speed_limit_is_enforced_on_commands():
    sc = SupervisorConfig(hold_speed_frac=0.5)
    sim, h = run("adaptive_comm", profile=make_fault_profile("blackout", 3.0, 8.0),
                 supervisor_cfg=sc, duration=12.0)
    cfg = sim.cfg
    deep_hold = h["caution"][:, 1:] >= 0.999
    assert deep_hold.any()
    assert h["v_cmd"][:, 1:][deep_hold].max() <= cfg.max_v * 0.5 + 1e-12


def test_supervisor_is_deterministic_across_identical_runs():
    a, ha = run("adaptive_comm", seed=9, duration=10.0)
    b, hb = run("adaptive_comm", seed=9, duration=10.0)
    np.testing.assert_array_equal(ha["states"], hb["states"])
    assert [r.as_dict() for r in a.supervisors[2].transitions] == \
           [r.as_dict() for r in b.supervisors[2].transitions]


def test_supervisor_is_suspended_when_follower_leaves_formation_following():
    sim = MultiAgentSimulation(control_mode="adaptive_comm", seed=4, fault_profile=BLACKOUT)
    sim.run(6.5)                                       # inside the blackout -> HOLD
    assert sim.supervisors[1].state.value == "HOLD"
    sim.agents[1].set_mode(AgentMode.STOPPED)          # (a SCATTER packet could not
    sim.run(0.2)                                       #  arrive during a blackout)
    assert sim.supervisors[1].state.value == "NORMAL"
    assert sim.supervisors[1].transitions[-1].kind == "reset"
    assert "left formation-following" in sim.supervisors[1].transitions[-1].reason


def test_long_blackout_stays_finite_and_collision_free():
    _, h = run("adaptive_comm", profile=make_fault_profile("blackout", 4.0, 10.0), duration=20.0)
    assert np.isfinite(h["states"]).all()
    assert h["min_distance"].min() > Config().collision_distance


def test_supervisor_config_can_be_swapped_via_constructor():
    sc = SupervisorConfig(hold_enter_age_s=0.6, hold_exit_age_s=0.3)
    sim = MultiAgentSimulation(control_mode="adaptive_comm", seed=1, supervisor_cfg=sc)
    assert sim.cfg.supervisor.hold_enter_age_s == 0.6
    assert sim.supervisors[1].cfg is sc
