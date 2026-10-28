"""Webots/stand-in run -> dashboard recording (valid, faithful, honestly labelled)."""
import json
import numpy as np
import pytest
from pathlib import Path
from resilientsync_webots.dashboard_export import recording_from_run_dir
from resilientsync_webots.testing import run_short
from simulation.recording import Replay, load_recording, loads_recording, validate_recording


def test_every_run_writes_a_valid_recording_with_matching_content():
    run, meta = run_short("blackout_gentle", duration=12.0)
    assert meta.get("recording") == "recording.json" and "recording_error" not in meta
    rec = load_recording(run["dir"] / "recording.json")                # passes the dashboard's own validation
    st = run["steps"]
    f = rec["frames"]
    assert len(f["t"]) == len(st) == 240
    states = np.asarray(f["states"])
    for i in range(5):                                                  # replayed states == logged ground-truth poses
        assert np.allclose(states[:, i, 0], st[f"gt_x_{i}"], atol=1e-3)
        assert np.allclose(states[:, i, 1], st[f"gt_y_{i}"], atol=1e-3)
    assert np.allclose(f["formation_rms"], st.formation_rms, atol=1e-3)
    assert np.array_equal(np.asarray(f["supervisor_state"])[:, 1:], st[[f"sup_state_{i}" for i in range(1, 5)]].to_numpy())
    assert rec["meta"]["source"] == "standin" and "NATIVE Python plant" in rec["meta"]["note"]
    assert rec["meta"]["fault_profile"]["name"] == "blackout_gentle"      # the REAL profile, not a stand-in label
    s = Replay(rec).summary()                                           # the dashboard's summary works on it
    assert isinstance(s, dict) and s


def test_offline_export_reproduces_the_logged_commands():
    run, _ = run_short("blackout_gentle", duration=10.0)
    rec, worst = recording_from_run_dir(run["dir"])
    assert worst < 1e-9                                                  # deterministic engine + logged poses -> same commands
    live = load_recording(run["dir"] / "recording.json")
    assert np.allclose(rec["frames"]["errors"], live["frames"]["errors"], atol=1e-9)


def test_offline_export_detects_a_tampered_log(tmp_path):
    import pandas as pd, shutil
    run, _ = run_short("blackout_gentle", duration=6.0)
    d = tmp_path / "r"; shutil.copytree(run["dir"], d)
    df = pd.read_csv(d / "steps.csv"); df.loc[40:, "gt_x_2"] += 0.5; df.to_csv(d / "steps.csv", index=False)
    _, worst = recording_from_run_dir(d)
    assert worst > 1e-3                                                  # poses no longer explain the logged commands


def test_recording_is_json_round_trippable_through_the_upload_path():
    run, _ = run_short("nominal", duration=4.0, n=3)
    text = (run["dir"] / "recording.json").read_text()
    assert loads_recording(text)["meta"]["n_agents"] == 3                # what POST /recordings/upload runs


def test_world_camera_follows_the_leader():
    for n in (3, 5):
        w = (Path(__file__).resolve().parents[1] / f"webots_project/worlds/resilientsync_{n}robots.wbt").read_text()
        assert 'follow "leader"' in w and 'followType "Mounted Shot"' in w and 'name "leader"' in w
