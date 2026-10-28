"""Physical constants of the Webots robot (RSDiffDrive.proto) and timing.

These numbers MUST match `webots_project/protos/RSDiffDrive.proto` and the world files;
`tests/test_webots_assets.py` parses the PROTO and checks them.
"""
WHEEL_RADIUS = 0.0975        # [m]
TRACK = 0.33                 # [m] distance between wheel centres
MAX_WHEEL_RAD_S = 20.0       # [rad/s] RotationalMotor.maxVelocity (= 1.95 m/s linear)
ROBOT_Z = WHEEL_RADIUS       # [m] height of the robot reference point (axle) above the floor
CONTROL_DT_S = 0.05          # must equal simulation.config.DT (engine tick)
BASIC_TIME_STEP_MS = 10      # WorldInfo.basicTimeStep; control period = 5 x this
CONTROL_PERIOD_MS = 50
