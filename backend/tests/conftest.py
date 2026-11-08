from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import dispose_engine
from app.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    database_path = tmp_path / "test.db"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("TRAJECTORYLENS_DATABASE_URL", database_url)
    with TestClient(app) as test_client:
        yield test_client
    dispose_engine(database_url)
