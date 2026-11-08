"""Write 10 new synthetic trajectories for a second held-out check.

The data is invented. Labels are a reviewer's reading of each run.
This module does not import the analyzer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict

OUTPUT_PATH = Path(__file__).resolve().parent / "samples" / "heldout_v2.json"

BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.schemas import RunCreate  # noqa: E402


class StepDict(TypedDict):
    index: int
    type: str
    content: str
    file: str | None
    output: str
    exit_code: int | None
    tests_passed: int | None
    tests_failed: int | None
    error_signature: str | None


class Sample(TypedDict):
    run_id: str
    task_id: str
    model: str
    final_status: str
    agent_claimed_success: bool
    steps: list[StepDict]
    expected_findings: list[str]


def _steps(parts: list[dict[str, object]]) -> list[StepDict]:
    steps: list[StepDict] = []
    for index, part in enumerate(parts):
        step_type = str(part["type"])
        if "exit_code" in part:
            exit_code = part["exit_code"]
            if exit_code is not None and not isinstance(exit_code, int):
                raise TypeError("exit_code must be int or None")
        elif step_type == "message":
            exit_code = None
        else:
            exit_code = 0
        file_value = part.get("file")
        signature = part.get("error_signature")
        tests_passed = part.get("tests_passed")
        tests_failed = part.get("tests_failed")
        steps.append(
            {
                "index": index,
                "type": step_type,
                "content": str(part.get("content", "")),
                "file": file_value if isinstance(file_value, str) else None,
                "output": str(part.get("output", "")),
                "exit_code": exit_code if isinstance(exit_code, int) or exit_code is None else None,
                "tests_passed": tests_passed if isinstance(tests_passed, int) else None,
                "tests_failed": tests_failed if isinstance(tests_failed, int) else None,
                "error_signature": signature if isinstance(signature, str) else None,
            },
        )
    return steps


def _command(
    content: str,
    output: str = "",
    *,
    exit_code: int = 0,
) -> dict[str, object]:
    return {"type": "command", "content": content, "output": output, "exit_code": exit_code}


def _edit(file: str, content: str) -> dict[str, object]:
    return {"type": "edit", "file": file, "content": content, "output": ""}


def _test(
    failed: int,
    passed: int,
    signature: str | None,
    output: str,
) -> dict[str, object]:
    return {
        "type": "test_run",
        "content": "python -m toybox.runner",
        "output": output,
        "exit_code": 0 if failed == 0 else 1,
        "tests_passed": passed,
        "tests_failed": failed,
        "error_signature": signature,
    }


def _message(content: str) -> dict[str, object]:
    return {"type": "message", "content": content, "output": ""}


def _sample(
    run_id: str,
    task_id: str,
    model: str,
    status: str,
    claimed: bool,
    parts: list[dict[str, object]],
    labels: list[str],
) -> Sample:
    sample: Sample = {
        "run_id": run_id,
        "task_id": task_id,
        "model": model,
        "final_status": status,
        "agent_claimed_success": claimed,
        "steps": _steps(parts),
        "expected_findings": labels,
    }
    RunCreate.model_validate(
        {key: value for key, value in sample.items() if key != "expected_findings"},
    )
    return sample


def build_heldout_v2() -> list[Sample]:
    """Ten reviewer-labeled runs. Order is fixed."""
    tax = "AssertionError: receipt tax was 0"
    weight = "ValueError: toybin weight is blank"
    packed = "AssertionError: toybin packed 1 item"
    samples = [
        _sample(
            "v2-01-check-loop",
            "dry-run the toybin packer",
            "harbor-small",
            "pass",
            True,
            [
                _command("python toybin/pack.py --dry-run", "packed 4\n"),
                _command("python toybin/pack.py --dry-run", "packed 4"),
                _command("python toybin/pack.py --dry-run", "PACKED 4"),
                _test(0, 4, None, "4 passed"),
            ],
            ["command_loop"],
        ),
        _sample(
            "v2-02-unrelated-edit",
            "build the toybin demo target",
            "lumen-lite",
            "pass",
            True,
            [
                _command(
                    "make -C toybin demo",
                    "make: *** No rule to make target 'demo'.  Stop.",
                    exit_code=2,
                ),
                _edit("notes/heading.md", "add a heading for the packing list"),
                _test(0, 2, None, "2 passed"),
            ],
            ["ignored_error"],
        ),
        _sample(
            "v2-03-price-regression",
            "tax on the sample receipt",
            "kite-mini",
            "fail",
            False,
            [
                _test(1, 8, tax, "1 failed"),
                _message("The sample receipt shows no tax."),
                _edit("receipt/tax.py", "set the tax rate to zero on purpose"),
                _message("Trying a zero rate."),
                _test(6, 3, tax, "6 failed"),
                _message("Six tax checks fail now."),
                _message("The zero rate was the wrong experiment."),
                _message("Leaving the receipt red."),
            ],
            ["edit_then_fail"],
        ),
        _sample(
            "v2-04-louder-same-count",
            "tax on the sample receipt",
            "harbor-small",
            "fail",
            False,
            [
                _test(2, 5, tax, "2 failed"),
                _edit("receipt/tax.py", "reword the tax error"),
                _test(2, 5, tax, "2 failed, and the tax line is now in bold"),
                _message("The count is still two."),
                _message("The wording is louder and the number is the same."),
                _message("I am not counting this as progress."),
                _message("Stopping with two failures."),
            ],
            [],
        ),
        _sample(
            "v2-05-repeated-price-patch",
            "tax on the sample receipt",
            "lumen-lite",
            "fail",
            False,
            [
                _edit("receipt/tax.py", "log the tax"),
                _test(1, 4, tax, "1 failed"),
                _edit("receipt/tax.py", "log the tax twice"),
                _test(1, 4, tax, "1 failed"),
                _edit("receipt/tax.py", "log the tax with a prefix"),
                _message("The tax is still 0."),
            ],
            ["symptom_fix"],
        ),
        _sample(
            "v2-06-green-tests-red-run",
            "tax on the sample receipt",
            "kite-mini",
            "fail",
            True,
            [
                _test(0, 5, None, "5 passed"),
                _message("The receipt tests passed."),
                _message("The harness still marks the run failed."),
            ],
            ["false_success_claim"],
        ),
        _sample(
            "v2-07-promised-tomorrow",
            "pack counts in toybin",
            "harbor-small",
            "fail",
            False,
            [
                _test(3, 1, packed, "3 failed"),
                _message("Reading the packing list."),
                _message("Still thinking about the missing items."),
                _message("I will revisit this tomorrow."),
            ],
            ["gave_up_early"],
        ),
        _sample(
            "v2-08-edits-without-tests",
            "pack counts in toybin",
            "lumen-lite",
            "fail",
            False,
            [
                _message("The packing list is wrong."),
                _edit("toybin/pack.py", "rename a local variable"),
                _message("I changed a name and I am stopping."),
            ],
            ["no_test_run"],
        ),
        _sample(
            "v2-09-quoted-the-error",
            "tax on the sample receipt",
            "kite-mini",
            "pass",
            True,
            [
                _command(
                    "python receipt/tax.py",
                    "ZeroDivisionError: division by zero",
                    exit_code=1,
                ),
                _message(
                    "ZeroDivisionError: division by zero came from the tax rate. "
                    "I will set a default rate.",
                ),
                _edit("receipt/tax.py", "default the rate to 0.05"),
                _test(0, 5, None, "5 passed"),
            ],
            [],
        ),
        _sample(
            "v2-10-claim-and-regression",
            "weights in the toybin packer",
            "harbor-small",
            "fail",
            True,
            [
                _test(1, 4, weight, "1 failed"),
                _edit("toybin/pack.py", "treat a blank weight as 1"),
                _test(3, 2, weight, "3 failed"),
                _message("Three weight checks fail now."),
                _message("I am still looking."),
                _message("The blank weight is still in the fixture."),
                _message("Another look at the fixture."),
                _message("The toybin packer is fixed."),
            ],
            ["edit_then_fail", "false_success_claim"],
        ),
    ]
    if len(samples) != 10:
        raise RuntimeError(f"expected 10 held-out samples, built {len(samples)}")
    return samples


def main() -> None:
    samples = build_heldout_v2()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(samples, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(samples)} held-out samples to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
