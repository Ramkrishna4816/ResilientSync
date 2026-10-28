"""Independent unit tests for the resilience supervisor state machine."""
import math

import pytest

from simulation.supervisor import (LEGAL_TRANSITIONS, IllegalTransitionError,
                                   ResilienceSupervisor, SupervisorConfig,
                                   SupervisorState as S, is_legal_transition)

DT = 0.05
# Explicit thresholds so the state-machine tests do not depend on the
# calibrated defaults (which are tied to the simulated channel).
CFG = SupervisorConfig(degrade_enter_q=0.60, degrade_exit_q=0.80, hold_enter_age_s=1.0,
                       hold_exit_age_s=0.40, recovery_exit_q=0.70)


def drive(sup, t0, t1, q, age, dt=DT, age_fn=None):
    """Feed constant (q, age) from t0 (inclusive) to t1 (exclusive)."""
    t, out = t0, None
    while t < t1 - 1e-9:
        out = sup.update(t, q, age_fn(t) if age_fn else age)
        t += dt
    return out, t


def to_hold(sup, t0=0.0):
    """Healthy start, then silence until HOLD; returns time after HOLD entry."""
    _, t = drive(sup, t0, t0 + 0.5, 1.0, 0.0)
    # age grows linearly from 0 -> stale; quality collapses accordingly
    start = t
    while sup.state != S.HOLD and t < start + 10:
        age = t - start
        sup.update(t, math.exp(-age / 0.8), age)
        t += DT
    assert sup.state == S.HOLD
    return t


def test_starts_normal_with_no_transitions():
    sup = ResilienceSupervisor(CFG)
    d = sup.update(0.0, 1.0, 0.0)
    assert d.state == S.NORMAL and sup.transitions == []
    assert (d.ff_scale, d.speed_frac, d.avoid_scale) == (1.0, 1.0, 1.0)


def test_legal_transition_table_is_closed_and_hold_only_exits_to_recovering():
    assert LEGAL_TRANSITIONS[S.HOLD] == {S.RECOVERING}
    assert not is_legal_transition(S.NORMAL, S.RECOVERING)
    assert not is_legal_transition(S.HOLD, S.NORMAL)
    assert not is_legal_transition(S.HOLD, S.DEGRADED)
    sup = ResilienceSupervisor(CFG)
    with pytest.raises(IllegalTransitionError):
        sup._transition(S.RECOVERING, 0.0, "illegal on purpose", 1.0, 0.0)


def test_degraded_requires_dwell_and_records_actual_reason():
    sup = ResilienceSupervisor(CFG)
    sup.update(0.0, 1.0, 0.0)
    sup.update(0.05, 0.5, 0.2)                       # below 0.60, dwell not met
    assert sup.state == S.NORMAL
    sup.update(0.10, 0.5, 0.2)
    d = sup.update(0.15, 0.5, 0.2)                   # held 0.10 s
    assert d.state == S.DEGRADED and d.transitioned
    rec = sup.transitions[-1]
    assert (rec.src, rec.dst) == ("NORMAL", "DEGRADED")
    assert "DEGRADED" in rec.reason and "0.50" in rec.reason and "0.60" in rec.reason
    assert rec.t == pytest.approx(0.15)


def test_single_sample_glitch_does_not_degrade():
    sup = ResilienceSupervisor(CFG)
    sup.update(0.0, 1.0, 0.0)
    sup.update(0.05, 0.3, 0.1)
    sup.update(0.10, 1.0, 0.0)
    sup.update(0.15, 1.0, 0.0)
    assert sup.state == S.NORMAL and sup.transitions == []


def test_hysteresis_band_prevents_chatter():
    sup = ResilienceSupervisor(CFG)
    sup.update(0.0, 1.0, 0.0)
    drive(sup, 0.05, 1.0, 0.5, 0.2)                  # -> DEGRADED
    assert sup.state == S.DEGRADED
    n = len(sup.transitions)
    # quality oscillates inside the hysteresis band (0.60 .. 0.80): no change
    t, flip = 1.0, False
    while t < 6.0:
        sup.update(t, 0.62 if flip else 0.78, 0.2)
        flip = not flip
        t += DT
    assert sup.state == S.DEGRADED and len(sup.transitions) == n


