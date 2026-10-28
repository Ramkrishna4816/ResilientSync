"""Recording format, replay integrity/seeking, malformed input, rerun comparison."""
import copy
import json

import numpy as np
import pytest

from simulation.recording import (FORMAT, Replay, RecordingError, RunSpec, build_recording,
                                  compare_rerun, load_recording, loads_recording, run_spec,
                                  save_recording, validate_recording)


@pytest.fixture(scope="module")
def rec():
    return run_spec(RunSpec(control_mode="adaptive_comm", seed=7, duration=10.0,
                            fault_profile="blackout", fault_start=3.0, fault_duration=2.0))


# ---- spec validation ----------------------------------------------------------
@pytest.mark.parametrize("bad", [
    {"control_mode": "magic"}, {"seed": -1}, {"seed": 1.5}, {"duration": 0.0}, {"duration": 1e9},
    {"n_agents": 1}, {"n_agents": 99}, {"fault_profile": "nope"}, {"fault_probability": 1.5},
    {"loss_scale": -1}, {"fault_duration": float("nan")}, {"formation": "BLOB"},
    {"supervisor_enabled": "yes"}, {"stride": 0}, {"unknown_field": 1}])
def test_runspec_rejects_invalid(bad):
    with pytest.raises(ValueError):
        RunSpec.from_dict(bad)


def test_runspec_roundtrip_and_formation_normalised():
    s = RunSpec.from_dict({"formation": "line", "seed": 3})
    assert s.formation == "LINE" and s.seed == 3


# ---- recording content ----------------------------------------------------------
def test_recording_has_required_content(rec):
    assert rec["format"] == FORMAT and rec["version"] == 1
    m, f, e = rec["meta"], rec["frames"], rec["events"]
    assert m["seed"] == 7 and m["control_mode"] == "adaptive_comm"
    assert m["fault_profile"]["events"][0]["kind"] == "blackout"
    n, k = m["n_agents"], len(f["t"])
    assert np.asarray(f["states"]).shape == (k, n, 5)          # positions + headings
    assert np.asarray(f["communication_quality"]).shape == (k, n)
    assert np.asarray(f["age"]).shape == (k, n - 1)
    assert e["fault_intervals"][0]["start"] == 3.0
    assert e["supervisor_transitions"] and "reason" in e["supervisor_transitions"][0]
    assert json.loads(json.dumps(rec)) == rec                  # plain JSON, no numpy leftovers


def test_non_adaptive_recording_has_no_supervisor_events():
    r = run_spec(RunSpec(control_mode="pidr", duration=4.0, fault_profile="none"))
    assert r["events"]["supervisor_transitions"] == []
    assert set(np.asarray(r["frames"]["supervisor_state"]).ravel()) == {0}


def test_stride_downsamples(rec):
    r2 = run_spec(RunSpec(seed=7, duration=10.0, fault_start=3.0, fault_duration=2.0, stride=5))
    assert len(r2["frames"]["t"]) == pytest.approx(len(rec["frames"]["t"]) / 5, abs=1)


# ---- replay integrity -------------------------------------------------------------
def test_replay_returns_saved_frames_exactly(rec):
    r = Replay(rec)
    for i in (0, 17, len(r) - 1):
        fr = r.frame(i)
        assert fr["states"] == rec["frames"]["states"][i]
        assert fr["formation_rms"] == rec["frames"]["formation_rms"][i]


def test_seek_nearest_and_clamping(rec):
    r = Replay(rec)
    t = np.asarray(rec["frames"]["t"])
    assert r.index_at(-5) == 0 and r.index_at(1e9) == len(t) - 1
    for k in (3, 50, 120):
        assert r.index_at(t[k] + 0.2 * (t[k + 1] - t[k])) == k
        assert r.index_at(t[k] + 0.8 * (t[k + 1] - t[k])) == k + 1
    assert r.seek(t[10])["index"] == 10
    with pytest.raises(ValueError):
        r.index_at(float("nan"))
    with pytest.raises(ValueError):
        r.index_at("3")


def test_step_forward_backward_and_bounds(rec):
    r = Replay(rec)
    r.seek(2.0)
    i = r.i
    assert r.step(1)["index"] == i + 1 and r.step(-1)["index"] == i
    assert r.step(-10**6)["index"] == 0 and r.step(10**6)["index"] == len(r) - 1
    with pytest.raises(IndexError):
        r.frame(len(r))


def test_frame_reports_active_fault_and_transition_context(rec):
    r = Replay(rec)
    assert r.seek(4.0)["active_faults"][0]["kind"] == "blackout"
    assert r.seek(1.0)["active_faults"] == []
    assert r.seek(9.0)["active_faults"] == []


