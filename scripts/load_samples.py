"""Load synthetic trajectories through the TrajectoryLens API.

expected_findings is a local label and is not sent to the server.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import cast

DEFAULT_URL = "http://127.0.0.1:8000"
DEFAULT_PATH = Path(__file__).resolve().parent / "samples" / "trajectories.json"


def _request(method: str, url: str, body: dict[str, object] | None = None) -> tuple[int, str]:
    data = None if body is None else json.dumps(body).encode()
    headers = {"content-type": "application/json"} if data is not None else {}
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def load_samples(base_url: str, path: Path) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit(f"{path} does not contain a list of samples")
    loaded = 0
    for item in raw:
        if not isinstance(item, dict):
            raise SystemExit(f"{path} contains a sample that is not an object")
        sample = cast(dict[str, object], item)
        run_id = sample.get("run_id")
        if not isinstance(run_id, str) or run_id == "":
            raise SystemExit("a sample is missing run_id")
        body = {key: value for key, value in sample.items() if key != "expected_findings"}
        status, detail = _request("POST", f"{base_url}/runs", body)
        if status == 409:
            deleted, _ = _request("DELETE", f"{base_url}/runs/{run_id}")
            if deleted != 204:
                raise SystemExit(f"could not replace {run_id}: delete returned {deleted}")
            status, detail = _request("POST", f"{base_url}/runs", body)
            if status != 201:
                raise SystemExit(f"failed to reload {run_id}: {status} {detail}")
            print(f"replaced {run_id}")
        elif status == 201:
            print(f"loaded {run_id}")
        else:
            raise SystemExit(f"failed to load {run_id}: {status} {detail}")
        loaded += 1
    print(f"loaded {loaded} samples")
    _analyze_all(base_url)


def _analyze_all(base_url: str) -> None:
    status, detail = _request("POST", f"{base_url}/analyze-all")
    if status != 200:
        raise SystemExit(f"analyze-all failed: {status} {detail}")
    body = cast(dict[str, object], json.loads(detail))
    print(f"analyzed {body['runs_analyzed']} runs, {body['findings']} findings")
    for name, count in _findings_by_type(base_url).items():
        print(f"{name} {count}")


def _findings_by_type(base_url: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    offset = 0
    total: int | None = None
    while total is None or offset < total:
        status, detail = _request("GET", f"{base_url}/runs?limit=100&offset={offset}")
        if status != 200:
            raise SystemExit(f"could not list runs: {status} {detail}")
        page = cast(dict[str, object], json.loads(detail))
        raw_total = page["total"]
        raw_items = page["items"]
        if not isinstance(raw_total, int) or not isinstance(raw_items, list):
            raise SystemExit("run list response was not usable")
        total = raw_total
        if len(raw_items) == 0:
            break
        for item in raw_items:
            if not isinstance(item, dict):
                raise SystemExit("run list contained a non-object")
            run_id = item.get("run_id")
            if not isinstance(run_id, str):
                raise SystemExit("run list item is missing run_id")
            quoted = urllib.parse.quote(run_id, safe="")
            finding_status, finding_body = _request("GET", f"{base_url}/runs/{quoted}/findings")
            if finding_status != 200:
                raise SystemExit(f"could not read findings for {run_id}: {finding_status}")
            findings = json.loads(finding_body)
            if not isinstance(findings, list):
                raise SystemExit(f"findings for {run_id} were not a list")
            for finding in findings:
                if isinstance(finding, dict) and isinstance(finding.get("type"), str):
                    finding_type = cast(str, finding["type"])
                    counts[finding_type] = counts.get(finding_type, 0) + 1
        offset += len(raw_items)
    return dict(sorted(counts.items()))


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PATH
    try:
        load_samples(base_url.rstrip("/"), path)
    except urllib.error.URLError as exc:
        raise SystemExit(f"could not reach {base_url}: {exc.reason}") from exc


if __name__ == "__main__":
    main()
