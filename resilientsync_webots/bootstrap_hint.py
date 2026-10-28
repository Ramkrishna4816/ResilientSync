"""Stdlib-only helper: turn a controller start-up ImportError into an actionable message."""
import sys


def explain_import_failure(exc: BaseException, root) -> str:
    exe = sys.executable
    lines = ["", "=" * 72, "[rs_coordinator] STARTUP FAILED: " + f"{type(exc).__name__}: {exc}",
             f"  Python used by Webots for this controller: {exe}",
             f"  Project root: {root}"]
    if isinstance(exc, ModuleNotFoundError):
        lines += [f"  This interpreter lacks '{exc.name}'. In Git Bash run:",
                  f"      \"{exe}\" -m pip install -r requirements-webots.txt",
                  "  then:  python scripts/check_webots_env.py --write-runtime-ini",
                  "  (runtime.ini in webots_project/controllers/rs_coordinator/ selects this interpreter;",
                  "   without it Webots uses Tools > Preferences > Python command.)"]
    lines.append("=" * 72)
    return "\n".join(lines)
