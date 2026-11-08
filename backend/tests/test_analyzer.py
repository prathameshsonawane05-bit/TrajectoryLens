from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analyzer import run_analysis
from app.analyzer.registry import Finding
from app.db import get_engine
from app.models import Finding as StoredFinding
from app.models import Run, Step


def _step(
    index: int,
    step_type: str,
    *,
    content: str = "",
    file: str | None = None,
    output: str = "",
    exit_code: int | None = 0,
    tests_passed: int | None = None,
    tests_failed: int | None = None,
    error_signature: str | None = None,
) -> Step:
    return Step(
        index=index,
        type=step_type,
        content=content,
        file=file,
        output=output,
        exit_code=exit_code,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        error_signature=error_signature,
    )


def command(
    index: int,
    content: str,
    output: str = "",
    exit_code: int | None = 0,
    *,
    file: str | None = None,
    error_signature: str | None = None,
) -> Step:
    return _step(
        index,
        "command",
        content=content,
        file=file,
        output=output,
        exit_code=exit_code,
        error_signature=error_signature,
    )


def edit(index: int, file: str, content: str = "diff") -> Step:
    return _step(index, "edit", content=content, file=file, exit_code=0)


def make_test_run(
    index: int,
    tests_failed: int,
    *,
    tests_passed: int = 1,
    error_signature: str | None = None,
    output: str = "",
) -> Step:
    return _step(
        index,
        "test_run",
        content="pytest -q",
        output=output,
        exit_code=0 if tests_failed == 0 else 1,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        error_signature=error_signature,
    )


def message(index: int, content: str) -> Step:
    return _step(index, "message", content=content, output="", exit_code=None)


def make_run(
    steps: list[Step],
    *,
    final_status: str = "fail",
    agent_claimed_success: bool = False,
) -> Run:
    return Run(
        run_id="local",
        task_id="task",
        model="model",
        final_status=final_status,
        agent_claimed_success=agent_claimed_success,
        created_at=datetime.now(UTC),
        steps=steps,
    )


def of_type(findings: list[Finding], finding_type: str) -> list[Finding]:
    return [finding for finding in findings if finding.type == finding_type]


def test_rules_are_registered() -> None:
    from app.analyzer.rules import registered_rules

    assert [func.__name__ for func in registered_rules()] == [
        "command_loop",
        "edit_then_fail",
        "false_success_claim",
        "gave_up_early",
        "symptom_fix",
        "ignored_error",
        "no_test_run",
    ]


def test_empty_run_produces_no_findings() -> None:
    assert run_analysis(make_run([])) == []


def test_command_loop_positive() -> None:
    run = make_run(
        [
            command(0, "pytest -q", "1 failed"),
            command(1, "pytest -q", "1 failed"),
            command(2, "pytest -q", "1 failed"),
        ],
        final_status="pass",
    )
    found = of_type(run_analysis(run), "command_loop")
    assert len(found) == 1
    assert found[0].step_index == 2
    assert found[0].severity == "medium"
    assert "pytest -q" in found[0].explanation
    assert "third" in found[0].explanation


def test_command_loop_negative_different_output() -> None:
    run = make_run(
        [
            command(0, "pytest -q", "all tests passed"),
            command(1, "pytest -q", "ModuleNotFoundError: no module named foo"),
            command(2, "pytest -q", "SyntaxError: unexpected indent"),
        ],
        final_status="pass",
    )
    assert of_type(run_analysis(run), "command_loop") == []


def test_command_loop_edge_thresholds() -> None:
    two = make_run(
        [command(0, "pytest -q", "1 failed"), command(1, "pytest -q", "1 failed")],
        final_status="pass",
    )
    assert of_type(run_analysis(two), "command_loop") == []

    five = make_run(
        [command(index, "pytest -q", "1 failed") for index in range(5)],
        final_status="pass",
    )
    found = of_type(run_analysis(five), "command_loop")
    assert len(found) == 1
    assert found[0].step_index == 2
    assert found[0].severity == "high"

    # Positions 0 and 6 are 7 steps apart, outside a 6-step window.
    spread = make_run(
        [
            command(0, "pytest -q", "1 failed"),
            command(1, "ls", ""),
            command(2, "pwd", ""),
            command(3, "true", ""),
            command(4, "false", "", exit_code=0),
            command(5, "echo hi", "hi"),
            command(6, "pytest -q", "1 failed"),
            command(7, "pytest -q", "1 failed"),
        ],
        final_status="pass",
    )
    assert of_type(run_analysis(spread), "command_loop") == []


