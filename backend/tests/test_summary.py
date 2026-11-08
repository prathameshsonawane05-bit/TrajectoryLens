"""GET /summary counts runs and stored findings."""

from fastapi.testclient import TestClient


def _step(
    index: int,
    step_type: str,
    content: str = "",
    *,
    file: str | None = None,
    output: str = "",
    exit_code: int | None = 0,
    tests_passed: int | None = None,
    tests_failed: int | None = None,
    error_signature: str | None = None,
) -> dict[str, object]:
    if step_type == "message":
        exit_code = None
    return {
        "index": index,
        "type": step_type,
        "content": content,
        "file": file,
        "output": output,
        "exit_code": exit_code,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "error_signature": error_signature,
    }


def _run(
    run_id: str,
    model: str,
    status: str,
    steps: list[dict[str, object]],
    *,
    claimed: bool = False,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "task_id": "task",
        "model": model,
        "final_status": status,
        "agent_claimed_success": claimed,
        "steps": steps,
    }


def _store(client: TestClient, payload: dict[str, object]) -> None:
    response = client.post("/runs", json=payload)
    assert response.status_code == 201


def test_summary_is_empty(client: TestClient) -> None:
    response = client.get("/summary")
    assert response.status_code == 200
    assert response.json() == {
        "pass_count": 0,
        "fail_count": 0,
        "by_type": [],
        "by_model": [],
        "top_failure_types": [],
    }


def test_summary_counts_types_models_and_top_five(client: TestClient) -> None:
    loop = [
        _step(index, "command", "pytest -q", output="1 failed")
        for index in range(3)
    ]
    _store(client, _run("loop-a", "model-a", "pass", loop))
    _store(client, _run("loop-b", "model-a", "pass", loop))
    _store(
        client,
        _run(
            "edit-fail",
            "model-b",
            "fail",
            [
                _step(0, "test_run", tests_passed=4, tests_failed=1, error_signature="boom"),
                _step(1, "edit", "change", file="app.py"),
                _step(2, "test_run", tests_passed=3, tests_failed=2, error_signature="boom"),
                _step(3, "message", "still looking"),
                _step(4, "message", "still looking"),
                _step(5, "message", "still looking"),
                _step(6, "message", "still looking"),
            ],
        ),
    )
    _store(
        client,
        _run(
            "claim",
            "model-b",
            "fail",
            [
                _step(0, "test_run", tests_passed=1, tests_failed=0),
                *[_step(index, "message", "maybe") for index in range(1, 6)],
            ],
            claimed=True,
        ),
    )
    _store(
        client,
        _run(
            "give-up",
            "model-b",
            "fail",
            [
                _step(0, "test_run", tests_passed=1, tests_failed=2, error_signature="boom"),
                _step(1, "message", "reading"),
                _step(2, "message", "thinking"),
                _step(3, "message", "tomorrow"),
            ],
        ),
    )
    _store(
        client,
        _run(
            "symptom",
            "model-c",
            "fail",
            [
                _step(0, "edit", "log", file="app.py"),
                _step(1, "test_run", tests_passed=1, tests_failed=1, error_signature="same"),
                _step(2, "edit", "log again", file="app.py"),
                _step(3, "test_run", tests_passed=1, tests_failed=1, error_signature="same"),
                _step(4, "edit", "log once more", file="app.py"),
            ],
        ),
    )
    _store(
        client,
        _run(
            "ignored",
            "model-c",
            "pass",
            [
                _step(
                    0,
                    "command",
                    "ls missing.txt",
                    output="No such file: missing.txt",
                    exit_code=1,
                ),
                _step(1, "command", "echo ok", output="ok"),
                _step(2, "test_run", tests_passed=1, tests_failed=0),
            ],
        ),
    )
    _store(
        client,
        _run("no-test", "model-c", "fail", [_step(0, "message", "stopping")]),
    )
    _store(client, _run("quiet", "model-d", "pass", [_step(0, "message", "all good")]))

    response = client.get("/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["pass_count"] == 4
    assert body["fail_count"] == 5
    assert body["by_type"] == [
        {"type": "command_loop", "count": 2},
        {"type": "edit_then_fail", "count": 1},
        {"type": "false_success_claim", "count": 1},
        {"type": "gave_up_early", "count": 1},
        {"type": "ignored_error", "count": 1},
        {"type": "no_test_run", "count": 1},
        {"type": "symptom_fix", "count": 1},
    ]
    assert body["top_failure_types"] == body["by_type"][:5]
    assert body["by_model"] == [
        {"model": "model-b", "count": 3},
        {"model": "model-c", "count": 3},
        {"model": "model-a", "count": 2},
        {"model": "model-d", "count": 0},
    ]
