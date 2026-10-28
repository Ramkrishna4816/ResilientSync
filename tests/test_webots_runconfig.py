"""Run-config resolution: relative out_dir must be anchored at the project root (not the cwd)."""
import json
import os
import pytest
from pathlib import Path
from resilientsync_webots.runconfig import load_run_config


def _cfg(tmp_path, **kw):
    d = {"scenario": "blackout_gentle", "arm": "pidr", "seed": 5}; d.update(kw)
    p = tmp_path / "c.json"; p.write_text(json.dumps(d)); return p


def test_relative_out_dir_is_resolved_against_project_root_not_cwd(tmp_path):
    old = os.getcwd(); os.chdir(tmp_path)
    try:
        c = load_run_config(_cfg(tmp_path, out_dir="results/webots"), Path("/proj"))
    finally:
        os.chdir(old)
    assert Path(c["out_dir"]) == Path("/proj/results/webots")


def test_absolute_out_dir_is_kept(tmp_path):
    target = str(tmp_path / "x")
    assert load_run_config(_cfg(tmp_path, out_dir=target), Path("/proj"))["out_dir"] == target


def test_defaults_and_validation(tmp_path):
    c = load_run_config(_cfg(tmp_path), Path("/proj"))
    assert c["duration_s"] == 18.0 and c["n_agents"] == 5 and c["quit_when_done"] is True
    with pytest.raises(ValueError):
        load_run_config(_cfg(tmp_path, scenario="nope"), Path("/proj"), known_scenarios={"blackout_gentle"})
    with pytest.raises(ValueError):
        load_run_config(_cfg(tmp_path, arm="nope"), Path("/proj"), known_arms={"pidr"})
    with pytest.raises(ValueError):
        load_run_config(_cfg(tmp_path, n_agents=4), Path("/proj"))
    p = tmp_path / "bad.json"; p.write_text(json.dumps({"scenario": "x"}))
    with pytest.raises(ValueError):
        load_run_config(p, Path("/proj"))


def test_shipped_run_config_is_valid():
    from experiments.run_benchmark import ARMS
    from resilientsync_webots.faults import load_scenarios
    root = Path(__file__).resolve().parents[1]
    c = load_run_config(root / "webots_project/config/run_config.json", root, load_scenarios(), ARMS, n_world=5)
    assert Path(c["out_dir"]) == root / "results" / "webots"


def test_auto_robot_count_follows_the_loaded_world(tmp_path):
    p = _cfg(tmp_path, n_agents="auto")
    assert load_run_config(p, Path("/proj"), n_world=3)["n_agents"] == 3
    assert load_run_config(p, Path("/proj"), n_world=5)["n_agents"] == 5
    with pytest.raises(ValueError):
        load_run_config(p, Path("/proj"))                       # auto without a world is an error


def test_explicit_robot_count_mismatching_the_world_gives_a_clear_error(tmp_path):
    # the user opened the 3-robot world while the config said 5
    with pytest.raises(ValueError, match="loaded world has 3 robots"):
        load_run_config(_cfg(tmp_path, n_agents=5), Path("/proj"), n_world=3)


def test_shipped_config_is_auto():
    root = Path(__file__).resolve().parents[1]
    assert json.loads((root / "webots_project/config/run_config.json").read_text())["n_agents"] == "auto"
