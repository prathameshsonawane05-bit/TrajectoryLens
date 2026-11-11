"""Precision and recall of the rule analyzer on the synthetic samples."""

from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.analyzer import run_analysis
from app.models import Run, Step
from app.schemas import RunCreate

RULE_NAMES = (
    "command_loop",
    "edit_then_fail",
    "false_success_claim",
    "gave_up_early",
    "symptom_fix",
    "ignored_error",
    "no_test_run",
)

_REPO = Path(__file__).resolve().parents[2]
_GENERATOR = _REPO / "scripts" / "generate_samples.py"


def _build_samples() -> list[dict[str, object]]:
    spec = importlib.util.spec_from_file_location("generate_samples", _GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    samples = module.build_samples()
    if not isinstance(samples, list):
        raise TypeError("build_samples() did not return a list")
    return samples


def _run_from_sample(sample: dict[str, object]) -> Run:
    payload = {key: value for key, value in sample.items() if key != "expected_findings"}
    parsed = RunCreate.model_validate(payload)
    return Run(
        run_id=parsed.run_id,
        task_id=parsed.task_id,
        model=parsed.model,
        final_status=parsed.final_status,
        agent_claimed_success=parsed.agent_claimed_success,
        created_at=datetime.now(UTC),
        steps=[
            Step(
                index=step.index,
                type=step.type,
                content=step.content,
                file=step.file,
                output=step.output,
                exit_code=step.exit_code,
                tests_passed=step.tests_passed,
                tests_failed=step.tests_failed,
                error_signature=step.error_signature,
            )
            for step in parsed.steps
        ],
    )


def _labels(sample: dict[str, object]) -> set[str]:
    raw = sample["expected_findings"]
    if not isinstance(raw, list):
        raise TypeError(f"{sample.get('run_id')} expected_findings is not a list")
    return {str(item) for item in raw}


ScoreRow = tuple[str, int, int, int, float | None, float | None]


def _ratio(count: int, total: int) -> float | None:
    if total == 0:
        return None
    return count / total


def _score(samples: list[dict[str, object]]) -> tuple[list[ScoreRow], list[str]]:
    counts: dict[str, dict[str, int]] = {
        name: {"tp": 0, "fp": 0, "fn": 0} for name in RULE_NAMES
    }
    mismatches: list[str] = []
    for sample in samples:
        expected = _labels(sample)
        predicted = {finding.type for finding in run_analysis(_run_from_sample(sample))}
        run_id = str(sample["run_id"])
        if expected != predicted:
            mismatches.append(
                f"{run_id}: expected {sorted(expected) or '[]'} "
                f"predicted {sorted(predicted) or '[]'}",
            )
        for name in RULE_NAMES:
            if name in expected and name in predicted:
                counts[name]["tp"] += 1
            elif name in predicted:
                counts[name]["fp"] += 1
            elif name in expected:
                counts[name]["fn"] += 1
    rows: list[ScoreRow] = []
    for name in RULE_NAMES:
        tp = counts[name]["tp"]
        fp = counts[name]["fp"]
        fn = counts[name]["fn"]
        rows.append((name, tp, fp, fn, _ratio(tp, tp + fp), _ratio(tp, tp + fn)))
    return rows, mismatches


def _rate_cell(rate: float | None, width: int) -> str:
    if rate is None:
        return f"{'N/A':>{width}}"
    return f"{rate:{width}.3f}"


def _table(rows: list[ScoreRow]) -> str:
    header = f"{'rule':<22} {'tp':>4} {'fp':>4} {'fn':>4} {'precision':>10} {'recall':>8}"
    lines = [header, "-" * len(header)]
    for name, tp, fp, fn, precision, recall in rows:
        precision_cell = _rate_cell(precision, 10)
        recall_cell = _rate_cell(recall, 8)
        lines.append(f"{name:<22} {tp:4d} {fp:4d} {fn:4d} {precision_cell} {recall_cell}")
    return "\n".join(lines)


def _is_weak(rate: float | None) -> bool:
    if rate is None:
        return True
    return rate < 0.8


def test_sample_set_covers_every_rule() -> None:
    samples = _build_samples()
    assert len(samples) == 40
    assert len({str(sample["run_id"]) for sample in samples}) == 40
    clean = [sample for sample in samples if _labels(sample) == set()]
    assert len(clean) == 8
    coverage: Counter[str] = Counter()
    duals = 0
    for sample in samples:
        labels = _labels(sample)
        assert labels <= set(RULE_NAMES)
        if len(labels) == 2:
            duals += 1
        assert len(labels) <= 2
        coverage.update(labels)
        RunCreate.model_validate(
            {key: value for key, value in sample.items() if key != "expected_findings"},
        )
    assert duals >= 4
    for name in RULE_NAMES:
        assert coverage[name] >= 4, f"{name} appears {coverage[name]} times"


def test_samples_are_reproducible() -> None:
    assert _build_samples() == _build_samples()


def test_rule_quality() -> None:
    rows, mismatches = _score(_build_samples())
    rendered = _table(rows)
    print(rendered)
    if mismatches:
        print("mismatches:")
        for line in mismatches:
            print(line)
    weak = [
        f"{name} precision={_rate_cell(precision, 0).strip()} "
        f"recall={_rate_cell(recall, 0).strip()}"
        for name, _tp, _fp, _fn, precision, recall in rows
        if _is_weak(precision) or _is_weak(recall)
    ]
    assert not weak, rendered + "\n" + "\n".join(weak)


def test_ratio_is_undefined_when_the_denominator_is_zero() -> None:
    assert _ratio(0, 0) is None
    assert _ratio(0, 2) == 0.0
    assert _ratio(1, 1) == 1.0
    assert _ratio(2, 3) == 2 / 3


def test_table_prints_undefined_precision_as_na() -> None:
    rendered = _table([("command_loop", 0, 0, 2, None, 0.0)])
    line = rendered.splitlines()[-1]
    assert "N/A" in line
    assert "0.000" in line
    assert "1.000" not in line


def test_table_prints_defined_ones_as_1_000() -> None:
    rendered = _table([("edit_then_fail", 1, 0, 0, 1.0, 1.0)])
    assert "1.000" in rendered


def test_training_scores_are_defined_rates() -> None:
    rows, _mismatches = _score(_build_samples())
    assert len(rows) == len(RULE_NAMES)
    for _name, _tp, _fp, _fn, precision, recall in rows:
        assert isinstance(precision, float)
        assert isinstance(recall, float)
