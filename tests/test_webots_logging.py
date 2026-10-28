"""CSV / JSON logging written by the run pipeline."""
import json
import numpy as np
import pytest
from resilientsync_webots.testing import run_short
from resilientsync_webots.runlog import CsvStream


def test_csvstream_header_from_first_row_and_blank_for_missing(tmp_path):
    s = CsvStream(tmp_path / "x.csv"); s.write({"a": 1, "b": 2}); s.write({"a": 3}); s.close()
    assert (tmp_path / "x.csv").read_text().split() == ["a,b", "1,2", "3,"]


def test_csvstream_rejects_unexpected_new_columns(tmp_path):
    s = CsvStream(tmp_path / "x.csv"); s.write({"a": 1})
    with pytest.raises(ValueError):
        s.write({"a": 1, "zzz": 2})


def test_run_directory_contents_and_consistency():
    run, meta = run_short("blackout_gentle", duration=8.0)
    d = run["dir"]
    for f in ("steps.csv", "comm_events.csv", "deliveries.csv", "faults.json", "transitions.json", "meta.json"):
        assert (d / f).exists(), f
    st = run["steps"]
    assert len(st) == meta["steps_run"] == 160
    assert np.allclose(np.diff(st.t), 0.05, atol=1e-9)
    assert meta["spec"]["plant"] == "standin" and meta["spec"]["seed"] == 100 and meta["status"] == "completed"
    need = {"t", "formation_rms", "min_sep", "fault_active", "blackout_active", "gt_x_0", "cmd_v_1", "wheel_l_1",
            "sat_1", "age_1", "quality_1", "sup_state_1", "rx_seq_1", "pose_seq_rx_1", "sent_1", "lost_1",
            "true_slot_err_1", "leader_est_err_1"}
    assert need <= set(st.columns)
    assert st.drop(columns=[c for c in st.columns if c.startswith("loss_est")]).notna().all().all()


def test_sequence_numbers_and_counts():
    run, _ = run_short("random_loss_30", duration=10.0)
    ev, dl, st = run["comm_events"], run["deliveries"], run["steps"]
    for f in range(1, 5):
        acc = dl[(dl.receiver == f) & dl.accepted].sort_values("t_delivered")
        assert (np.diff(acc.seq.to_numpy()) > 0).all()                         # accepted seq strictly increasing
        pose = ev[(ev.type == "POSE_UPDATE") & (ev.receiver == f)]
        delivered_ok = (pose.status != "LOST").sum()
        assert len(acc) <= delivered_ok <= len(pose)                           # delivered <= sent
        assert st[f"sent_{f}"].iloc[-1] >= len(pose) - 1                       # cumulative counter agrees
    assert (dl.age_at_delivery_s >= 0).all()


def test_transitions_log_is_json_and_ordered():
    run, _ = run_short("blackout_gentle", duration=14.0)
    tr = run["transitions"]
    assert len(tr) > 0 and all({"t", "from", "to", "follower"} <= set(x) for x in tr)
    assert [x["t"] for x in tr] == sorted(x["t"] for x in tr)
