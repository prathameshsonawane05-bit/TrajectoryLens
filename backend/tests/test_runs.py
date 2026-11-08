from collections.abc import Sequence

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models import Step


def step(index: int, step_type: str = "command", **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "index": index,
        "type": step_type,
        "content": "echo hello",
        "file": None,
        "output": "",
        "exit_code": 0,
        "tests_passed": None,
        "tests_failed": None,
        "error_signature": None,
    }
    payload.update(overrides)
    return payload


def trajectory(run_id: str = "run-1", **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "run_id": run_id,
        "task_id": "fix-pagination",
        "model": "fake-model-a",
        "final_status": "fail",
        "agent_claimed_success": False,
        "steps": [step(0)],
    }
    payload.update(overrides)
    return payload


def error_locs(response_json: dict[str, object]) -> list[Sequence[object]]:
    detail = response_json["detail"]
    assert isinstance(detail, list)
    locs: list[Sequence[object]] = []
    for item in detail:
        assert isinstance(item, dict)
        loc = item["loc"]
        msg = item["msg"]
        assert isinstance(loc, list)
        assert isinstance(msg, str)
        assert msg != ""
        locs.append(loc)
    return locs


def assert_names_field(client_response_json: dict[str, object], field: str) -> None:
    locs = error_locs(client_response_json)
    assert any(field in loc for loc in locs), locs


