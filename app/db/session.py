from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from app.config import get_settings

SCHEMA = Path(__file__).with_name("schema.sql")


@contextmanager
def connect() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as conn:
        register_vector(conn)
        yield conn


def init_schema() -> None:
    with psycopg.connect(get_settings().database_url, autocommit=True) as conn:
        conn.execute(SCHEMA.read_text(encoding="utf-8"))  # type: ignore[call-overload]
