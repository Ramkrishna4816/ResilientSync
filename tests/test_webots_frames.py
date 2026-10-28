"""Coordinate conversion Webots <-> ResilientSync frame."""
import math
import numpy as np
import pytest
from resilientsync_webots.frames import (FrameMap, measured_state, rotation_from_yaw,
                                         wrap_angle, yaw_from_rotation_matrix)
from resilientsync_webots.robot_params import ROBOT_Z


def rot9(th):
    c, s = math.cos(th), math.sin(th)
    return [c, -s, 0, s, c, 0, 0, 0, 1]          # Webots getOrientation(): row-major, z-up


@pytest.mark.parametrize("th", [0.0, 0.5, math.pi / 2, 3.0, -2.2, -math.pi / 2 + 1e-3])
def test_yaw_from_rotation_matrix(th):
    assert yaw_from_rotation_matrix(rot9(th)) == pytest.approx(wrap_angle(th), abs=1e-12)


def test_yaw_axes_convention():
    # robot pointing +y (North in ENU) has yaw +90 deg
    assert yaw_from_rotation_matrix(rot9(math.pi / 2)) == pytest.approx(math.pi / 2)


@pytest.mark.parametrize("fm", [FrameMap(), FrameMap(3.0, -2.0, 0.5), FrameMap(-7.5, 4.0, -2.9)])
def test_roundtrip_position_and_yaw(fm):
    rs = np.array([1.3, -0.7])
    assert fm.world_to_rs_xy(fm.rs_to_world_xy(rs)) == pytest.approx(rs, abs=1e-12)
    for th in (0.0, 1.0, -3.0, 3.1):
        assert fm.world_to_rs_yaw(fm.rs_to_world_yaw(th)) == pytest.approx(wrap_angle(th), abs=1e-12)


def test_identity_map_is_identity():
    fm = FrameMap()
    assert fm.rs_to_world_xy([2.0, 3.0]) == pytest.approx([2.0, 3.0])
    assert fm.world_translation([2.0, 3.0]) == [2.0, 3.0, ROBOT_Z]


def test_rotated_map_known_value():
    fm = FrameMap(1.0, 2.0, math.pi / 2)          # RS +x axis points world +y
    assert fm.rs_to_world_xy([1.0, 0.0]) == pytest.approx([1.0, 3.0], abs=1e-12)
    assert fm.rs_to_world_yaw(0.0) == pytest.approx(math.pi / 2)


def test_measured_state_forward_speed_projection():
    th = math.radians(30)
    vel = [2 * math.cos(th), 2 * math.sin(th), 0.0, 0, 0, 0.4]
    s = measured_state([5.0, 6.0, 0.0975], rot9(th), vel, FrameMap())
    assert s == pytest.approx([5.0, 6.0, th, 2.0, 0.4], abs=1e-9)


def test_measured_state_sideways_velocity_gives_zero_forward_speed():
    s = measured_state([0, 0, 0], rot9(0.0), [0.0, 1.0, 0, 0, 0, 0], FrameMap())
    assert s[3] == pytest.approx(0.0, abs=1e-12)


def test_measured_state_in_rotated_frame():
    fm = FrameMap(3.0, -2.0, 0.5)
    rs = np.array([4.0, 1.0])
    w = fm.rs_to_world_xy(rs)
    s = measured_state([w[0], w[1], 0.0], rot9(fm.rs_to_world_yaw(0.8)), [0, 0, 0, 0, 0, 0], fm)
    assert s[:3] == pytest.approx([4.0, 1.0, 0.8], abs=1e-12)


def test_rotation_from_yaw_is_z_axis_angle():
    assert rotation_from_yaw(0.7) == [0.0, 0.0, 1.0, 0.7]


def test_tilt_from_rotation_matrix():
    from resilientsync_webots.frames import tilt_from_rotation_matrix
    assert tilt_from_rotation_matrix(rot9(1.2)) == pytest.approx((0.0, 0.0), abs=1e-12)     # pure yaw is not tilt
    a = 0.1                                                                                  # rotation about +y
    Ry = [math.cos(a), 0, math.sin(a), 0, 1, 0, -math.sin(a), 0, math.cos(a)]
    assert tilt_from_rotation_matrix(Ry) == pytest.approx((0.0, a), abs=1e-12)
    Rx = [1, 0, 0, 0, math.cos(a), -math.sin(a), 0, math.sin(a), math.cos(a)]               # rotation about +x
    assert tilt_from_rotation_matrix(Rx) == pytest.approx((a, 0.0), abs=1e-12)