def test_command_loop_ignores_dot_slash_and_backslashes() -> None:
    run = make_run(
        [
            command(0, "python src/cart.py --check", "cart check: 4 lines"),
            command(1, "python ./src/cart.py --check", "Cart check: 4 lines"),
            command(2, "python src\\cart.py --check", "CART CHECK: 4 lines"),
        ],
        final_status="pass",
    )
    found = of_type(run_analysis(run), "command_loop")
    assert len(found) == 1
    assert found[0].step_index == 2


def test_command_loop_within_window() -> None:
    run = make_run(
        [
            command(0, "pytest -q", "Error: connection refused at port 5432"),
            edit(1, "app.py"),
            command(2, "pytest -q", "Error: connection refused at port 5433"),
            message(3, "retrying"),
            command(4, "pytest -q", "Error: connection refused at port 5432"),
        ],
        final_status="pass",
    )
    found = of_type(run_analysis(run), "command_loop")
    assert len(found) == 1
    assert found[0].step_index == 4
    assert found[0].severity == "medium"


def test_edit_then_fail_positive() -> None:
    run = make_run(
        [
            make_test_run(0, tests_failed=1, error_signature="AssertionError: expected 3 got 2"),
            edit(1, "app.py"),
            command(2, "sed -n 1p app.py", "class App"),
            make_test_run(3, tests_failed=3, error_signature="AssertionError: expected 3 got 2"),
        ],
    )
    found = of_type(run_analysis(run), "edit_then_fail")
    assert len(found) == 1
    assert found[0].step_index == 3
    assert found[0].severity == "medium"
    assert "app.py" in found[0].explanation
    assert "1" in found[0].explanation and "3" in found[0].explanation


def test_edit_then_fail_negative_without_edit() -> None:
    run = make_run(
        [
            make_test_run(0, tests_failed=1),
            command(1, "ls", "app.py"),
            make_test_run(2, tests_failed=4),
        ],
    )
    assert of_type(run_analysis(run), "edit_then_fail") == []


def test_edit_then_fail_edge_equal_failures() -> None:
    run = make_run(
        [
            make_test_run(0, tests_failed=2),
            edit(1, "app.py"),
            make_test_run(2, tests_failed=2),
        ],
    )
    assert of_type(run_analysis(run), "edit_then_fail") == []
    short = make_run([edit(0, "app.py")], final_status="pass")
    assert of_type(run_analysis(short), "edit_then_fail") == []


def test_false_success_claim_positive() -> None:
    run = make_run(
        [make_test_run(0, tests_failed=0, tests_passed=2), message(1, "done")],
        agent_claimed_success=True,
    )
    found = of_type(run_analysis(run), "false_success_claim")
    assert len(found) == 1
    assert found[0].step_index == 1
    assert found[0].severity == "high"
    assert "claimed success" in found[0].explanation


def test_false_success_claim_negative() -> None:
    run = make_run(
        [message(0, "done")],
        final_status="pass",
        agent_claimed_success=True,
    )
    assert of_type(run_analysis(run), "false_success_claim") == []


def test_false_success_claim_edge_empty() -> None:
    run = make_run([], agent_claimed_success=True)
    assert of_type(run_analysis(run), "false_success_claim") == []


def test_gave_up_early_positive() -> None:
    run = make_run(
        [
            make_test_run(0, tests_failed=2, error_signature="AssertionError: expected 3 got 2"),
            command(1, "ls", "app.py"),
            command(2, "pwd", "/tmp"),
            command(3, "true", ""),
            message(4, "stopping"),
        ],
    )
    found = of_type(run_analysis(run), "gave_up_early")
    assert len(found) == 1
    assert found[0].step_index == 4
    assert found[0].severity == "medium"
    assert "only 4 steps" in found[0].explanation


def test_gave_up_early_negative_edit_in_last_steps() -> None:
    run = make_run(
        [
            make_test_run(0, tests_failed=1),
            command(1, "ls", ""),
            command(2, "pwd", ""),
            edit(3, "app.py"),
        ],
    )
    assert of_type(run_analysis(run), "gave_up_early") == []


