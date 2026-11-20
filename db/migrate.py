"""Apply the repository's single ordered SQL migration stream."""

import argparse
import hashlib
import os
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).parent / "migrations"


def migrate(database_url: str) -> list[str]:
    if not database_url:
        raise ValueError("DATABASE_URL is required")
    applied = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):
            sql = path.read_text(encoding="utf-8")
            digest = hashlib.sha256(sql.encode()).hexdigest()
            with conn.transaction():
                conn.execute("select pg_advisory_xact_lock(854226, 1)")
                conn.execute("""create table if not exists schema_migrations (
                    name text primary key,
                    sha256 text not null,
                    applied_at timestamptz not null default now()
                )""")
                row = conn.execute(
                    "select sha256 from schema_migrations where name = %s", (path.name,)
                ).fetchone()
                if row:
                    if row[0] != digest:
                        raise RuntimeError(f"Migration changed after application: {path.name}")
                    continue
                conn.execute(sql)
                conn.execute(
                    "insert into schema_migrations (name, sha256) values (%s, %s)",
                    (path.name, digest),
                )
                applied.append(path.name)
    return applied


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Use TEST_DATABASE_URL only")
    args = parser.parse_args()
    key = "TEST_DATABASE_URL" if args.test else "DATABASE_URL"
    print("Applied:", migrate(os.environ.get(key, "")))