def test_valid_upload(client: TestClient) -> None:
    payload = trajectory(
        steps=[
            step(0, content="pytest -q", output="1 failed", exit_code=1),
            step(1, "edit", content="--- a/app.py", file="app.py", output=""),
            step(
                2,
                "test_run",
                content="pytest -q",
                output="2 passed",
                exit_code=0,
                tests_passed=2,
                tests_failed=0,
            ),
            step(3, "message", content="finished", output="", exit_code=None),
        ],
    )
    response = client.post("/runs", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["run_id"] == "run-1"
    assert [item["index"] for item in body["steps"]] == [0, 1, 2, 3]
    assert body["steps"][1]["file"] == "app.py"
    assert body["steps"][2]["tests_failed"] == 0


def test_round_trip_returns_identical_data(client: TestClient) -> None:
    payload = trajectory(
        run_id="round-trip",
        task_id="add-retry",
        model="fake-model-b",
        final_status="pass",
        agent_claimed_success=True,
        steps=[
            step(0, content="ls", output="src", exit_code=0),
            step(2, "edit", content="diff", file="src/client.py", output="updated"),
            step(
                5,
                "test_run",
                content="pytest -q",
                output="ok",
                exit_code=0,
                tests_passed=4,
                tests_failed=1,
                error_signature="AssertionError: expected 3 got 2",
            ),
        ],
    )
    created = client.post("/runs", json=payload)
    assert created.status_code == 201
    fetched = client.get("/runs/round-trip")
    assert fetched.status_code == 200
    assert fetched.json() == created.json()
    body = fetched.json()
    for key, value in payload.items():
        assert body[key] == value
    assert isinstance(body["created_at"], str)


def test_empty_run_id(client: TestClient) -> None:
    response = client.post("/runs", json=trajectory(run_id=""))
    assert response.status_code == 422
    assert_names_field(response.json(), "run_id")
    assert response.json()["detail"][0]["msg"] == "run_id must be non-empty"


def test_whitespace_run_id(client: TestClient) -> None:
    response = client.post("/runs", json=trajectory(run_id="   "))
    assert response.status_code == 422
    assert_names_field(response.json(), "run_id")
    assert response.json()["detail"][0]["msg"] == "run_id must be non-empty"


def test_missing_steps(client: TestClient) -> None:
    payload = trajectory()
    del payload["steps"]
    response = client.post("/runs", json=payload)
    assert response.status_code == 422
    assert_names_field(response.json(), "steps")


def test_empty_steps(client: TestClient) -> None:
    response = client.post("/runs", json=trajectory(steps=[]))
    assert response.status_code == 422
    assert_names_field(response.json(), "steps")
    assert "at least one step" in response.json()["detail"][0]["msg"]


def test_index_must_start_at_zero(client: TestClient) -> None:
    response = client.post("/runs", json=trajectory(steps=[step(1)]))
    assert response.status_code == 422
    assert_names_field(response.json(), "index")
    assert "start at 0" in response.json()["detail"][0]["msg"]


def test_indexes_must_be_strictly_increasing(client: TestClient) -> None:
    response = client.post("/runs", json=trajectory(steps=[step(0), step(0)]))
    assert response.status_code == 422
    assert_names_field(response.json(), "index")
    assert "strictly increasing" in response.json()["detail"][0]["msg"]


def test_decreasing_index(client: TestClient) -> None:
    response = client.post("/runs", json=trajectory(steps=[step(0), step(2), step(1)]))
    assert response.status_code == 422
    assert_names_field(response.json(), "index")


def test_negative_index(client: TestClient) -> None:
    response = client.post("/runs", json=trajectory(steps=[step(-1)]))
    assert response.status_code == 422
    assert_names_field(response.json(), "index")


def test_test_run_requires_counts(client: TestClient) -> None:
    response = client.post("/runs", json=trajectory(steps=[step(0, "test_run")]))
    assert response.status_code == 422
    locs = error_locs(response.json())
    assert any("tests_passed" in loc for loc in locs)
    assert any("tests_failed" in loc for loc in locs)
    messages = " ".join(item["msg"] for item in response.json()["detail"])
    assert "tests_passed" in messages
    assert "tests_failed" in messages


def test_test_run_requires_tests_failed_when_passed_is_present(client: TestClient) -> None:
    response = client.post(
        "/runs",
        json=trajectory(steps=[step(0, "test_run", tests_passed=1)]),
    )
    assert response.status_code == 422
    assert_names_field(response.json(), "tests_failed")


def test_edit_requires_file(client: TestClient) -> None:
    response = client.post("/runs", json=trajectory(steps=[step(0, "edit")]))
    assert response.status_code == 422
    assert_names_field(response.json(), "file")
    assert "file" in response.json()["detail"][0]["msg"]


def test_edit_rejects_blank_file(client: TestClient) -> None:
    response = client.post("/runs", json=trajectory(steps=[step(0, "edit", file="  ")]))
    assert response.status_code == 422
    assert_names_field(response.json(), "file")


def test_invalid_final_status(client: TestClient) -> None:
    response = client.post("/runs", json=trajectory(final_status="error"))
    assert response.status_code == 422
    assert_names_field(response.json(), "final_status")


def test_invalid_step_type(client: TestClient) -> None:
    response = client.post("/runs", json=trajectory(steps=[step(0, "think")]))
    assert response.status_code == 422
    assert_names_field(response.json(), "type")


def test_missing_content(client: TestClient) -> None:
    incomplete = step(0)
    del incomplete["content"]
    response = client.post("/runs", json=trajectory(steps=[incomplete]))
    assert response.status_code == 422
    assert_names_field(response.json(), "content")


def test_duplicate_run_id(client: TestClient) -> None:
    first = client.post("/runs", json=trajectory(run_id="same"))
    assert first.status_code == 201
    second = client.post("/runs", json=trajectory(run_id="same", task_id="other"))
    assert second.status_code == 409
    assert second.json()["detail"] == "run_id already exists"
    listed = client.get("/runs")
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["task_id"] == "fix-pagination"


def test_filters_and_pagination(client: TestClient) -> None:
    created = [
        trajectory(run_id="run-a", model="fake-model-a", final_status="fail"),
        trajectory(run_id="run-b", model="fake-model-b", final_status="pass"),
        trajectory(run_id="run-c", model="fake-model-a", final_status="pass"),
    ]
    for payload in created:
        assert client.post("/runs", json=payload).status_code == 201

    page = client.get("/runs", params={"limit": 2, "offset": 0})
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert [item["run_id"] for item in body["items"]] == ["run-c", "run-b"]
    assert "steps" not in body["items"][0]

    next_page = client.get("/runs", params={"limit": 2, "offset": 2})
    assert [item["run_id"] for item in next_page.json()["items"]] == ["run-a"]

    by_status = client.get("/runs", params={"status": "pass"})
    assert by_status.json()["total"] == 2
    assert {item["run_id"] for item in by_status.json()["items"]} == {"run-b", "run-c"}

    by_model = client.get("/runs", params={"model": "fake-model-a"})
    assert {item["run_id"] for item in by_model.json()["items"]} == {"run-c", "run-a"}

    both = client.get("/runs", params={"status": "pass", "model": "fake-model-a"})
    assert [item["run_id"] for item in both.json()["items"]] == ["run-c"]

    none = client.get("/runs", params={"model": "missing-model"})
    assert none.status_code == 200
    assert none.json()["items"] == []
    assert none.json()["total"] == 0


def test_invalid_status_filter(client: TestClient) -> None:
    response = client.get("/runs", params={"status": "broken"})
    assert response.status_code == 422
    assert_names_field(response.json(), "status")


def test_invalid_pagination(client: TestClient) -> None:
    limit = client.get("/runs", params={"limit": 0})
    assert limit.status_code == 422
    assert_names_field(limit.json(), "limit")
    offset = client.get("/runs", params={"offset": -1})
    assert offset.status_code == 422
    assert_names_field(offset.json(), "offset")


def test_get_missing_run(client: TestClient) -> None:
    response = client.get("/runs/missing")
    assert response.status_code == 404
    assert response.json()["detail"] == "run not found"


def test_delete_missing_run(client: TestClient) -> None:
    response = client.delete("/runs/missing")
    assert response.status_code == 404
    assert response.json()["detail"] == "run not found"


def test_delete_removes_run_and_steps(client: TestClient) -> None:
    payload = trajectory(
        run_id="doomed",
        steps=[step(0), step(1, "edit", file="app.py")],
    )
    assert client.post("/runs", json=payload).status_code == 201
    kept = trajectory(run_id="kept")
    assert client.post("/runs", json=kept).status_code == 201

    deleted = client.delete("/runs/doomed")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get("/runs/doomed").status_code == 404
    assert client.get("/runs/kept").status_code == 200

    with Session(get_engine()) as session:
        remaining = session.scalar(select(func.count()).select_from(Step))
    assert remaining == 1