def test_gave_up_early_edge_exactly_five_steps_after() -> None:
    run = make_run(
        [make_test_run(0, tests_failed=1)] + [command(index, "ls", "") for index in range(1, 6)],
    )
    assert of_type(run_analysis(run), "gave_up_early") == []


def test_symptom_fix_positive() -> None:
    signature = "AssertionError: expected 3 got 2"
    run = make_run(
        [
            edit(0, "app.py"),
            make_test_run(1, tests_failed=1, error_signature=signature),
            edit(2, "app.py"),
            make_test_run(3, tests_failed=1, error_signature=signature),
            edit(4, "app.py"),
        ],
    )
    found = of_type(run_analysis(run), "symptom_fix")
    assert len(found) == 1
    assert found[0].step_index == 4
    assert found[0].severity == "high"
    assert "app.py" in found[0].explanation
    assert signature in found[0].explanation


def test_symptom_fix_negative_signature_changes() -> None:
    run = make_run(
        [
            edit(0, "app.py"),
            make_test_run(1, tests_failed=1, error_signature="NameError: foo"),
            edit(2, "app.py"),
            make_test_run(3, tests_failed=1, error_signature="TypeError: bar"),
            edit(4, "app.py"),
        ],
    )
    assert of_type(run_analysis(run), "symptom_fix") == []


def test_symptom_fix_edge_two_edits() -> None:
    signature = "AssertionError: expected 3 got 2"
    run = make_run(
        [
            edit(0, "app.py"),
            make_test_run(1, tests_failed=1, error_signature=signature),
            edit(2, "app.py"),
        ],
    )
    assert of_type(run_analysis(run), "symptom_fix") == []


def test_ignored_error_positive() -> None:
    run = make_run(
        [
            command(0, "python app.py", "No such file: app.py", exit_code=1),
            command(1, "ls", "readme"),
        ],
        final_status="pass",
    )
    found = of_type(run_analysis(run), "ignored_error")
    assert len(found) == 1
    assert found[0].step_index == 1
    assert found[0].severity == "low"
    assert "exited 1" in found[0].explanation


def test_ignored_error_negative_message_quotes_error() -> None:
    run = make_run(
        [
            command(0, "python app.py", "No such file: app.py", exit_code=1),
            message(1, "The traceback says No such file: app.py"),
        ],
        final_status="pass",
    )
    assert of_type(run_analysis(run), "ignored_error") == []


def test_ignored_error_edit_of_command_path_is_not_ignored() -> None:
    run = make_run(
        [
            command(
                0,
                "python toy_api/paginate.py",
                "Traceback (most recent call last):\n"
                "ModuleNotFoundError: No module named 'toy_api'",
                exit_code=1,
            ),
            edit(1, "./toy_api/paginate.py", "export the paginate function"),
        ],
        final_status="pass",
    )
    assert of_type(run_analysis(run), "ignored_error") == []


def test_ignored_error_message_naming_exception_is_not_ignored() -> None:
    run = make_run(
        [
            command(
                0,
                "python playground_cal/parse.py",
                "ImportError: cannot import name 'month_number' from 'playground_cal.parse'",
                exit_code=1,
            ),
            message(1, "The ImportError for month_number is a missing helper."),
        ],
        final_status="pass",
    )
    assert of_type(run_analysis(run), "ignored_error") == []


def test_symptom_fix_treats_absolute_and_relative_as_the_same_file() -> None:
    signature = "AssertionError: total was 9"
    run = make_run(
        [
            edit(0, "cart/total.py"),
            make_test_run(1, tests_failed=1, error_signature=signature),
            edit(2, "/tmp/work/cart/total.py"),
            make_test_run(3, tests_failed=1, error_signature=signature),
            edit(4, "cart/total.py"),
        ],
    )
    found = of_type(run_analysis(run), "symptom_fix")
    assert len(found) == 1
    assert found[0].step_index == 4


def test_ignored_error_edit_of_absolute_path_is_not_ignored() -> None:
    run = make_run(
        [
            command(
                0,
                "python cart/total.py",
                "SyntaxError: invalid syntax",
                exit_code=1,
            ),
            edit(1, "/tmp/work/cart/total.py", "close the parenthesis"),
        ],
        final_status="pass",
    )
    assert of_type(run_analysis(run), "ignored_error") == []


