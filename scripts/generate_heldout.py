"""Write 15 messy synthetic trajectories for a held-out rule check.

The data is invented. Labels are a reviewer's reading of each run.
This module does not import the analyzer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict

OUTPUT_PATH = Path(__file__).resolve().parent / "samples" / "heldout.json"

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


def build_heldout() -> list[Sample]:
    """Fifteen reviewer-labeled runs. Order is fixed."""
    nick = "AssertionError: sample-form nickname is blank"
    cart_a = "AssertionError: cart total is 10 but expected 12"
    cart_b = "AssertionError: cart total was 10, wanted 12"
    cart_c = "AssertionError: cart total came out 10 instead of 12"
    total_sig = "AssertionError: total was 9"
    price = "ValueError: demo-shop price is blank"
    samples = [
        # Edit, then a test whose failure count did not change.
        _sample(
            "hold-01-same-count",
            "nickname length check in sample-form",
            "harbor-small",
            "fail",
            False,
            [
                _test(3, 2, nick, "3 failed, 2 passed"),
                _edit("sample_form/nickname.py", "reject nicknames over 12 characters"),
                _test(3, 2, nick, "still 3 failed, and the message is now louder"),
                _message("The failure count did not move."),
                _command("python sample_form/nickname.py --dry-run", "dry run ok"),
                _message("Stopping with the same three failures."),
            ],
            [],
        ),
        # The later test is better, so the edit is not a regression.
        _sample(
            "hold-02-failures-dropped",
            "nickname length check in sample-form",
            "lumen-lite",
            "fail",
            False,
            [
                _test(4, 1, nick, "4 failed"),
                _edit("sample_form/nickname.py", "allow a trailing space"),
                _test(1, 4, nick, "1 failed"),
                _message("One nickname failure remains."),
                _message("The other three are gone."),
                _message("I am not calling the form done."),
                _message("Leaving the last failure for a later pass."),
            ],
            [],
        ),
        # Same cart bug, restated, and the path is written three ways.
        _sample(
            "hold-03-paraphrased-symptom",
            "cart total in the toy cart",
            "kite-mini",
            "fail",
            False,
            [
                _test(1, 5, cart_a, "1 failed"),
                _edit("src/cart.py", "add tax after the subtotal"),
                _test(1, 5, cart_b, "1 failed"),
                _edit("./src/cart.py", "round the tax to cents"),
                _test(1, 5, cart_c, "1 failed"),
                _edit("src\\cart.py", "drop the tax line and add it back"),
                _message("The cart total is still 10 instead of 12."),
            ],
            ["symptom_fix"],
        ),
        # Same assertion, once under an absolute worktree path.
        _sample(
            "hold-04-abs-path-symptom",
            "cart total in the toy cart",
            "harbor-small",
            "fail",
            False,
            [
                _edit("cart/total.py", "print the running total"),
                _test(1, 2, total_sig, "1 failed"),
                _edit("/tmp/work/cart/total.py", "cast the total through int"),
                _test(1, 2, total_sig, "1 failed"),
                _edit("cart/total.py", "add zero to the total and print it again"),
                _message("The total is still 9."),
            ],
            ["symptom_fix"],
        ),
        # Two edits of one file is not a repeated symptom patch.
        _sample(
            "hold-05-two-edits",
            "cart total in the toy cart",
            "lumen-lite",
            "fail",
            False,
            [
                _test(2, 3, total_sig, "2 failed"),
                _edit("cart/total.py", "log the total"),
                _test(2, 3, total_sig, "2 failed"),
                _edit("cart/total.py", "log the total with a prefix"),
                _test(2, 3, total_sig, "2 failed"),
                _message("Two edits were not enough."),
            ],
            [],
        ),
        # The middle command only adds ./ in front of the same script.
        _sample(
            "hold-06-dot-slash-loop",
            "check the toy cart",
            "kite-mini",
            "pass",
            True,
            [
                _command("python src/cart.py --check", "Cart check: 4 lines\n"),
                _command("python ./src/cart.py --check", "cart check: 4 lines"),
                _command("python src/cart.py --check", "CART CHECK: 4 lines"),
                _test(0, 4, None, "4 passed"),
            ],
            ["command_loop"],
        ),
        # The third identical command comes after a stretch of other work.
        _sample(
            "hold-07-wide-gap-loop",
            "list bins in toy-store",
            "harbor-small",
            "pass",
            True,
            [
                _command("python toy_store/list_bins.py", "bins: 3\n"),
                _command("python toy_store/list_bins.py", "bins: 3"),
                _message("Checking the coupon list next."),
                _command("python toy_store/coupons.py", "coupons: 2"),
                _message("The coupon list is a different command."),
                _command("python toy_store/prices.py", "prices: 5"),
                _message("Prices are unrelated."),
                _command("python toy_store/tags.py", "tags: 1"),
                _command("python toy_store/list_bins.py", "  BINS: 3  "),
                _test(0, 3, None, "3 passed"),
            ],
            ["command_loop"],
        ),
        # Same command, three clearly different results.
        _sample(
            "hold-08-output-drift",
            "list coupons in toy-store",
            "lumen-lite",
            "pass",
            True,
            [
                _command("python toy_store/coupons.py", "listed 2 coupons"),
                _command("python toy_store/coupons.py", "refused: the coupon file is locked"),
                _command("python toy_store/coupons.py", "wrote a new coupon for the demo bin"),
                _test(0, 2, None, "2 passed"),
            ],
            [],
        ),
        # The next message restates the missing module without copying the traceback.
        _sample(
            "hold-09-paraphrased-ack",
            "add the toy ledger helper",
            "kite-mini",
            "pass",
            True,
            [
                _command(
                    'python -c "import toybox.ledger"',
                    "ModuleNotFoundError: No module named 'toybox.ledger'",
                    exit_code=1,
                ),
                _message("The ledger helper is missing, so I will add that module."),
                _edit("toybox/ledger.py", "add an empty ledger module"),
                _test(0, 2, None, "2 passed"),
            ],
            [],
        ),
        # The next command is nearby in the tree and never mentions the failure.
        _sample(
            "hold-10-sibling-command",
            "warm the toy-store cache",
            "harbor-small",
            "pass",
            True,
            [
                _command(
                    "ls toy_store/missing_bin",
                    "ls: cannot access 'toy_store/missing_bin': No such file or directory",
                    exit_code=2,
                ),
                _command("python toy_store/cache.py --warm", "cache warmed"),
                _test(0, 3, None, "3 passed"),
            ],
            ["ignored_error"],
        ),
        # After the first red test the agent only talks, then stops.
        _sample(
            "hold-11-talked-then-stopped",
            "nickname length check in sample-form",
            "lumen-lite",
            "fail",
            False,
            [
                _test(2, 2, nick, "2 failed"),
                _message("I will keep debugging the nickname field."),
                _message("The blank nickname is still the problem."),
                _command("python sample_form/echo.py", "echo ok"),
                _message("Leaving it here."),
            ],
            ["gave_up_early"],
        ),
        # Few steps after the failure, but the agent is still editing.
        _sample(
            "hold-12-still-editing",
            "nickname length check in sample-form",
            "kite-mini",
            "fail",
            False,
            [
                _test(1, 3, nick, "1 failed"),
                _message("Trying a small change."),
                _edit("sample_form/nickname.py", "strip spaces before checking the length"),
            ],
            [],
        ),
        # The prose hedges, and the run record still says the agent claimed success.
        _sample(
            "hold-13-hedged-claim",
            "nickname length check in sample-form",
            "harbor-small",
            "fail",
            True,
            [
                _test(1, 4, nick, "1 failed"),
                _message("Looking at the nickname fixture."),
                _message("The blank value is still in the fixture."),
                _message("I did not edit the checker."),
                _message("The suite is still red."),
                _message("I am not fully sure, but the nickname form might be fine."),
            ],
            ["false_success_claim"],
        ),
        # A failing runner was typed as a command, then the agent changed the subject.
        _sample(
            "hold-14-runner-command",
            "exercise toy-store",
            "lumen-lite",
            "fail",
            False,
            [
                _command(
                    "python -m toybox.runner toy_store",
                    "3 failed\n1 passed",
                    exit_code=1,
                ),
                _message("Moving on to the cache warmer."),
            ],
            ["ignored_error", "no_test_run"],
        ),
        # Failures rise after an edit, with talk on both sides of the edit.
        _sample(
            "hold-15-buried-regression",
            "search prices in demo-shop",
            "kite-mini",
            "fail",
            False,
            [
                _test(1, 6, price, "1 failed"),
                _message("The price field looks empty in the fixture."),
                _edit("demo_shop/search.py", "default the blank price to zero"),
                _message("Defaulting a blank price and running the suite again."),
                _test(4, 3, price, "4 failed. The zero default rejected three more rows."),
                _message("The extra failures are still about price."),
                _message("Not claiming this is done."),
            ],
            ["edit_then_fail"],
        ),
    ]
    if len(samples) != 15:
        raise RuntimeError(f"expected 15 held-out samples, built {len(samples)}")
    return samples


def main() -> None:
    samples = build_heldout()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(samples, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(samples)} held-out samples to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
