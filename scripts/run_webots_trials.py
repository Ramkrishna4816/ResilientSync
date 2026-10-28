"""Launch Webots once per (scenario, arm, seed) and collect the run directories.

    python scripts/run_webots_trials.py --scenarios blackout_gentle --arms adaptive_supervisor --seeds 100
    python scripts/run_webots_trials.py --dry-run          # print commands only (no Webots needed)

STATUS: not executed in the authoring environment (no Webots installed there).
Webots CLI flags used: --mode=fast --batch --minimize --stdout --stderr (+ --no-rendering optional).
"""
import argparse, json, os, platform, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))


def find_webots(explicit=None):
    if explicit:
        return explicit
    home = os.environ.get("WEBOTS_HOME")
    cands = []
    if home:
        cands += [Path(home) / "msys64/mingw64/bin/webots.exe", Path(home) / "webots", Path(home) / "Contents/MacOS/webots"]
    la = os.environ.get("LOCALAPPDATA")
    if la:
        cands.append(Path(la) / "Programs" / "Webots" / "msys64" / "mingw64" / "bin" / "webots.exe")   # per-user install
    cands += [Path(r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe"),
              Path("/usr/local/webots/webots"), Path("/Applications/Webots.app/Contents/MacOS/webots")]
    for c in cands:
        if c.exists():
            return str(c)
    return shutil.which("webots") or shutil.which("webots.exe")


ap = argparse.ArgumentParser()
ap.add_argument("--scenarios", nargs="+", default=["nominal_gentle", "blackout_gentle"])
ap.add_argument("--arms", nargs="+", default=["adaptive_supervisor"])
ap.add_argument("--seeds", nargs="+", type=int, default=[100])
ap.add_argument("--n-agents", type=int, default=5, choices=[3, 5])
ap.add_argument("--duration", type=float, default=18.0)
ap.add_argument("--out", default=str(ROOT / "results" / "webots"))
ap.add_argument("--webots-exe", default=None)
ap.add_argument("--mode", default="fast", choices=["fast", "realtime"])
ap.add_argument("--no-rendering", action="store_true")
ap.add_argument("--timeout", type=float, default=900.0)
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--show", action="store_true", help="do not minimise the Webots window")
ap.add_argument("--keep-open", action="store_true", help="leave Webots open after the scenario ends (close the window yourself)")
ap.add_argument("--no-diagnose", action="store_true", help="skip the automatic post-run diagnosis")
a = ap.parse_args()

exe = find_webots(a.webots_exe)
if not exe and not a.dry_run:
    sys.exit("Webots executable not found. Pass --webots-exe or set WEBOTS_HOME (see README).")
world = ROOT / "webots_project" / "worlds" / f"resilientsync_{a.n_agents}robots.wbt"
cfg_dir = Path(a.out) / "_configs"; cfg_dir.mkdir(parents=True, exist_ok=True)
failed = 0
for sc in a.scenarios:
    for arm in a.arms:
        for seed in a.seeds:
            rid = f"{sc}__{arm}__s{seed}__n{a.n_agents}"
            cfg = {"scenario": sc, "arm": arm, "seed": seed, "duration_s": a.duration, "n_agents": a.n_agents,
                   "out_dir": str(Path(a.out)), "teleport_initial": True, "quit_when_done": not a.keep_open, "frame": [0, 0, 0]}
            cfg_path = cfg_dir / f"{rid}.json"; cfg_path.write_text(json.dumps(cfg, indent=2))
            cmd = [exe or "webots", f"--mode={a.mode}", "--batch", "--stdout", "--stderr"] + ([] if a.show else ["--minimize"])
            if a.no_rendering: cmd.append("--no-rendering")
            cmd.append(str(world))
            print(("DRY " if a.dry_run else "RUN "), rid, "\n   ", " ".join(cmd), f"\n    env RS_RUN_CONFIG={cfg_path}")
            if a.dry_run: continue
            env = dict(os.environ, RS_RUN_CONFIG=str(cfg_path))
            if exe and "RS_WEBOTS_VERSION" not in env:
                try:
                    v = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30)
                    env["RS_WEBOTS_VERSION"] = (v.stdout or v.stderr).strip().splitlines()[0] if (v.stdout or v.stderr).strip() else "unknown"
                except Exception:
                    pass
            try:
                r = subprocess.run(cmd, env=env, timeout=None if a.keep_open else a.timeout, capture_output=True, text=True)
                (Path(a.out) / f"{rid}.webots.log").write_text((r.stdout or "") + "\n--- stderr ---\n" + (r.stderr or ""))
                ok = (Path(a.out) / rid / "meta.json").exists()
                print("    exit", r.returncode, "| meta.json written:", ok, "|", Path(a.out) / rid)
                failed += (not ok)
                if not ok:
                    print("    NO LOGS. Look at:", Path(a.out) / f"{rid}.webots.log", "and", Path(a.out) / rid / "coordinator_error.txt")
                    print("    Webots stdout/stderr tail:\n      " + "\n      ".join(((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-15:]))
                elif not a.no_diagnose:
                    from resilientsync_webots.diagnose import diagnose
                    res = diagnose(Path(a.out) / rid)
                    print("    diagnosis:", res["verdict"])
                    for c in res["checks"]:
                        if c["level"] in ("FAIL", "WARN"):
                            print(f"      [{c['level']}] {c['id']}: {c['msg'].splitlines()[0]}")
                    failed += (res["verdict"] == "FAIL")
                    try:                                  # make the run viewable on the website (Replay tab)
                        from resilientsync_webots.dashboard_export import recording_from_run_dir
                        from simulation.recording import save_recording
                        rec, worst = recording_from_run_dir(Path(a.out) / rid)
                        (ROOT / "recordings").mkdir(exist_ok=True)
                        dest = ROOT / "recordings" / f"webots__{rid}.json"
                        save_recording(rec, dest)
                        print(f"    website replay: recordings/{dest.name}  (engine reproduces logged commands to {worst:.1e})")
                    except Exception as exc:
                        print("    (could not export a dashboard recording:", type(exc).__name__, exc, ")")
            except subprocess.TimeoutExpired:
                print("    TIMEOUT"); failed += 1
sys.exit(1 if failed else 0)
