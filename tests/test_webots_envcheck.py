"""Environment pre-flight: must detect the 'numpy missing in the interpreter Webots uses' failure."""
import sys
from pathlib import Path
from resilientsync_webots.bootstrap_hint import explain_import_failure
from resilientsync_webots.envcheck import install_hint, launch_test

ROOT = Path(__file__).resolve().parents[1]


def test_launch_test_passes_for_a_working_interpreter():
    ok, out = launch_test(sys.executable, ROOT)
    assert ok, out
    assert "project imports ok" in out and "numpy" in out


def test_launch_test_detects_missing_numpy_like_the_reported_failure():
    # -S hides site-packages, reproducing a venv without numpy
    ok, out = launch_test(sys.executable, ROOT, extra_args=["-S"])
    assert not ok and "No module named 'numpy'" in out
    hint = install_hint(sys.executable, out)
    assert "requirements-webots.txt" in hint and "'numpy'" in hint


def test_launch_test_reports_a_nonexistent_interpreter():
    ok, out = launch_test(ROOT / "no_such_python.exe", ROOT)
    assert not ok and out


def test_startup_message_names_interpreter_module_and_fix():
    exc = ModuleNotFoundError("No module named 'numpy'", name="numpy")
    msg = explain_import_failure(exc, "/proj")
    assert sys.executable in msg and "numpy" in msg and "requirements-webots.txt" in msg and "check_webots_env.py" in msg


def test_webots_requirements_exclude_dashboard_stack_but_include_numpy_scipy():
    txt = (ROOT / "requirements-webots.txt").read_text().lower()
    body = "\n".join(l for l in txt.splitlines() if not l.lstrip().startswith("#"))
    assert "numpy" in body and "scipy" in body
    for pkg in ("fastapi", "uvicorn", "jinja2", "httpx"):
        assert pkg not in body


def test_coordinator_imports_are_guarded_and_use_the_resolver():
    src = (ROOT / "webots_project/controllers/rs_coordinator/rs_coordinator.py").read_text()
    assert "explain_import_failure" in src and "load_run_config(cfg_path, ROOT, scenarios, ARMS, n_world=n_world)" in src
    assert src.index("try:") < src.index("import numpy as np")        # numpy import is inside the guard
