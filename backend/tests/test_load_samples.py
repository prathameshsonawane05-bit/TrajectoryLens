"""load_samples analyzes the uploaded runs and prints counts by type."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO = Path(__file__).resolve().parents[2]
_LOADER = _REPO / "scripts" / "load_samples.py"


def _loader() -> ModuleType:
    spec = importlib.util.spec_from_file_location("load_samples", _LOADER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_LOADER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_samples_analyzes_and_prints_type_counts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sample = {
        "run_id": "r1",
        "task_id": "t",
        "model": "m",
        "final_status": "fail",
        "agent_claimed_success": False,
        "expected_findings": ["no_test_run"],
        "steps": [
            {
                "index": 0,
                "type": "message",
                "content": "stopping",
                "file": None,
                "output": "",
                "exit_code": None,
                "tests_passed": None,
                "tests_failed": None,
                "error_signature": None,
            }
        ],
    }
    path = tmp_path / "trajectories.json"
    path.write_text(json.dumps([sample]), encoding="utf-8")
    module = _loader()
    calls: list[tuple[str, str]] = []

    def fake_request(
        method: str,
        url: str,
        body: dict[str, object] | None = None,
    ) -> tuple[int, str]:
        calls.append((method, url))
        if method == "POST" and url.endswith("/runs"):
            assert body is not None
            assert "expected_findings" not in body
            return 201, "{}"
        if method == "POST" and url.endswith("/analyze-all"):
            return 200, json.dumps({"runs_analyzed": 1, "findings": 1})
        if method == "GET" and "/runs?" in url:
            return 200, json.dumps(
                {
                    "items": [
                        {
                            "run_id": "r1",
                            "task_id": "t",
                            "model": "m",
                            "final_status": "fail",
                            "agent_claimed_success": False,
                            "created_at": "2026-01-01T00:00:00Z",
                        }
                    ],
                    "total": 1,
                    "limit": 100,
                    "offset": 0,
                }
            )
        if method == "GET" and url.endswith("/runs/r1/findings"):
            return 200, json.dumps(
                [
                    {
                        "type": "no_test_run",
                        "step_index": 0,
                        "severity": "medium",
                        "explanation": "The run contains no test_run step.",
                    }
                ]
            )
        raise AssertionError(f"unexpected request {method} {url}")

    monkeypatch.setattr(module, "_request", fake_request)
    module.load_samples("http://127.0.0.1:8000", path)
    output = capsys.readouterr().out
    assert "loaded r1" in output
    assert "analyzed 1 runs, 1 findings" in output
    assert "no_test_run 1" in output
    post_urls = [url for method, url in calls if method == "POST"]
    assert post_urls[-1].endswith("/analyze-all")
    assert any(url.endswith("/runs") for url in post_urls[:-1])