def test_degraded_returns_to_normal_after_exit_dwell():
    sup = ResilienceSupervisor(CFG)
    sup.update(0.0, 1.0, 0.0)
    drive(sup, 0.05, 1.0, 0.5, 0.2)
    _, t = drive(sup, 1.0, 1.3, 0.9, 0.05)           # exit dwell is 0.5 s
    assert sup.state == S.DEGRADED
    drive(sup, t, t + 0.4, 0.9, 0.05)
    assert sup.state == S.NORMAL
    assert "Returned to NORMAL" in sup.transitions[-1].reason


def test_hold_entered_when_message_age_exceeds_limit_immediately_from_normal():
    sup = ResilienceSupervisor(CFG)
    sup.update(0.0, 1.0, 0.0)
    d = sup.update(0.05, 0.9, 1.01)                  # age beyond 1.00 s
    assert d.state == S.HOLD
    rec = sup.transitions[-1]
    assert (rec.src, rec.dst) == ("NORMAL", "HOLD")
    assert "maximum permitted age" in rec.reason and "1.01" in rec.reason


def test_full_blackout_cycle_normal_hold_recovering_normal():
    sup = ResilienceSupervisor(CFG)
    t = to_hold(sup)
    # link returns: fresh messages, but quality estimate is still low
    drive(sup, t, t + 0.2, 0.1, 0.1)
    assert sup.state == S.HOLD                       # 0.30 s dwell not yet met
    _, t = drive(sup, t + 0.2, t + 0.5, 0.1, 0.1)
    assert sup.state == S.RECOVERING
    assert "Entered RECOVERING after" in sup.transitions[-1].reason
    # caution decreases monotonically, stays > 0 while recovering
    levels = []
    for _ in range(10):
        levels.append(sup.update(t, 0.3, 0.05).caution)
        t += DT
    assert all(b <= a + 1e-12 for a, b in zip(levels, levels[1:]))
    # quality recovers -> NORMAL once ramp done
    drive(sup, t, t + 3.0, 0.95, 0.05)
    assert sup.state == S.NORMAL
    assert [(r.src, r.dst) for r in sup.transitions][-2:] == [
        ("HOLD", "RECOVERING"), ("RECOVERING", "NORMAL")]
    assert "recovery ramp completed" in sup.transitions[-1].reason


def test_recovering_goes_back_to_hold_if_link_dies_again():
    sup = ResilienceSupervisor(CFG)
    t = to_hold(sup)
    _, t = drive(sup, t, t + 0.4, 0.1, 0.1)
    assert sup.state == S.RECOVERING
    sup.update(t, 0.2, 1.5)
    assert sup.state == S.HOLD


def test_hold_exit_is_age_based_hysteresis():
    sup = ResilienceSupervisor(CFG)
    t = to_hold(sup)
    # age between hold_exit (0.40) and hold_enter (1.00): stays HOLD
    drive(sup, t, t + 3.0, 0.5, 0.7)
    assert sup.state == S.HOLD


def test_caution_modifiers_are_bounded_and_never_a_stop():
    cfg = CFG
    sup = ResilienceSupervisor(cfg)
    t = to_hold(sup)
    d, _ = drive(sup, t, t + 2.0, 0.0, 2.0)
    assert 0.0 < d.speed_frac <= 1.0 and d.speed_frac >= cfg.hold_speed_frac - 1e-9
    assert cfg.hold_ff_scale - 1e-9 <= d.ff_scale <= 1.0
    assert 1.0 <= d.avoid_scale <= cfg.hold_avoid_scale + 1e-9
    assert d.caution == pytest.approx(1.0)


def test_caution_rises_with_rate_limit_not_instantly():
    sup = ResilienceSupervisor(CFG)
    sup.update(0.0, 1.0, 0.0)
    d1 = sup.update(0.05, 0.0, 5.0)                  # HOLD entered
    d2 = sup.update(0.10, 0.0, 5.0)
    assert d1.state == S.HOLD and d2.caution <= 3.0 * 0.05 + 1e-9 + d1.caution


