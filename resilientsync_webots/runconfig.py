"""Run-configuration loading shared by the Webots coordinator and tests.

Relative paths are resolved against the PROJECT ROOT, never against the process working
directory: Webots starts controllers with the controller's own folder as cwd, so a relative
"out_dir" would otherwise silently land inside webots_project/controllers/rs_coordinator/.
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULTS = {"duration_s": 18.0, "n_agents": 5, "out_dir": "results/webots", "teleport_initial": True,
            "quit_when_done": True, "frame": [0.0, 0.0, 0.0]}
REQUIRED = ("scenario", "arm", "seed")


def load_run_config(path, root, known_scenarios=None, known_arms=None, n_world=None) -> dict:
    cfg = dict(DEFAULTS)
    cfg.update(json.loads(Path(path).read_text(encoding="utf-8")))
    missing = [k for k in REQUIRED if k not in cfg]
    if missing:
        raise ValueError(f"run config {path} is missing {missing}")
    if known_scenarios is not None and cfg["scenario"] not in known_scenarios:
        raise ValueError(f"unknown scenario {cfg['scenario']!r}; choose from {sorted(known_scenarios)}")
    if known_arms is not None and cfg["arm"] not in known_arms:
        raise ValueError(f"unknown arm {cfg['arm']!r}; choose from {sorted(known_arms)}")
    if cfg["n_agents"] == "auto":                       # take the robot count from the loaded world
        if not n_world:
            raise ValueError('n_agents "auto" needs the robot count of the loaded world')
        cfg["n_agents"] = int(n_world)
    elif n_world and int(cfg["n_agents"]) != int(n_world):
        raise ValueError(f"run config says n_agents={cfg['n_agents']} but the loaded world has {n_world} robots "
                         f"(DEF RS_0..RS_{n_world-1}); open resilientsync_{cfg['n_agents']}robots.wbt or set "
                         f'"n_agents": "auto"')
    if int(cfg["n_agents"]) not in (3, 5):
        raise ValueError("n_agents must be 3 or 5 (the shipped worlds)")
    out = Path(cfg["out_dir"])
    cfg["out_dir"] = str(out if out.is_absolute() else Path(root) / out)
    cfg["seed"], cfg["n_agents"], cfg["duration_s"] = int(cfg["seed"]), int(cfg["n_agents"]), float(cfg["duration_s"])
    return cfg
