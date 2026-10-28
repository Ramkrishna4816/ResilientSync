"""Benchmark runner: new metrics, scenarios, reproducibility, overwrite protection."""
import csv
import json

import pytest

from experiments import run_benchmark as rb


def test_run_one_reports_connectivity_consensus_and_saturation():
    r = rb.run_one("adaptive_supervisor", "blackout_3s", 42)
    assert r["run_status"] == "ok"
    for k in ("conn_interruption_s", "isolated_s_max", "lambda2_min", "heading_rms_mean",
              "consensus_frac", "sat_frac", "conn_status", "consensus_status"):
        assert k in r
    # blackout 5-8 s: leader links die after the 1 s timeout and come back with the first packet
    assert r["conn_status"] == "restored" and 1.5 <= r["conn_interruption_s"] <= 2.5
    assert r["lambda2_min"] == 0.0
    assert 0.0 <= r["consensus_frac"] <= 1.0 and 0.0 <= r["sat_frac"] <= 1.0


def test_nominal_run_has_no_connectivity_interruption():
    r = rb.run_one("pidr", "nominal", 43)
    assert r["conn_interruption_s"] == 0.0 and r["conn_status"] == "not_interrupted"
    assert r["recovery_status"] == "not_applicable"


def test_same_seed_same_result_different_seed_differs():
    a, b = rb.run_one("advanced", "random_loss_30", 5), rb.run_one("advanced", "random_loss_30", 5)
    c = rb.run_one("advanced", "random_loss_30", 9)
    keys = ("RMSE", "Peak", "MinSep", "heading_rms_mean", "sat_frac")
    assert all(a[k] == b[k] for k in keys)
    assert any(a[k] != c[k] for k in keys)


def test_gentle_scenarios_are_a_feasible_tracking_control():
    assert {"nominal_gentle", "blackout_gentle"} <= set(rb.SCENARIOS)
    gentle = rb.run_one("pidr", "nominal_gentle", 42)
    default = rb.run_one("pidr", "nominal", 42)
    assert gentle["RMSE"] < 0.2 < 1.0 < default["RMSE"]      # slots reachable vs. not reachable
    assert gentle["recovery_status"] == "not_applicable"


def test_blackout_gentle_can_measure_recovery():
    r = rb.run_one("pidr", "blackout_gentle", 42)
    assert r["recovery_status"] in ("recovered", "not_recovered")    # window is applicable here


def test_benchmark_writes_files_and_refuses_to_overwrite(tmp_path):
    kw = dict(arms=["pidr", "adaptive_supervisor"], scenarios=["nominal", "blackout_3s"], seeds=[42, 43],
              duration=8.0, tag="t", out_root=tmp_path, plots=False, progress=False)
    res = rb.run_benchmark(**kw)
    d = tmp_path / "t"
    assert {p.name for p in d.iterdir()} >= {"per_run.csv", "aggregate.csv", "summary.json", "report.md"}
    rows = list(csv.DictReader((d / "per_run.csv").open(encoding="utf-8")))
    assert len(rows) == 2 * 2 * 2 and {r["seed"] for r in rows} == {"42", "43"}
    assert all(r["run_status"] == "ok" for r in rows)
    summ = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    assert summ["meta"]["seeds"] == [42, 43] and "consensus_reached_runs" in summ["aggregate"][0]
    assert "Connectivity, consensus and saturation" in (d / "report.md").read_text(encoding="utf-8")
    before = (d / "per_run.csv").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        rb.run_benchmark(**kw)                                  # historical results are protected
    assert (d / "per_run.csv").read_text(encoding="utf-8") == before
    rb.run_benchmark(**kw, overwrite=True)                      # explicit opt-in works


def test_first_round_results_are_untouched_and_present():
    p = rb.OUT_ROOT / "eval" / "per_run.csv"
    assert p.is_file()
    assert "conn_interruption_s" not in p.read_text(encoding="utf-8").splitlines()[0]   # old schema preserved
