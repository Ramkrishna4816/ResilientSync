"""API: connectivity, experiment runs, recordings and replay, validation."""
import json

import pytest
from fastapi.testclient import TestClient

from web.app import create_app

RUN = {"control_mode": "adaptive_comm", "seed": 5, "duration": 8.0, "fault_profile": "blackout",
       "fault_start": 2.0, "fault_duration": 2.0}


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(recordings_dir=tmp_path)) as c:
        yield c


def test_connectivity_endpoint_is_real_and_labelled_global(client):
    d = client.get("/connectivity").json()
    assert d["scope"].startswith("global diagnostic")
    client.post("/sim/reset", json={"control_mode": "adaptive_comm", "seed": 3})
    import time; time.sleep(0.5)
    d = client.get("/connectivity").json()
    assert {"components", "algebraic_connectivity", "heading_rms", "tracker", "closest_approach",
            "isolated_from_leader", "unreached_by_leader"} <= set(d)
    assert "connectivity" in client.get("/state").json()


def test_run_save_list_load_summary_frame(client):
    r = client.post("/experiments/run", json=RUN).json()
    assert r["ok"] and r["summary"]["max_error"]["formation_rms"] > 0
    rid = r["id"]
    lst = client.get("/recordings").json()["recordings"]
    assert [x["id"] for x in lst] == [rid] and lst[0]["fault_profile"] == "blackout"
    rec = client.get(f"/recordings/{rid}").json()
    assert rec["meta"]["seed"] == 5 and rec["frames"]["t"][0] == 0.0
    fr = client.get(f"/recordings/{rid}/frame", params={"t": 3.0}).json()
    assert abs(fr["t"] - 3.0) < 0.06 and fr["active_faults"][0]["kind"] == "blackout"
    sm = client.get(f"/recordings/{rid}/summary").json()
    assert sm["min_separation"]["distance"] > 0
    rr = client.post(f"/recordings/{rid}/rerun").json()
    assert rr["ok"] and rr["identical"]


@pytest.mark.parametrize("patch", [
    {"seed": -1}, {"duration": 0}, {"duration": 1000}, {"n_agents": 1}, {"fault_probability": 2},
    {"control_mode": "magic"}, {"fault_profile": "nope"}, {"stride": 0}, {"jitter_s": -1}])
def test_run_and_config_validation(client, patch):
    for path in ("/experiments/run", "/experiments/config"):
        r = client.post(path, json={**RUN, **patch})
        assert r.status_code == 422, (path, patch, r.text)


def test_config_endpoint_returns_normalised_spec(client):
    r = client.post("/experiments/config", json={**RUN, "formation": "line"}).json()
    assert r["ok"] and r["spec"]["formation"] == "LINE" and r["spec"]["seed"] == 5


def test_unknown_and_malicious_ids(client):
    assert client.get("/recordings/nope").status_code == 404
    assert client.get("/recordings/..%2F..%2Fetc%2Fpasswd").status_code in (400, 404)
    assert client.get("/recordings/bad id").status_code in (400, 404)
    assert client.get("/recordings/a.b").status_code == 400
    assert client.get("/recordings/nope/frame", params={"t": 1}).status_code == 404


def test_upload_valid_and_malformed(client):
    rid = client.post("/experiments/run", json=RUN).json()["id"]
    text = json.dumps(client.get(f"/recordings/{rid}").json())
    ok = client.post("/recordings/upload", json={"text": text, "name": "my run!"})
    assert ok.status_code == 200 and ok.json()["id"].startswith("my_run_")
    for bad in ("{nope", json.dumps({"format": "x"}), "[]"):
        r = client.post("/recordings/upload", json={"text": bad})
        assert r.status_code == 422 and r.json()["ok"] is False


def test_corrupt_file_on_disk_is_ignored_in_listing_and_reported_on_load(client, tmp_path):
    (tmp_path / "broken.json").write_text("{oops", encoding="utf-8")
    assert client.get("/recordings").json()["recordings"] == []
    r = client.get("/recordings/broken")
    assert r.status_code == 422 and r.json()["ok"] is False


def test_concurrent_run_is_rejected_with_409_and_leaves_no_file(tmp_path):
    app = create_app(recordings_dir=tmp_path)
    with TestClient(app) as c:
        assert app.state.run_lock.acquire(blocking=False)         # a run is "in progress"
        try:
            r = c.post("/experiments/run", json=RUN)
            assert r.status_code == 409 and r.json()["ok"] is False
            assert list(tmp_path.glob("*.json")) == []
        finally:
            app.state.run_lock.release()
        assert c.post("/experiments/run", json=RUN).json()["ok"]  # works again afterwards


def test_reset_accepts_latency_and_jitter_and_rejects_bad_values(client):
    ok = client.post("/sim/reset", json={"control_mode": "adaptive_comm", "fault_profile": "latency_jitter",
                                         "extra_latency_s": 0.4, "jitter_s": 0.1}).json()
    assert ok["ok"]
    assert client.post("/sim/reset", json={"jitter_s": 99}).status_code == 422
