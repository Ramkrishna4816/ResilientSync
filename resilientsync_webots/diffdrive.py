"""Unicycle command (v, omega) <-> differential-drive wheel speeds."""
from __future__ import annotations

import math
from typing import NamedTuple

from .robot_params import MAX_WHEEL_RAD_S, TRACK, WHEEL_RADIUS


class WheelCommand(NamedTuple):
    left: float          # [rad/s]
    right: float         # [rad/s]
    saturated: bool      # True if the command had to be scaled to the motor limit
    scale: float         # factor applied to both wheels (1.0 = none)


def cmd_to_wheels(v: float, w: float, radius: float = WHEEL_RADIUS, track: float = TRACK,
                  max_wheel: float = MAX_WHEEL_RAD_S) -> WheelCommand:
    """wl = (v - w*track/2)/r, wr = (v + w*track/2)/r.

    If either wheel exceeds `max_wheel`, both are scaled by the same factor (curvature is
    preserved, speed is reduced).  Non-finite input gives a stop command (0, 0).
    """
    if not (math.isfinite(v) and math.isfinite(w)):
        return WheelCommand(0.0, 0.0, True, 0.0)
    wl = (v - 0.5 * w * track) / radius
    wr = (v + 0.5 * w * track) / radius
    peak = max(abs(wl), abs(wr))
    if peak > max_wheel:
        k = max_wheel / peak
        return WheelCommand(wl * k, wr * k, True, k)
    return WheelCommand(wl, wr, False, 1.0)


def wheels_to_cmd(wl: float, wr: float, radius: float = WHEEL_RADIUS, track: float = TRACK):
    """Forward kinematics: (v, omega) realised by wheel speeds (rad/s)."""
    return radius * (wl + wr) / 2.0, radius * (wr - wl) / track
