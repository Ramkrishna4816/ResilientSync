"""Static checks of the Webots project files (these do NOT prove the world loads in Webots)."""
import importlib.util
import py_compile
import re
from pathlib import Path
import numpy as np
import pytest
from resilientsync_webots import robot_params as rp

ROOT = Path(__file__).resolve().parents[1]
WP = ROOT / "webots_project"
PROTO_RAW = (WP / "protos" / "RSDiffDrive.proto").read_text()
PROTO = "\n".join(l for l in PROTO_RAW.splitlines() if not l.lstrip().startswith("#") or l.startswith("#VRML"))   # comments removed


def _balanced(text):
    stack = []
    for ch in re.sub(r'"[^"]*"', '""', re.sub(r"#.*", "", text)):
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if not stack or {"}": "{", "]": "["}[ch] != stack.pop():
                return False
    return not stack


def test_proto_constants_match_python_parameters():
    radii = {float(x) for x in re.findall(r"radius\s+([0-9.]+)", PROTO)}
    assert rp.WHEEL_RADIUS in radii
    anchors = [float(x) for x in re.findall(r"anchor\s+0\s+(-?[0-9.]+)\s+0", PROTO)]
    assert sorted(anchors) == [-rp.TRACK / 2, rp.TRACK / 2]
    assert {float(x) for x in re.findall(r"maxVelocity\s+([0-9.]+)", PROTO)} == {rp.MAX_WHEEL_RAD_S}
    assert f"0 0 {rp.ROBOT_Z}" in PROTO                          # default translation height
    assert "centerOfMass" in PROTO                               # so getVelocity() is the origin velocity


def test_proto_devices_used_by_controllers_exist():
    for dev in ("left wheel motor", "right wheel motor", "cmd_rx"):
        assert f'"{dev}"' in PROTO
    drv = (WP / "controllers/rs_wheel_driver/rs_wheel_driver.py").read_text()
    for dev in ("left wheel motor", "right wheel motor", "cmd_rx"):
        assert f'"{dev}"' in drv
    assert f"MAX_WHEEL = {rp.MAX_WHEEL_RAD_S}" in drv


@pytest.mark.parametrize("n", [3, 5])
def test_world_files_structure(n):
    w = (WP / "worlds" / f"resilientsync_{n}robots.wbt").read_text()
    assert w.startswith("#VRML_SIM R2023b utf8") and _balanced(w)
    assert 'coordinateSystem "ENU"' in w                         # frame assumed by frames.py
    assert f"basicTimeStep {rp.BASIC_TIME_STEP_MS}" in w
    assert rp.CONTROL_PERIOD_MS % rp.BASIC_TIME_STEP_MS == 0
    assert abs(rp.CONTROL_PERIOD_MS / 1000 - rp.CONTROL_DT_S) < 1e-12
    assert [int(x) for x in re.findall(r"DEF RS_(\d+) ", w)] == list(range(n))
    assert len(re.findall(r"DEF SLOT_", w)) == n - 1
    assert 'EXTERNPROTO "../protos/RSDiffDrive.proto"' in w
    assert "supervisor TRUE" in w and 'controller "rs_coordinator"' in w
    assert 'Emitter { name "cmd_tx" channel 1 }' in w and "Receiver {\n        name \"cmd_rx\"\n        channel 1" in PROTO
    assert all(f'controllerArgs [ "{i}" "{n}" ]' in w for i in range(n))


def test_casters_are_part_of_the_top_level_bounding_object():
    # Webots ignores the boundingObject of a child Solid that has no physics ("collisions will have no effect").
    # Only the two wheel Solids (each with physics) may be Solids; casters live in the robot's boundingObject Group.
    assert len(re.findall(r"\bSolid\s*\{", PROTO)) == 2
    assert len(re.findall(r"physics\s+Physics", PROTO)) == 3                 # 2 wheels + robot body
    assert "front caster" not in PROTO and "rear caster" not in PROTO
    robot_bo = PROTO[PROTO.index("    boundingObject Group"):]
    assert robot_bo.count("Sphere {") == 2 and "radius 0.0285" in robot_bo
    assert PROTO.count('contactMaterial "rs_caster"') == 1
    # caster sphere lowest point must touch the floor: centre z + (-radius) == -wheel radius (relative to axle)
    z = float(re.search(r"translation 0\.15 0 (-[0-9.]+)", robot_bo).group(1))
    assert z - 0.0285 == pytest.approx(-rp.WHEEL_RADIUS, abs=1e-6)


def test_proto_is_balanced():
    assert _balanced(PROTO)


def test_control_period_equals_engine_dt():
    from simulation.config import DT
    assert rp.CONTROL_DT_S == DT


def test_worlds_are_exactly_what_the_generator_produces():
    spec = importlib.util.spec_from_file_location("make_worlds", WP / "make_worlds.py")
    mw = importlib.util.module_from_spec(spec); spec.loader.exec_module(mw)
    for n in (3, 5):
        assert (WP / "worlds" / f"resilientsync_{n}robots.wbt").read_text() == mw.world_text(n)


def test_viewpoint_looks_at_arena_centre():
    spec = importlib.util.spec_from_file_location("make_worlds", WP / "make_worlds.py")
    mw = importlib.util.module_from_spec(spec); spec.loader.exec_module(mw)
    eye, tgt = np.array([9.0, -13.4, 15.2]), np.array([9.0, 1.0, 0.0])
    ax_x, ax_y, ax_z, ang = mw.viewpoint(9.0, 1.0, tuple(eye))
    k = np.array([ax_x, ax_y, ax_z]); x = np.array([1.0, 0, 0])
    fwd = x * np.cos(ang) + np.cross(k, x) * np.sin(ang) + k * (k @ x) * (1 - np.cos(ang))
    want = (tgt - eye) / np.linalg.norm(tgt - eye)
    assert np.allclose(fwd, want, atol=0.05)


def test_controllers_compile_and_runtime_example_exists():
    for f in ("rs_coordinator/rs_coordinator.py", "rs_wheel_driver/rs_wheel_driver.py"):
        py_compile.compile(str(WP / "controllers" / f), doraise=True, cfile="/tmp/_x.pyc")
    assert (WP / "controllers/rs_coordinator/runtime.ini.example").exists()