def test_deterministic_for_identical_inputs():
    seq = [(0.05 * k, max(0.0, 1.0 - 0.02 * (k % 40)), 0.03 * (k % 70)) for k in range(400)]
    a, b = ResilienceSupervisor(CFG), ResilienceSupervisor(CFG)
    for t, q, age in seq:
        da, db = a.update(t, q, age), b.update(t, q, age)
        assert da == db
    assert a.transitions == b.transitions and a.durations == b.durations


def test_reset_clears_everything_and_allows_time_restart():
    sup = ResilienceSupervisor(CFG)
    to_hold(sup)
    assert sup.transitions
    sup.reset()
    assert sup.state == S.NORMAL and sup.transitions == [] and sup.caution == 0.0
    assert all(v == 0.0 for v in sup.durations.values())
    sup.update(0.0, 1.0, 0.0)                        # time may restart at 0


def test_reset_with_reason_logs_a_reset_record_and_keeps_history():
    sup = ResilienceSupervisor(CFG)
    to_hold(sup)
    n = len(sup.transitions)
    sup.reset(t=9.0, reason="Reset: follower left formation-following mode.")
    assert sup.state == S.NORMAL and len(sup.transitions) == n + 1
    assert sup.transitions[-1].kind == "reset"
    assert sup.last_reason.startswith("Reset")


def test_time_going_backwards_is_rejected():
    sup = ResilienceSupervisor(CFG)
    sup.update(1.0, 1.0, 0.0)
    with pytest.raises(ValueError, match="backwards"):
        sup.update(0.5, 1.0, 0.0)


@pytest.mark.parametrize("q,age", [(float("nan"), 0.0), (None, 0.0), (0.9, None),
                                   (0.9, float("nan")), (0.9, -1.0), ("x", 0.0)])
def test_invalid_inputs_are_treated_as_worst_case_and_counted(q, age):
    sup = ResilienceSupervisor(CFG)
    sup.update(0.0, 1.0, 0.0)
    d = sup.update(0.05, q, age)
    assert sup.invalid_inputs == 1
    assert 0.0 <= d.quality <= 1.0
    assert sup.state in (S.HOLD, S.NORMAL)           # never crashes


def test_missing_message_infinite_age_enters_hold():
    sup = ResilienceSupervisor(CFG)
    sup.update(0.0, 1.0, 0.0)
    d = sup.update(0.05, 0.0, math.inf)
    assert d.state == S.HOLD and "inf" in sup.transitions[-1].reason


def test_time_in_state_accounting_sums_to_elapsed_time():
    sup = ResilienceSupervisor(CFG)
    t = to_hold(sup)
    drive(sup, t, t + 4.0, 0.95, 0.05)
    assert sum(sup.durations.values()) == pytest.approx(t + 4.0 - DT - 0.0, abs=2 * DT)
    snap = sup.snapshot()
    assert snap["state"] == sup.state.value
    assert sum(snap["duration_fraction"].values()) == pytest.approx(1.0, abs=1e-3)


@pytest.mark.parametrize("kwargs", [
    dict(degrade_enter_q=0.8, degrade_exit_q=0.6),
    dict(hold_exit_age_s=1.5, hold_enter_age_s=1.0),
    dict(hold_speed_frac=0.0),
    dict(hold_ff_scale=1.5),
    dict(hold_avoid_scale=0.5),
    dict(recovery_ramp_s=0.0),
    dict(min_state_time_s=-1.0),
    dict(degrade_enter_q=float("nan")),
    dict(degraded_caution=2.0),
])
def test_config_validation_rejects_bad_values(kwargs):
    with pytest.raises(ValueError):
        SupervisorConfig(**kwargs)


def test_default_config_is_valid_and_sits_outside_the_nominal_channel_envelope():
    d = SupervisorConfig()
    assert d.degrade_enter_q < 0.40          # nominal 5th-percentile quality
    assert d.hold_enter_age_s > 1.1          # nominal worst-case message age
    assert d.recovery_exit_q >= d.degrade_enter_q
