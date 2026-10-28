"""rs_wheel_driver -- per-robot Webots controller: applies wheel speeds sent by rs_coordinator.

It contains NO control law.  It only (1) receives the packed wheel-speed vector on the
actuation channel, (2) clips to the motor limit, (3) sets the two RotationalMotors.
The actuation channel (Emitter/Receiver channel 1) is simulation infrastructure, NOT the
radio link under test: ResilientSync faults are injected inside the engine's Network, on the
leader->follower pose messages, never on this channel.
controllerArgs: <robot index> <robot count>
"""
import struct
import sys

from controller import Robot

MAX_WHEEL = 20.0            # rad/s, must equal RotationalMotor.maxVelocity in RSDiffDrive.proto
WATCHDOG_S = 0.5            # stop if the coordinator stops sending (e.g. it crashed)

idx, n = int(sys.argv[1]), int(sys.argv[2])
robot = Robot()
ts = int(robot.getBasicTimeStep())
left, right = robot.getDevice("left wheel motor"), robot.getDevice("right wheel motor")
for m in (left, right):
    m.setPosition(float("inf"))
    m.setVelocity(0.0)
rx = robot.getDevice("cmd_rx")
rx.enable(ts)
fmt = f"<d{2 * n}d"
size = struct.calcsize(fmt)
last_rx_t = robot.getTime()
while robot.step(ts) != -1:
    pkt = None
    while rx.getQueueLength() > 0:
        data = rx.getBytes() if hasattr(rx, "getBytes") else rx.getData()
        if len(data) == size:
            pkt = struct.unpack(fmt, data)
        rx.nextPacket()
    now = robot.getTime()
    if pkt is not None:
        last_rx_t = now
        wl, wr = pkt[1 + 2 * idx], pkt[2 + 2 * idx]
        if wl != wl or wr != wr:                      # NaN guard
            wl = wr = 0.0
        left.setVelocity(max(-MAX_WHEEL, min(MAX_WHEEL, wl)))
        right.setVelocity(max(-MAX_WHEEL, min(MAX_WHEEL, wr)))
    elif now - last_rx_t > WATCHDOG_S:
        left.setVelocity(0.0)
        right.setVelocity(0.0)
