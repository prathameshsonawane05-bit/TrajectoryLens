"""Precision and recall on the second held-out set.

Prints the table and every mismatch. A miss does not fail the test.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from test_rule_quality import _score, _table

_REPO = Path(__file__).resolve().parents[2]
_GENERATOR = _REPO / "scripts" / "generate_heldout_v2.py"
_HELD_OUT = _REPO / "scripts" / "samples" / "heldout_v2.json"


def _build_heldout_v2() -> list[dict[str, object]]:
    spec = importlib.util.spec_from_file_location("generate_heldout_v2", _GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    samples = module.build_heldout_v2()
    if not isinstance(samples, list):
        raise TypeError("build_heldout_v2() did not return a list")
    return samples


def test_heldout_v2_set_shape() -> None:
    samples = _build_heldout_v2()
    assert len(samples) == 10
    assert len({str(sample["run_id"]) for sample in samples}) == 10
    assert _build_heldout_v2() == samples
    on_disk = json.loads(_HELD_OUT.read_text(encoding="utf-8"))
    assert on_disk == samples


def test_heldout_v2_rule_quality() -> None:
    rows, mismatches = _score(_build_heldout_v2())
    print(_table(rows))
    print("mismatches:")
    if mismatches:
        for line in mismatches:
            print(line)
    else:
        print("(none)")
    assert mismatches == []
    counts = {
        name: (tp, fp, fn, precision, recall)
        for name, tp, fp, fn, precision, recall in rows
    }
    assert counts["command_loop"][:3] == (1, 0, 0)
    assert counts["edit_then_fail"][:3] == (2, 0, 0)
    assert counts["false_success_claim"][:3] == (2, 0, 0)
    assert counts["gave_up_early"][:3] == (1, 0, 0)
    assert counts["symptom_fix"][:3] == (1, 0, 0)
    assert counts["ignored_error"][:3] == (1, 0, 0)
    assert counts["no_test_run"][:3] == (1, 0, 0)
    for _name, _tp, _fp, _fn, precision, recall in rows:
        assert precision == 1
        assert recall == 1