def test_max_error_and_min_separation_match_arrays(rec):
    r = Replay(rec)
    e = np.asarray(rec["frames"]["formation_rms"])
    d = np.asarray(rec["frames"]["min_distance"])
    assert r.max_error()["formation_rms"] == e.max() and r.max_error()["t"] == rec["frames"]["t"][int(e.argmax())]
    ms = r.min_separation()
    assert ms["distance"] == d.min() and len(ms["pair"]) == 2 and ms["pair"][0] < ms["pair"][1]


def test_summary_is_built_from_recorded_events(rec):
    s = Replay(rec).summary()
    text = " ".join(s["text"])
    assert "seed 7" in text and "blackout" in text and "Peak formation RMS error" in text
    assert s["n_transitions"] >= 1 and set(s["time_in_state_s"]) == {"NORMAL", "DEGRADED", "HOLD", "RECOVERING"}
    assert s["connectivity_interruptions"]


# ---- malformed / incompatible recordings -----------------------------------------
def mutate(rec, fn):
    r = copy.deepcopy(rec)
    fn(r)
    return r


@pytest.mark.parametrize("fn,msg", [
    (lambda r: r.update(format="other"), "not a ResilientSync"),
    (lambda r: r.update(version=99), "unsupported recording version"),
    (lambda r: r.update(version="1"), "unsupported recording version"),
    (lambda r: r.pop("frames"), "missing section"),
    (lambda r: r["meta"].update(n_agents=1), "n_agents"),
    (lambda r: r["meta"].pop("dt"), "meta.dt"),
    (lambda r: r["frames"].pop("states"), "frames.states missing"),
    (lambda r: r["frames"]["t"].pop(), "shape"),
    (lambda r: r["frames"]["formation_rms"].__setitem__(3, float("nan")), "NaN"),
    (lambda r: r["frames"]["errors"].__setitem__(0, "x"), "non-numeric"),
    (lambda r: r["frames"]["t"].__setitem__(5, r["frames"]["t"][4]), "strictly increasing"),
    (lambda r: r["events"].update(fault_intervals="x"), "must be a list"),
    (lambda r: r.update(frames={"t": []}), "non-empty"),
])
def test_invalid_recordings_raise_recording_error(rec, fn, msg):
    with pytest.raises(RecordingError, match=msg):
        validate_recording(mutate(rec, fn))


def test_non_dict_and_bad_json_rejected():
    for bad in ([], "x", None, 3):
        with pytest.raises(RecordingError):
            validate_recording(bad)
    for text in ("{not json", "", "[1,2", "\x00"):
        with pytest.raises(RecordingError):
            loads_recording(text)


def test_save_load_roundtrip_and_missing_file(rec, tmp_path):
    p = save_recording(rec, tmp_path / "sub" / "a.json")
    assert load_recording(p) == rec
    with pytest.raises(RecordingError, match="no such recording"):
        load_recording(tmp_path / "missing.json")
    (tmp_path / "bin.json").write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(RecordingError):
        load_recording(tmp_path / "bin.json")


def test_save_refuses_nan(rec, tmp_path):
    bad = mutate(rec, lambda r: r["frames"]["lambda2"].__setitem__(0, float("inf")))
    with pytest.raises(RecordingError):
        save_recording(bad, tmp_path / "bad.json")


# ---- replay vs rerun -------------------------------------------------------------
def test_rerun_from_saved_spec_matches_this_build(rec):
    out = compare_rerun(rec)
    assert out["identical"] and out["max_abs_state_deviation"] == 0.0


def test_rerun_detects_a_changed_timeline(rec):
    changed = copy.deepcopy(rec)
    changed["meta"]["run_spec"]["seed"] = 8                    # different seed than the frames
    out = compare_rerun(changed)
    assert out["identical"] is False and out["max_abs_state_deviation"] > 1e-3


def test_same_seed_and_fault_is_reproducible_but_other_seed_differs():
    a = run_spec(RunSpec(seed=11, duration=6.0, fault_profile="random_loss", fault_start=2.0,
                         fault_duration=3.0))
    b = run_spec(RunSpec(seed=11, duration=6.0, fault_profile="random_loss", fault_start=2.0,
                         fault_duration=3.0))
    c = run_spec(RunSpec(seed=13, duration=6.0, fault_profile="random_loss", fault_start=2.0,
                         fault_duration=3.0))
    assert a["frames"] == b["frames"]
    assert a["frames"]["states"] != c["frames"]["states"]