def test_symptom_fix_treats_dot_slash_as_the_same_file() -> None:
    signature = "AssertionError: expected 3 got 2"
    run = make_run(
        [
            edit(0, "./app.py"),
            make_test_run(1, tests_failed=1, error_signature=signature),
            edit(2, "app.py"),
            make_test_run(3, tests_failed=1, error_signature=signature),
            edit(4, "./app.py"),
        ],
    )
    found = of_type(run_analysis(run), "symptom_fix")
    assert len(found) == 1
    assert found[0].step_index == 4


def test_ignored_error_edge_failure_is_last_step() -> None:
    run = make_run(
        [command(0, "python app.py", "No such file: app.py", exit_code=1)],
        final_status="pass",
    )
    assert of_type(run_analysis(run), "ignored_error") == []


def test_no_test_run_positive() -> None:
    run = make_run([command(0, "ls", "app.py"), message(1, "I think this works")])
    found = of_type(run_analysis(run), "no_test_run")
    assert len(found) == 1
    assert found[0].step_index == 1
    assert found[0].severity == "medium"
    assert "no test_run" in found[0].explanation


def test_no_test_run_negative() -> None:
    run = make_run([command(0, "ls", ""), make_test_run(1, tests_failed=1)])
    assert of_type(run_analysis(run), "no_test_run") == []


def test_no_test_run_edge_empty() -> None:
    assert of_type(run_analysis(make_run([])), "no_test_run") == []


def test_findings_are_sorted_by_step_index() -> None:
    run = make_run(
        [
            command(0, "python app.py", "No such file: app.py", exit_code=1),
            command(1, "ls", "readme"),
            message(2, "stopping"),
        ],
    )
    found = run_analysis(run)
    indexes = [item.step_index for item in found]
    assert indexes == sorted(indexes)
    assert [item.type for item in found] == ["ignored_error", "no_test_run"]


def test_analyze_is_idempotent(client: TestClient) -> None:
    payload = {
        "run_id": "loop-1",
        "task_id": "retry",
        "model": "fake-model-a",
        "final_status": "pass",
        "agent_claimed_success": False,
        "steps": [
            {
                "index": index,
                "type": "command",
                "content": "pytest -q",
                "file": None,
                "output": "1 failed",
                "exit_code": 0,
                "tests_passed": None,
                "tests_failed": None,
                "error_signature": None,
            }
            for index in range(3)
        ],
    }
    assert client.post("/runs", json=payload).status_code == 201
    assert client.get("/runs/loop-1/findings").json() == []

    first = client.post("/runs/loop-1/analyze")
    second = client.post("/runs/loop-1/analyze")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert client.get("/runs/loop-1/findings").json() == first.json()
    assert len(first.json()) == 1
    assert first.json()[0]["type"] == "command_loop"

    with Session(get_engine()) as session:
        stored = session.scalar(select(func.count()).select_from(StoredFinding))
    assert stored == 1


def test_analyze_missing_run(client: TestClient) -> None:
    response = client.post("/runs/missing/analyze")
    assert response.status_code == 404
    assert response.json()["detail"] == "run not found"
    listed = client.get("/runs/missing/findings")
    assert listed.status_code == 404
    assert listed.json()["detail"] == "run not found"


def test_delete_run_removes_findings(client: TestClient) -> None:
    payload = {
        "run_id": "doomed-findings",
        "task_id": "retry",
        "model": "fake-model-a",
        "final_status": "fail",
        "agent_claimed_success": True,
        "steps": [
            {
                "index": 0,
                "type": "message",
                "content": "done",
                "file": None,
                "output": "",
                "exit_code": None,
                "tests_passed": None,
                "tests_failed": None,
                "error_signature": None,
            }
        ],
    }
    assert client.post("/runs", json=payload).status_code == 201
    analyzed = client.post("/runs/doomed-findings/analyze")
    assert analyzed.status_code == 200
    assert {item["type"] for item in analyzed.json()} >= {"false_success_claim", "no_test_run"}
    assert client.delete("/runs/doomed-findings").status_code == 204
    with Session(get_engine()) as session:
        stored = session.scalar(select(func.count()).select_from(StoredFinding))
    assert stored == 0
