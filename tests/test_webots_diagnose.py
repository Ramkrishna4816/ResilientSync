"""The motion/pipeline diagnostic must pass a healthy run and FAIL on each injected defect."""
import json
import shutil
import numpy as np
import pandas as pd
from pathlib import Path
from resilientsync_webots.diagnose import diagnose
from resilientsync_webots.testing import run_short


def _levels(res):
    return {c["id"]: c["level"] for c in res["checks"]}


def _copy(run, tmp):
    dst = Path(tmp) / "r"; shutil.copytree(run["dir"], dst); return dst


def _healthy():
    run, _ = run_short("blackout_gentle", duration=12.0)
    return run


def test_healthy_standin_run_has_no_failures_and_is_labelled_standin():
    r = diagnose(_healthy()["dir"])
    assert r["verdict"] in ("OK", "WARN")
    lv = _levels(r)
    assert lv["not_webots"] == "WARN"                                  # never mistaken for Webots evidence
    assert lv["blackout_effective"] == "PASS" and lv["leader_vs_reference"] == "PASS"
    assert not [c for c in r["checks"] if c["level"] == "FAIL"]


def test_frozen_robot_is_detected(tmp_path):
    d = _copy(_healthy(), tmp_path); df = pd.read_csv(d / "steps.csv")
    for c in ("gt_x_3", "gt_y_3"):
        df[c] = df[c].iloc[0]; 
    df["gt_v_3"] = 0.0
    df.to_csv(d / "steps.csv", index=False)
    lv = _levels(diagnose(d, with_native_reference=False))
    assert lv["moved_3"] == "FAIL" and lv["frozen_3"] == "FAIL"


def test_teleport_is_detected(tmp_path):
    d = _copy(_healthy(), tmp_path); df = pd.read_csv(d / "steps.csv")
    df.loc[100:, "gt_x_2"] += 3.0
    df.to_csv(d / "steps.csv", index=False)
    assert _levels(diagnose(d, with_native_reference=False))["teleport"] == "FAIL"


def test_tipping_and_sinking_are_detected(tmp_path):
    d = _copy(_healthy(), tmp_path); df = pd.read_csv(d / "steps.csv")
    df["pitch_1"] = np.radians(20.0); df["gt_z_1"] = 0.05
    df.to_csv(d / "steps.csv", index=False)
    lv = _levels(diagnose(d, with_native_reference=False))
    assert lv["tilt"] == "FAIL" and lv["height"] == "FAIL"


def test_nan_command_is_detected(tmp_path):
    d = _copy(_healthy(), tmp_path); df = pd.read_csv(d / "steps.csv")
    df.loc[50, "cmd_v_1"] = np.nan
    df.to_csv(d / "steps.csv", index=False)
    assert _levels(diagnose(d, with_native_reference=False))["finite"] == "FAIL"


def test_leader_that_does_not_follow_the_reference_is_detected(tmp_path):
    d = _copy(_healthy(), tmp_path); df = pd.read_csv(d / "steps.csv")
    df["gt_y_0"] += np.linspace(0, 4, len(df))
    df.to_csv(d / "steps.csv", index=False)
    assert _levels(diagnose(d))["leader_vs_reference"] == "FAIL"


def test_coordinator_error_file_and_missing_files_fail(tmp_path):
    d = _copy(_healthy(), tmp_path)
    (d / "coordinator_error.txt").write_text("Traceback: boom")
    (d / "deliveries.csv").unlink()
    r = diagnose(d, with_native_reference=False)
    lv = _levels(r)
    assert r["verdict"] == "FAIL" and lv["coordinator_error"] == "FAIL" and lv["files"] == "FAIL"


def test_empty_directory_does_not_crash(tmp_path):
    assert diagnose(tmp_path)["verdict"] == "FAIL"
