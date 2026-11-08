import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent.parent / "trajectorylens.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DATABASE_PATH}"

_engines: dict[str, Engine] = {}


class Base(DeclarativeBase):
    pass


def get_database_url() -> str:
    return os.environ.get("TRAJECTORYLENS_DATABASE_URL", DEFAULT_DATABASE_URL)


def get_engine() -> Engine:
    url = get_database_url()
    engine = _engines.get(url)
    if engine is None:
        engine = create_engine(url, connect_args={"check_same_thread": False})
        _engines[url] = engine
    return engine


def dispose_engine(url: str | None = None) -> None:
    key = get_database_url() if url is None else url
    engine = _engines.pop(key, None)
    if engine is not None:
        engine.dispose()


def init_db() -> None:
    # Import models so their tables are registered on Base.metadata.
    from app import models

    _ = models.Run
    Base.metadata.create_all(get_engine())


def get_db() -> Iterator[Session]:
    session = Session(get_engine())
    try:
        yield session
    finally:
        session.close()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    if type(dbapi_connection).__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
