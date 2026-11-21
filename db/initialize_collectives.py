"""Idempotently ensure the two operational collectives for a local pilot.

Run only against the local Docker database:
    docker compose exec api python -m db.initialize_collectives --local-only
"""

import argparse
import os
from uuid import UUID

from db.connection import open_connection
from db.promote_admin import require_local_database


def initialize(database_url: str, pilot_id: UUID, *, create_pilot: bool = False) -> int:
    require_local_database(database_url)
    with open_connection(database_url) as conn, conn.transaction():
        if create_pilot:
            conn.execute("""
                insert into pilots (id, name, city)
                values (%s, 'Villas de San Pablo', 'Barranquilla')
                on conflict do nothing
            """, (pilot_id,))
        exists = conn.execute("select 1 from pilots where id = %s and active", (pilot_id,)).fetchone()
        if exists is None:
            raise SystemExit("The configured active pilot does not exist; no data was inserted")
        rows = conn.execute("""
            insert into collectives (pilot_id, flow)
            values (%s, 'huerta'), (%s, 'reciclaje')
            on conflict (pilot_id, flow) do nothing
            returning flow
        """, (pilot_id, pilot_id)).fetchall()
        return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-only", action="store_true", required=True)
    parser.add_argument("--create-pilot", action="store_true", help="Create the configured local pilot if missing")
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL", "")
    pilot_id = os.environ.get("ECO_PILOT_ID", "")
    if not database_url or not pilot_id:
        raise SystemExit("DATABASE_URL and ECO_PILOT_ID must be configured")
    try:
        created = initialize(database_url, UUID(pilot_id), create_pilot=args.create_pilot)
    except ValueError:
        parser.error("Revisa DATABASE_URL y ECO_PILOT_ID.")
    print(f"Local pilot collectives are ready; {created} collective(s) created.")


if __name__ == "__main__":
    main()
