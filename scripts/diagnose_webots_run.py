"""Print the motion/pipeline diagnosis of run directories.

    python scripts/diagnose_webots_run.py results/webots/<run_dir> [more dirs] [--no-reference]
    python scripts/diagnose_webots_run.py --latest        # newest run under results/webots
"""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from resilientsync_webots.diagnose import diagnose

ap = argparse.ArgumentParser()
ap.add_argument("dirs", nargs="*"); ap.add_argument("--latest", action="store_true"); ap.add_argument("--no-reference", action="store_true")
a = ap.parse_args()
dirs = [Path(x) for x in a.dirs]
if a.latest or not dirs:
    cands = sorted((p for p in (ROOT / "results" / "webots").glob("*") if p.is_dir() and not p.name.startswith("_")), key=lambda p: p.stat().st_mtime)
    if not cands:
        sys.exit("No run directories under results/webots. Search for them with:\n  find . -name meta.json -path '*webots*' 2>/dev/null\n  find . -name coordinator_error.txt")
    dirs = dirs or [cands[-1]]
worst = 0
for d in dirs:
    r = diagnose(d, with_native_reference=not a.no_reference)
    print(f"\n=== {d}  ->  {r['verdict']}")
    for c in r["checks"]:
        print(f"  [{c['level']:4s}] {c['id']}: {c['msg']}")
    worst = max(worst, {"OK": 0, "WARN": 1, "FAIL": 2}[r["verdict"]])
sys.exit(worst)
