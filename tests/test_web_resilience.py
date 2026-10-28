"""Dashboard API tests for resilience observability."""
import pytest
from fastapi.testclient import TestClient

from web.app import create_app


@pytest.fixture()
def client():
    with TestClient(create_app()) as c:
        yield c


def test_resilience_endpoint_reports_real_supervisor_state(client):
    r = client.post("/sim/reset", json={"control_mode": "adaptive_comm", "seed": 5,
                                        "fault_profile": "blackout", "fault_start": 0.2,
                                        "fault_duration": 1.0}).json()
    assert r["ok"] is True
    import time; time.sleep(0.6)
    d = client.get("/resilience").json()
    assert d["supervisor_active"] is True
    assert d["faults"]["profile"] == "blackout"
    assert d["trace"]["fields"][0] == "t" and len(d["trace"]["rows"]) > 0
    assert set(d["followers"]["1"]).issuperset({"state", "reason", "quality", "age", "transitions"})
    st = client.get("/state").json()
    assert "resilience" in st and st["resilience"]["supervisor_enabled"] is True


def test_supervisor_inactive_for_other_modes_but_faults_still_reported(client):
    client.post("/sim/reset", json={"control_mode": "pidr", "seed": 1})
    d = client.get("/resilience").json()
    assert d["supervisor_active"] is False and "followers" not in d
    assert d["faults"]["profile"] == "none"


def test_fault_endpoint_schedules_and_clears_and_validates(client):
    ok = client.post("/faults", json={"profile": "random_loss", "start_in": 1, "duration": 2,
                                      "probability": 0.5}).json()
    assert ok["ok"] is True and ok["profile"]["events"][0]["kind"] == "random_loss"
    assert client.get("/resilience").json()["faults"]["profile"] == "random_loss"
    bad = client.post("/faults", json={"profile": "nope"}).json()
    assert bad["ok"] is False
    assert client.post("/faults", json={"profile": "blackout", "duration": -1}).status_code == 422
    assert client.post("/faults/clear").json()["ok"] is True
    assert client.get("/resilience").json()["faults"]["profile"] == "none"


def test_reset_rejects_unknown_fault_profile(client):
    r = client.post("/sim/reset", json={"fault_profile": "bogus"}).json()
    assert r["ok"] is False


def test_benchmark_endpoint_serves_measured_data_or_clear_404(client):
    r = client.get("/benchmark?tag=definitely_missing")
    assert r.status_code == 404 and r.json()["ok"] is False
    assert client.get("/benchmark?tag=../x").status_code == 400
    r = client.get("/benchmark")          # eval results are shipped with the project
    if r.status_code == 200:
        assert r.json()["rows"] and "RMSE_mean" in r.json()["rows"][0]


def test_supervisor_can_be_disabled_on_reset(client):
    client.post("/sim/reset", json={"control_mode": "adaptive_comm", "supervisor_enabled": False})
    assert client.get("/resilience").json()["supervisor_active"] is False
