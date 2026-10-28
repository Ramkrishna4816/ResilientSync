"""Run-directory writer: steps.csv, comm_events.csv, deliveries.csv, faults.json, transitions.json, meta.json."""
from __future__ import annotations

import csv
import json
from pathlib import Path


class CsvStream:
    """Append dict rows; header fixed by the first row (later missing keys -> blank)."""

    def __init__(self, path: Path):
        self.path, self._f, self._w, self._keys = Path(path), None, None, None

    def write(self, row: dict):
        if self._f is None:
            self._f = open(self.path, "w", newline="", encoding="utf-8")
            self._keys = list(row)
            self._w = csv.DictWriter(self._f, fieldnames=self._keys, extrasaction="raise")
            self._w.writeheader()
        extra = set(row) - set(self._keys)
        if extra:                                   # never drop data silently
            raise ValueError(f"{self.path.name}: columns not in header: {sorted(extra)}")
        self._w.writerow({k: row.get(k, "") for k in self._keys})

    def close(self):
        if self._f:
            self._f.close()
            self._f = None


def write_rows(path, rows):
    s = CsvStream(path)
    for r in rows:
        s.write(r)
    if not rows:                           # still create the file, header-only
        Path(path).write_text("", encoding="utf-8")
    s.close()


class RunWriter:
    def __init__(self, outdir):
        self.dir = Path(outdir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.steps = CsvStream(self.dir / "steps.csv")

    def step(self, row: dict):
        self.steps.write(row)

    def finish(self, adapter, meta: dict):
        self.steps.close()
        write_rows(self.dir / "comm_events.csv", adapter.sink.rows)
        write_rows(self.dir / "deliveries.csv", adapter.sim.delivery_rows)
        (self.dir / "faults.json").write_text(json.dumps(
            {"profile": adapter.sim.network.profile.as_dict(),
             "edges": adapter.sim.network.fault_log,
             "counts": adapter.sim.network.fault_counts}, indent=2), encoding="utf-8")
        (self.dir / "transitions.json").write_text(json.dumps(adapter.transitions(), indent=2), encoding="utf-8")
        (self.dir / "meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
