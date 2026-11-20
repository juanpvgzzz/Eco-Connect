"""Shared PostgreSQL connection factory; callers supply their configured URL."""

import psycopg
from psycopg.rows import dict_row


def open_connection(database_url: str) -> psycopg.Connection:
    if not database_url:
        raise ValueError("database_url is required")
    # Explicit conn.transaction() blocks own commit/rollback boundaries.
    return psycopg.connect(database_url, autocommit=True, row_factory=dict_row)
