"""Make a run viewable on the website (Replay tab).

    python scripts/export_recording.py results/webots/<run_dir>        # one run
    python scripts/export_recording.py --latest                         # newest Webots run
Writes <run>/recording.json and copies it to recordings/<plant>__<run_id>.json, where the dashboard lists it.
Also re-drives a fresh engine with the logged measured poses and reports how closely it reproduces the logged
commands (integrity check of the log).
"""
import argparse, json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from resilientsync_webots.dashboard_export import recording_from_run_dir
from simulation.recording import save_recording

ap = argparse.ArgumentParser()
ap.add_argument("dirs", nargs="*"); ap.add_argument("--latest", action="store_true")
ap.add_argument("--recordings-dir", default=str(ROOT / "recordings"))
a = ap.parse_args()
dirs = [Path(x) for x in a.dirs]
if a.latest or not dirs:
    c = sorted((p for p in (ROOT / "results" / "webots").glob("*") if (p / "meta.json").exists()), key=lambda p: p.stat().st_mtime)
    if not c: sys.exit("no Webots run directories with meta.json under results/webots")
    dirs = dirs or [c[-1]]
for d in dirs:
    rec, worst = recording_from_run_dir(d)
    plant = json.loads((d / "meta.json").read_text())["spec"]["plant"]
    save_recording(rec, d / "recording.json")
    Path(a.recordings_dir).mkdir(exist_ok=True)
    dest = Path(a.recordings_dir) / f"{plant}__{d.name}.json"
    shutil.copyfile(d / "recording.json", dest)
    print(f"{d.name}: {len(rec['frames']['t'])} frames -> {dest}")
    print(f"   engine re-driven with the logged poses reproduces the logged commands to {worst:.2e} (expect ~1e-9 or less)")
