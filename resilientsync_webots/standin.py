"""Stand-in plant -- NOT Webots.

A differential-drive robot model used to exercise the adapter, logging and analysis pipeline
when Webots is unavailable.  It differs from the engine's own plant on purpose (so it is a
genuine second implementation of the plant, not the same RK4 code):
  * wheel-level model: wheel speed first-order lag (tau_wheel), saturation at MAX_WHEEL_RAD_S
  * forward-Euler integration at 10 ms sub-steps (engine: RK4 at 50 ms)
  * commands take effect one sub-step late (emulates the Emitter/Receiver hop)
  * poses live in a rotated/offset WORLD frame and are mapped back through `FrameMap`
It has no contact physics, no friction, no wheel slip, no mass -- so results from it say
NOTHING about Webots physics.  Every output from it is labelled plant="standin".
"""
from __future__ import annotations

import math

import numpy as np

from .frames import FrameMap, measured_state, rotation_from_yaw
from .robot_params import BASIC_TIME_STEP_MS, MAX_WHEEL_RAD_S, ROBOT_Z, TRACK, WHEEL_RADIUS


def _rot9(theta):
    c, s = math.cos(theta), math.sin(theta)
    return [c, -s, 0, s, c, 0, 0, 0, 1]


class StandInPlant:
    def __init__(self, n: int, frame: FrameMap = FrameMap(), wheel_tau: float = 0.05,
                 control_dt: float = 0.05, substep_ms: int = BASIC_TIME_STEP_MS):
        self.n, self.fm, self.tau = n, frame, wheel_tau
        self.h = substep_ms / 1000.0
        self.k = int(round(control_dt / self.h))
        self.t = 0.0
        self.x = np.zeros((n, 3))            # world x, y, yaw
        self.wheel = np.zeros((n, 2))        # actual wheel speeds
        self.cmd = np.zeros((n, 2))
        self._new = np.zeros((n, 2))

    def place(self, states_rs):
        for i, s in enumerate(states_rs):
            p = self.fm.rs_to_world_xy(s[:2])
            self.x[i] = (p[0], p[1], self.fm.rs_to_world_yaw(s[2]))

    def time(self):
        return self.t

    def measure(self):
        out = np.zeros((self.n, 5))
        for i in range(self.n):
            x, y, th = self.x[i]
            wl, wr = self.wheel[i]
            v = WHEEL_RADIUS * (wl + wr) / 2
            w = WHEEL_RADIUS * (wr - wl) / TRACK
            out[i] = measured_state([x, y, 0.0], _rot9(th),
                                    [v * math.cos(th), v * math.sin(th), 0, 0, 0, w], self.fm)
        return out

    def extras(self):
        d = {}
        for i in range(self.n):
            d.update({f"gt_z_{i}": ROBOT_Z, f"roll_{i}": 0.0, f"pitch_{i}": 0.0})   # planar model: no height/tilt
        return d

    def apply(self, wheels):
        self._new = np.array(wheels, float)

    def advance(self):
        for j in range(self.k):
            if j >= 1:
                self.cmd = self._new                    # one sub-step command latency
            c = np.clip(self.cmd, -MAX_WHEEL_RAD_S, MAX_WHEEL_RAD_S)
            self.wheel += (c - self.wheel) * (self.h / self.tau)
            v = WHEEL_RADIUS * (self.wheel[:, 0] + self.wheel[:, 1]) / 2
            w = WHEEL_RADIUS * (self.wheel[:, 1] - self.wheel[:, 0]) / TRACK
            self.x[:, 0] += v * np.cos(self.x[:, 2]) * self.h
            self.x[:, 1] += v * np.sin(self.x[:, 2]) * self.h
            self.x[:, 2] += w * self.h
            self.t += self.h
        self.cmd = self._new


class EngineKinematicsPlant:
    """Plant that uses the ENGINE's own RK4 unicycle + actuator-lag model (tau_motor).

    Diagnostic only: running the adapter on this plant isolates the effect of the
    adapter's measure-then-command ordering from the effect of a different plant.
    """

    def __init__(self, n: int, tau_motor: float = 0.12, control_dt: float = 0.05):
        self.n, self.tau, self.dt = n, tau_motor, control_dt
        self.S = np.zeros((n, 5))
        self.t = 0.0
        self._cmd = np.zeros((n, 2))

    def place(self, states_rs):
        self.S = np.array(states_rs, float)

    def time(self):
        return self.t

    def measure(self):
        return self.S.copy()

    def apply(self, wheels):
        from .diffdrive import wheels_to_cmd
        self._cmd = np.array([wheels_to_cmd(*w) for w in wheels])

    def advance(self):
        from simulation.kinematics import rk4_step
        for i in range(self.n):
            self.S[i] = rk4_step(self.S[i], self._cmd[i], self.dt, self.tau)
        self.t += self.dt
