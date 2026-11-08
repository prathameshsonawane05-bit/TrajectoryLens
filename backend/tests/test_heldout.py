"""Precision and recall on the held-out trajectories.

This test prints the table and every mismatch. It does not apply a cutoff
and it does not treat a miss as a failure.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from test_rule_quality import _score, _table

_REPO = Path(__file__).resolve().parents[2]
_GENERATOR = _REPO / "scripts" / "generate_heldout.py"
_HELD_OUT = _REPO / "scripts" / "samples" / "heldout.json"


def _build_heldout() -> list[dict[str, object]]:
    spec = importlib.util.spec_from_file_location("generate_heldout", _GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    samples = module.build_heldout()
    if not isinstance(samples, list):
        raise TypeError("build_heldout() did not return a list")
    return samples


def test_heldout_set_shape() -> None:
    samples = _build_heldout()
    assert len(samples) == 15
    assert len({str(sample["run_id"]) for sample in samples}) == 15
    assert _build_heldout() == samples
    on_disk = json.loads(_HELD_OUT.read_text(encoding="utf-8"))
    assert on_disk == samples


def test_heldout_rule_quality() -> None:
    rows, mismatches = _score(_build_heldout())
    print(_table(rows))
    print("mismatches:")
    if mismatches:
        for line in mismatches:
            print(line)
    else:
        print("(none)")
