"""Coordinate-frame mapping between Webots world and the ResilientSync (RS) frame.

Webots world: ENU (x East, y North, z Up) -- set explicitly in the .wbt (`coordinateSystem "ENU"`).
RS frame:     planar x, y, theta (counter-clockwise about +z), identical axes to ENU.
The default map is the identity (RS origin == Webots origin).  `FrameMap` allows an
offset + rotation so the adapter can be tested for frame-correctness.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .robot_params import ROBOT_Z


def wrap_angle(a: float) -> float:
    return float((a + math.pi) % (2 * math.pi) - math.pi)


def yaw_from_rotation_matrix(R) -> float:
    """Yaw about +z from Webots `getOrientation()` (9 values, row-major, z-up)."""
    return math.atan2(R[3], R[0])


def rotation_from_yaw(theta: float):
    """Webots SFRotation (axis-angle) for a yaw about +z."""
    return [0.0, 0.0, 1.0, float(theta)]


@dataclass(frozen=True)
class FrameMap:
    """world = origin + Rot(yaw) @ rs   (yaw = rotation of the RS frame in the world)."""
    origin_x: float = 0.0
    origin_y: float = 0.0
    yaw: float = 0.0

    def _rot(self):
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        return np.array([[c, -s], [s, c]])

    def rs_to_world_xy(self, xy):
        return np.array([self.origin_x, self.origin_y]) + self._rot() @ np.asarray(xy, float)

    def world_to_rs_xy(self, xy):
        return self._rot().T @ (np.asarray(xy, float) - np.array([self.origin_x, self.origin_y]))

    def rs_to_world_yaw(self, th):
        return wrap_angle(th + self.yaw)

    def world_to_rs_yaw(self, th):
        return wrap_angle(th - self.yaw)

    def world_translation(self, rs_xy):
        """Webots translation [x, y, z] of a robot at RS position `rs_xy`."""
        p = self.rs_to_world_xy(rs_xy)
        return [float(p[0]), float(p[1]), ROBOT_Z]


def measured_state(position, orientation, velocity, fm: FrameMap) -> np.ndarray:
    """Webots node readings -> RS state [x, y, theta, v, omega].

    position    getPosition()     [x, y, z]
    orientation getOrientation()  9 floats
    velocity    getVelocity()     [vx, vy, vz, wx, wy, wz] (world frame)
    v = forward speed (projection of the world velocity on the heading); omega = wz.
    """
    th_w = yaw_from_rotation_matrix(orientation)
    xy = fm.world_to_rs_xy(position[:2])
    v = velocity[0] * math.cos(th_w) + velocity[1] * math.sin(th_w)
    return np.array([xy[0], xy[1], fm.world_to_rs_yaw(th_w), v, velocity[5]], float)


def tilt_from_rotation_matrix(R):
    """(roll, pitch) in rad from Webots `getOrientation()` (row-major, z-up).

    roll: rotation about the robot x axis; pitch: rotation about y (positive = nose down in ENU).
    A robot standing level on its wheels and casters has both ~0.
    """
    pitch = math.asin(max(-1.0, min(1.0, -R[6])))
    roll = math.atan2(R[7], R[8])
    return roll, pitch
