"""Pre-flight check for a Webots run (Windows / Git Bash friendly).

    python scripts/check_webots_env.py [--write-runtime-ini] [--webots-exe PATH]

Reports: the Python Webots must use, importability of numpy/scipy and the project packages,
the Webots executable, and the resolved run configuration.  --write-runtime-ini writes
webots_project/controllers/rs_coordinator/runtime.ini pointing at THIS interpreter.
"""
import argparse, importlib, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ap = argparse.ArgumentParser()
ap.add_argument("--write-runtime-ini", action="store_true")
ap.add_argument("--webots-exe", default=None)
a = ap.parse_args()
bad = 0


def line(ok, msg):
    global bad
    bad += (ok is False)
    print(("[ OK ] " if ok else "[FAIL] " if ok is False else "[info] ") + msg)


line(None, f"python {sys.version.split()[0]} at {sys.executable}")
if sys.prefix == sys.base_prefix:
    line(None, "not inside a virtual environment (fine if the packages below import)")
for mod in ("numpy", "scipy"):
    try:
        m = importlib.import_module(mod); line(True, f"{mod} {m.__version__}")
    except Exception as e:
        line(False, f"{mod} not importable: {e}   ->  python -m pip install -r requirements.txt")
for mod in ("simulation", "experiments.run_benchmark", "resilientsync_webots.adapter", "resilientsync_webots.runconfig"):
    try:
        importlib.import_module(mod); line(True, f"import {mod}")
    except Exception as e:
        line(False, f"import {mod}: {type(e).__name__}: {e}")
for m in ("pandas", "matplotlib"):
    try:
        importlib.import_module(m); line(True, f"{m} (needed only for analysis/plots)")
    except Exception as e:
        line(None, f"{m} missing (analysis/plots unavailable): {e}")

cands = [a.webots_exe, os.environ.get("WEBOTS_EXE"),
         str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Webots/msys64/mingw64/bin/webots.exe"),
         r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe"]
exe = next((c for c in cands if c and Path(c).exists()), None)
line(bool(exe), f"Webots executable: {exe or 'NOT FOUND (pass --webots-exe)'}")

for f in ("webots_project/worlds/resilientsync_3robots.wbt", "webots_project/worlds/resilientsync_5robots.wbt",
          "webots_project/protos/RSDiffDrive.proto", "webots_project/controllers/rs_coordinator/rs_coordinator.py",
          "webots_project/controllers/rs_wheel_driver/rs_wheel_driver.py", "webots_project/config/run_config.json"):
    line((ROOT / f).exists(), f)
try:
    from experiments.run_benchmark import ARMS
    from resilientsync_webots.faults import load_scenarios
    from resilientsync_webots.runconfig import load_run_config
    cfg = load_run_config(ROOT / "webots_project/config/run_config.json", ROOT, load_scenarios(), ARMS, n_world=5)   # "auto" resolved against the 5-robot world
    line(True, f"run_config.json: scenario={cfg['scenario']} arm={cfg['arm']} seed={cfg['seed']} n_agents={cfg['n_agents']}")
    line(None, f"logs will be written under: {cfg['out_dir']}")
except Exception as e:
    line(False, f"run_config.json: {e}")

from resilientsync_webots.envcheck import install_hint, launch_test
ini = ROOT / "webots_project/controllers/rs_coordinator/runtime.ini"
py_for_webots = sys.executable
if ini.exists() and not a.write_runtime_ini:
    for l in ini.read_text().splitlines():
        if l.strip().lower().startswith("command"):
            py_for_webots = l.split("=", 1)[1].strip()
ok, out = launch_test(py_for_webots, ROOT)
line(ok, f"Webots-style launch test with {py_for_webots} (clean env, cwd = controller folder)")
for ol in out.splitlines()[-6:]:
    print("         " + ol)
if not ok:
    print("         " + install_hint(py_for_webots, out).replace("\n", "\n         "))
if a.write_runtime_ini:
    if ok:
        ini.write_text("[python]\nCOMMAND = " + sys.executable + "\n", encoding="utf-8")
        line(True, f"wrote {ini} -> {sys.executable}")
    else:
        line(False, "NOT writing runtime.ini: this interpreter cannot run the coordinator (see launch test above)")
else:
    line(None, f"runtime.ini {'exists: ' + ini.read_text().strip().replace(chr(10), ' ') if ini.exists() else 'absent (Webots then uses Tools > Preferences > Python command)'}")
print("\nResult:", "FAILED - fix the [FAIL] lines first" if bad else "ready")
sys.exit(1 if bad else 0)
