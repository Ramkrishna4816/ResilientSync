"""Check that a Python interpreter can run the Webots coordinator the way Webots launches it."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

_CODE = r"""
import sys
print('python', sys.version.split()[0], sys.executable)
import numpy, scipy
print('numpy', numpy.__version__, numpy.__file__)
print('scipy', scipy.__version__)
sys.path.insert(0, {root!r})
import simulation, experiments.run_benchmark, resilientsync_webots.adapter, resilientsync_webots.runconfig
print('project imports ok')
"""


def launch_test(python_exe, root, extra_args=(), timeout=90):
    """Run `python_exe` as Webots would: cwd = coordinator folder, venv/PYTHON* variables scrubbed.

    Returns (ok, combined_output).
    """
    root = Path(root)
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH")}
    cwd = root / "webots_project" / "controllers" / "rs_coordinator"
    try:
        r = subprocess.run([str(python_exe), *extra_args, "-c", _CODE.format(root=str(root))],
                           cwd=str(cwd if cwd.exists() else root), env=env, capture_output=True,
                           text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"{type(e).__name__}: {e}"
    return r.returncode == 0 and "project imports ok" in r.stdout, (r.stdout + r.stderr).strip()


def install_hint(python_exe, output: str) -> str:
    """Actionable fix for a failed launch test."""
    exe = str(python_exe)
    if "No module named" in output:
        mod = output.split("No module named", 1)[1].split()[0].strip("'\"")
        return (f"'{mod}' is not installed for {exe}.\n"
                f"  Fix (Git Bash):  \"{exe}\" -m pip install -r requirements-webots.txt\n"
                f"  If that fails, send me the pip output (the full requirements.txt also installs the web-dashboard "
                f"stack, and one failing package aborts the whole install).")
    return f"launch test failed for {exe}; see the output above."
