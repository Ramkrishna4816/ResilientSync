"""Command conversion (v, omega) <-> wheel velocities."""
import math
import pytest
from resilientsync_webots.diffdrive import cmd_to_wheels, wheels_to_cmd
from resilientsync_webots.robot_params import MAX_WHEEL_RAD_S, TRACK, WHEEL_RADIUS


def test_straight_line():
    c = cmd_to_wheels(1.0, 0.0)
    assert c.left == pytest.approx(c.right) and c.left == pytest.approx(1.0 / WHEEL_RADIUS)
    assert not c.saturated and c.scale == 1.0


def test_spin_in_place():
    c = cmd_to_wheels(0.0, 1.0)
    assert c.left == pytest.approx(-c.right)
    assert c.right == pytest.approx(0.5 * TRACK / WHEEL_RADIUS)


def test_positive_omega_turns_left_means_right_wheel_faster():
    c = cmd_to_wheels(0.5, 0.8)
    assert c.right > c.left


@pytest.mark.parametrize("v,w", [(0.0, 0.0), (1.25, 0.0), (0.4, -1.2), (-0.3, 0.5), (1.0, 2.4)])
def test_roundtrip_when_unsaturated(v, w):
    c = cmd_to_wheels(v, w)
    assert not c.saturated
    assert wheels_to_cmd(c.left, c.right) == pytest.approx((v, w), abs=1e-12)


def test_saturation_scales_both_wheels_and_preserves_curvature():
    v, w = 3.0, 4.0                              # far above the motor limit
    c = cmd_to_wheels(v, w)
    assert c.saturated and 0.0 < c.scale < 1.0
    assert max(abs(c.left), abs(c.right)) == pytest.approx(MAX_WHEEL_RAD_S)
    v2, w2 = wheels_to_cmd(c.left, c.right)
    assert v2 / w2 == pytest.approx(v / w)       # same turning radius
    assert (v2, w2) == pytest.approx((v * c.scale, w * c.scale))


def test_documented_command_limits_do_not_saturate():
    # engine limits: max_v 1.25 m/s with max_w 2.4 rad/s must fit inside the 20 rad/s motor limit
    from simulation.config import Config
    cfg = Config()
    assert not cmd_to_wheels(cfg.max_v, cfg.max_w).saturated


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_command_stops_robot(bad):
    c = cmd_to_wheels(bad, 0.0)
    assert (c.left, c.right) == (0.0, 0.0) and c.saturated
    c = cmd_to_wheels(0.0, bad)
    assert (c.left, c.right) == (0.0, 0.0)
