"""Write 40 synthetic trajectories with hidden expected_findings labels.

The data is invented. It does not come from a real client, company, or
evaluation platform. Output is fully determined by SEED.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import TypedDict

SEED = 0
MODELS = ("harbor-small", "lumen-lite", "kite-mini")
OUTPUT_PATH = Path(__file__).resolve().parent / "samples" / "trajectories.json"

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
    file: str | None = None,
) -> dict[str, object]:
    return {
        "type": "command",
        "content": content,
        "output": output,
        "exit_code": exit_code,
        "file": file,
    }


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
    rng: random.Random,
    run_id: str,
    task_id: str,
    final_status: str,
    claimed: bool,
    parts: list[dict[str, object]],
    expected: list[str],
) -> Sample:
    sample: Sample = {
        "run_id": run_id,
        "task_id": task_id,
        "model": rng.choice(MODELS),
        "final_status": final_status,
        "agent_claimed_success": claimed,
        "steps": _steps(parts),
        "expected_findings": expected,
    }
    payload = {key: value for key, value in sample.items() if key != "expected_findings"}
    RunCreate.model_validate(payload)
    return sample


def build_samples() -> list[Sample]:
    rng = random.Random(SEED)
    samples: list[Sample] = []

    # Eight passes. Four of them respond to a failing command, so they are not
    # ignored_error even though the command exits non-zero.
    samples.append(
        _sample(
            rng,
            "clean-01",
            "fix pagination bug in toy-api",
            "pass",
            True,
            [
                _command("python toy_api/paginate.py --page 2", "page ok: 10 rows"),
                _edit("toy_api/paginate.py", "return the slice for the requested page"),
                _test(0, 6, None, "6 passed"),
                _message("Pagination in toy-api now returns the second page."),
            ],
            [],
        ),
    )
    samples.append(
        _sample(
            rng,
            "clean-02",
            "add retry to fake-client",
            "pass",
            False,
            [
                _command("python -m fake_client.ping", "pong"),
                _test(0, 4, None, "4 passed"),
                _message("The fake client retries once and then succeeds."),
            ],
            [],
        ),
    )
    samples.append(
        _sample(
            rng,
            "clean-03",
            "sort search results in demo-shop",
            "pass",
            True,
            [
                _test(0, 3, None, "3 passed"),
                _command("python demo_shop/search.py --q mug", "sorted 3 hits"),
                _message("Demo shop search is ordered by price."),
            ],
            [],
        ),
    )
    samples.append(
        _sample(
            rng,
            "clean-04",
            "validate nickname in sample-form",
            "pass",
            False,
            [
                _command("python sample_form/check.py", "nickname accepted"),
                _edit("sample_form/check.py", "reject a blank nickname"),
                _test(0, 5, None, "5 passed"),
            ],
            [],
        ),
    )
    samples.append(
        _sample(
            rng,
            "clean-05",
            "fix pagination bug in toy-api",
            "pass",
            True,
            [
                _command(
                    "python toy_api/paginate.py --page 2",
                    "Traceback (most recent call last):\n"
                    "ModuleNotFoundError: No module named 'toy_api'",
                    exit_code=1,
                ),
                _edit("toy_api/paginate.py", "export the paginate function"),
                _test(0, 4, None, "4 passed"),
                _message("The second page of toy-api loads."),
            ],
            [],
        ),
    )
    samples.append(
        _sample(
            rng,
            "clean-06",
            "cache lookup in toy-store",
            "pass",
            False,
            [
                _command(
                    "python toy_store/cache.py",
                    "Traceback (most recent call last):\n"
                    "ModuleNotFoundError: No module named 'toy_store'",
                    exit_code=1,
                ),
                _edit("./toy_store/cache.py", "create the missing cache helper"),
                _test(0, 3, None, "3 passed"),
            ],
            [],
        ),
    )
    samples.append(
        _sample(
            rng,
            "clean-07",
            "parse month names in playground-cal",
            "pass",
            True,
            [
                _command(
                    "python playground_cal/parse.py",
                    "ImportError: cannot import name 'month_number' from 'playground_cal.parse'",
                    exit_code=1,
                ),
                _message(
                    "The ImportError for month_number is a missing helper. I will add it.",
                ),
                _edit("playground_cal/parse.py", "add month_number for the playground calendar"),
                _test(0, 4, None, "4 passed"),
            ],
            [],
        ),
    )
    samples.append(
        _sample(
            rng,
            "clean-08",
            "add retry to fake-client",
            "pass",
            False,
            [
                _command(
                    "python -m fake_client.call",
                    "TimeoutError: fake-client timed out talking to the stub server",
                    exit_code=1,
                ),
                _message("TimeoutError from the stub means the retry wrapper never ran."),
                _edit("fake_client/call.py", "retry the stub call twice"),
                _test(0, 5, None, "5 passed"),
            ],
            [],
        ),
    )

    catalog = "retrieved {count} items from the toy catalog"
    samples.append(
        _sample(
            rng,
            "loop-01",
            "fix pagination bug in toy-api",
            "pass",
            False,
            [
                _command("python toy_api/paginate.py --page 2", "page items: 0"),
                _command("python toy_api/paginate.py --page 2", "page items: 0"),
                _command("python toy_api/paginate.py --page 2", "page items: 0"),
                _test(0, 1, None, "1 passed"),
            ],
            ["command_loop"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "loop-02",
            "sort search results in demo-shop",
            "pass",
            False,
            [
                _command("python demo_shop/search.py --q mug", catalog.format(count=10))
                for _ in range(5)
            ],
            ["command_loop"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "loop-03",
            "cache lookup in toy-store",
            "pass",
            False,
            [
                _test(0, 2, None, "2 passed"),
                _command("python toy_store/cache.py --key sku-1", "cache miss for sku-1"),
                _edit("toy_store/notes.py", "jot down the miss"),
                _command("python toy_store/cache.py --key sku-1", "cache miss for sku-1"),
                _message("The toy-store cache still misses sku-1."),
                _command("python toy_store/cache.py --key sku-1", "cache miss for sku-1"),
            ],
            ["command_loop"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "loop-04",
            "add retry to fake-client",
            "pass",
            False,
            [
                _command(
                    "python -m fake_client.ping",
                    "retrieved 10 items from the toy catalog",
                ),
                _command(
                    "python -m fake_client.ping",
                    "retrieved 11 items from the toy catalog",
                ),
                _command(
                    "python -m fake_client.ping",
                    "retrieved 10 items from the toy catalog",
                ),
            ],
            ["command_loop"],
        ),
    )

    page_sig = "AssertionError: expected page 2 to return 10 rows, got 0"
    samples.append(
        _sample(
            rng,
            "edit-fail-01",
            "fix pagination bug in toy-api",
            "fail",
            False,
            [
                _test(1, 4, page_sig, "1 failed"),
                _command("python toy_api/show.py", "current slice starts at 0"),
                _edit("toy_api/paginate.py", "shift the slice start by one"),
                _test(3, 2, page_sig, "3 failed"),
            ],
            ["edit_then_fail"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "edit-fail-02",
            "sort search results in demo-shop",
            "fail",
            False,
            [
                _test(2, 3, "ValueError: demo-shop price is blank", "2 failed"),
                _edit("demo_shop/search.py", "coerce blank prices to zero"),
                _message("Blank prices should sort last."),
                _test(4, 1, "ValueError: demo-shop price is blank", "4 failed"),
            ],
            ["edit_then_fail"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "edit-fail-03",
            "validate nickname in sample-form",
            "pass",
            False,
            [
                _test(1, 5, "KeyError: sample-form field nickname", "1 failed"),
                _edit("sample_form/check.py", "read nickname with a default"),
                _test(2, 4, "KeyError: sample-form field nickname", "2 failed"),
            ],
            ["edit_then_fail"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "edit-fail-04",
            "parse month names in playground-cal",
            "fail",
            False,
            [
                _test(1, 2, "AssertionError: playground-cal parsed month 13", "1 failed"),
                _edit("playground_cal/parse.py", "clamp the month into 1..12"),
                _command("python playground_cal/show.py", "month=13"),
                _test(2, 1, "AssertionError: playground-cal parsed month 13", "2 failed"),
            ],
            ["edit_then_fail"],
        ),
    )

    samples.append(
        _sample(
            rng,
            "claim-01",
            "fix pagination bug in toy-api",
            "fail",
            True,
            [
                _test(0, 6, None, "6 passed"),
                _message("The toy-api page size looks correct to me."),
            ],
            ["false_success_claim"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "claim-02",
            "add retry to fake-client",
            "fail",
            True,
            [
                _command("python -m fake_client.ping", "pong"),
                _test(0, 4, None, "4 passed"),
                _message("Retries are in place and the stub answers."),
            ],
            ["false_success_claim"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "claim-03",
            "sort search results in demo-shop",
            "fail",
            True,
            [
                _test(0, 3, None, "3 passed"),
                _edit("demo_shop/search.py", "sort hits by the price field"),
                _message("Demo shop results are sorted."),
            ],
            ["false_success_claim"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "claim-04",
            "cache lookup in toy-store",
            "fail",
            True,
            [
                _command("python toy_store/cache.py --key sku-1", "hit"),
                _test(0, 2, None, "2 passed"),
            ],
            ["false_success_claim"],
        ),
    )

    stop = "I am stopping here."
    samples.append(
        _sample(
            rng,
            "giveup-01",
            "fix pagination bug in toy-api",
            "fail",
            False,
            [
                _test(2, 1, page_sig, "2 failed"),
                _message(stop),
            ],
            ["gave_up_early"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "giveup-02",
            "add retry to fake-client",
            "fail",
            False,
            [
                _test(1, 2, "TimeoutError: fake-client retry budget exhausted", "1 failed"),
                _command("python -m fake_client.ping", "no answer"),
                _message(stop),
            ],
            ["gave_up_early"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "giveup-03",
            "sort search results in demo-shop",
            "fail",
            False,
            [
                _test(3, 1, "ValueError: demo-shop price is blank", "3 failed"),
                _command("python demo_shop/show.py", "3 unsorted hits"),
                _command("python demo_shop/count.py", "count=3"),
                _message("Leaving the demo shop unsorted."),
            ],
            ["gave_up_early"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "giveup-04",
            "validate nickname in sample-form",
            "fail",
            False,
            [
                _command("python sample_form/show.py", "form has 4 fields"),
                _test(1, 4, "KeyError: sample-form field nickname", "1 failed"),
                _command("python sample_form/count.py", "fields=4"),
                _command("pwd", "/work/sample-form"),
                _message(stop),
            ],
            ["gave_up_early"],
        ),
    )

    cache_sig = "LookupError: toy-store cache missed key sku-1"
    samples.append(
        _sample(
            rng,
            "symptom-01",
            "cache lookup in toy-store",
            "fail",
            False,
            [
                _edit("toy_store/cache.py", "print the missing key"),
                _test(1, 2, cache_sig, "1 failed"),
                _edit("toy_store/cache.py", "return an empty dict on a miss"),
                _test(1, 2, cache_sig, "1 failed"),
                _edit("toy_store/cache.py", "log the miss and return none"),
                _message("The same cache miss is still there."),
            ],
            ["symptom_fix"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "symptom-02",
            "fix pagination bug in toy-api",
            "fail",
            False,
            [
                _edit("toy_api/paginate.py", "hard-code the page length"),
                _test(2, 2, page_sig, "2 failed"),
                _edit("toy_api/paginate.py", "slice only the first page"),
                _test(2, 2, page_sig, "2 failed"),
                _edit("toy_api/paginate.py", "swap the start and end indexes"),
            ],
            ["symptom_fix"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "symptom-03",
            "parse month names in playground-cal",
            "fail",
            False,
            [
                _edit("./playground_cal/parse.py", "print the raw month token"),
                _test(1, 3, "AssertionError: playground-cal parsed month 13", "1 failed"),
                _edit("playground_cal/parse.py", "strip spaces from the token"),
                _test(1, 3, "AssertionError: playground-cal parsed month 13", "1 failed"),
                _edit("./playground_cal/parse.py", "lowercase the token before parsing"),
                _message("Month 13 is still accepted."),
            ],
            ["symptom_fix"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "symptom-04",
            "sort search results in demo-shop",
            "fail",
            False,
            [
                _edit("./demo_shop/search.py", "print each hit"),
                _test(1, 3, "ValueError: demo-shop price is blank", "1 failed"),
                _edit("demo_shop/search.py", "skip a hit when the title is empty"),
                _test(1, 3, "ValueError: demo-shop price is blank", "1 failed"),
                _edit("./demo_shop/search.py", "replace a blank title with 'item'"),
            ],
            ["symptom_fix"],
        ),
    )

    samples.append(
        _sample(
            rng,
            "ignored-01",
            "fix pagination bug in toy-api",
            "fail",
            False,
            [
                _test(1, 4, page_sig, "1 failed"),
                _command(
                    "python toy_api/build_index.py",
                    "Error: toy-api index builder could not open the stub catalog",
                    exit_code=1,
                ),
                _command("python toy_api/count.py", "rows=10"),
                _command("python toy_api/show.py", "first row is a mug"),
                _command("pwd", "/work/toy-api"),
                _command("python toy_api/version.py", "toy-api 0.0"),
                _message(stop),
            ],
            ["ignored_error"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "ignored-02",
            "add retry to fake-client",
            "fail",
            False,
            [
                _test(1, 2, "TimeoutError: fake-client retry budget exhausted", "1 failed"),
                _command(
                    "python -m fake_client.call",
                    "Error: stub server refused the fake-client hello packet",
                    exit_code=1,
                ),
                _message("Moving on to the readme examples."),
                _command("python -m fake_client.version", "0.0"),
                _command("pwd", "/work/fake-client"),
                _command("python -m fake_client.paths", "src only"),
                _message(stop),
            ],
            ["ignored_error"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "ignored-03",
            "cache lookup in toy-store",
            "pass",
            False,
            [
                _command(
                    "python toy_store/warm.py",
                    "Error: toy-store warmer found no local fixture data",
                    exit_code=1,
                ),
                _command("python toy_store/count.py", "skus=4"),
                _test(0, 2, None, "2 passed"),
            ],
            ["ignored_error"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "ignored-04",
            "validate nickname in sample-form",
            "fail",
            False,
            [
                _test(1, 3, "KeyError: sample-form field nickname", "1 failed"),
                _command(
                    "python sample_form/export.py",
                    "Error: sample-form export could not write the scratch file",
                    exit_code=2,
                ),
                _command("python sample_form/count.py", "fields=4"),
                _command("pwd", "/work/sample-form"),
                _command("python sample_form/version.py", "0.0"),
                _command("python sample_form/show.py", "nickname missing"),
                _message("I will not chase the export."),
            ],
            ["ignored_error"],
        ),
    )

    samples.append(
        _sample(
            rng,
            "notest-01",
            "fix pagination bug in toy-api",
            "fail",
            False,
            [
                _command("python toy_api/show.py", "slice starts at 0"),
                _edit("toy_api/paginate.py", "change the default page length"),
                _message("This should page correctly now."),
            ],
            ["no_test_run"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "notest-02",
            "add retry to fake-client",
            "fail",
            False,
            [
                _command("python -m fake_client.ping", "no answer"),
                _message("The stub is probably down, so I am done."),
            ],
            ["no_test_run"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "notest-03",
            "sort search results in demo-shop",
            "fail",
            False,
            [
                _edit("demo_shop/search.py", "sort by title instead of price"),
                _command("python demo_shop/show.py", "3 hits"),
                _message("Titles look alphabetical."),
            ],
            ["no_test_run"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "notest-04",
            "parse month names in playground-cal",
            "fail",
            False,
            [
                _command("python playground_cal/show.py", "token=March"),
                _command("pwd", "/work/playground-cal"),
                _message("March maps to 3, so this is finished."),
            ],
            ["no_test_run"],
        ),
    )

    # Two failure types in one run.
    samples.append(
        _sample(
            rng,
            "dual-loop-ignored",
            "add retry to fake-client",
            "pass",
            False,
            [
                _command(
                    "python -m fake_client.ping",
                    "Error: connection refused by the fake-client stub",
                    exit_code=1,
                ),
                _command(
                    "python -m fake_client.ping",
                    "Error: connection refused by the fake-client stub",
                    exit_code=1,
                ),
                _command(
                    "python -m fake_client.ping",
                    "Error: connection refused by the fake-client stub",
                    exit_code=1,
                ),
                _message("Trying something else entirely."),
            ],
            ["command_loop", "ignored_error"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "dual-claim-notest",
            "sort search results in demo-shop",
            "fail",
            True,
            [
                _command("python demo_shop/show.py", "3 hits"),
                _edit("demo_shop/search.py", "reverse the hit list"),
                _message("Search is fixed."),
            ],
            ["false_success_claim", "no_test_run"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "dual-edit-giveup",
            "fix pagination bug in toy-api",
            "fail",
            False,
            [
                _test(1, 4, page_sig, "1 failed"),
                _edit("toy_api/paginate.py", "drop the last row of the page"),
                _test(4, 1, page_sig, "4 failed"),
                _command("python toy_api/count.py", "rows=9"),
                _message("I will leave toy-api in this state."),
            ],
            ["edit_then_fail", "gave_up_early"],
        ),
    )
    samples.append(
        _sample(
            rng,
            "dual-symptom-claim",
            "cache lookup in toy-store",
            "fail",
            True,
            [
                _edit("toy_store/cache.py", "print the key on every lookup"),
                _test(1, 2, cache_sig, "1 failed"),
                _edit("toy_store/cache.py", "return [] when the key is missing"),
                _test(1, 2, cache_sig, "1 failed"),
                _edit("toy_store/cache.py", "swallow the lookup and return 0"),
                _message("The toy-store cache bug is fixed."),
            ],
            ["false_success_claim", "symptom_fix"],
        ),
    )

    if len(samples) != 40:
        raise RuntimeError(f"expected 40 samples, built {len(samples)}")
    return samples


def main() -> None:
    samples = build_samples()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(samples, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(samples)} samples to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
