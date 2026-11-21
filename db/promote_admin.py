"""Promote an existing account to the first administrator of a local pilot.

Example (local Compose only):
    docker compose exec -e ECO_ALLOW_ADMIN_BOOTSTRAP=true api python -m db.promote_admin --local-only --national-id 123456789

The target account must already exist. This command never creates or resets a PIN.
"""

import argparse
from contextlib import contextmanager
import os

from psycopg.conninfo import conninfo_to_dict

from backend.app.accounts.service import normalize_national_id
from db.connection import open_connection


LOCAL_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}


def require_local_database(database_url: str) -> None:
    params = conninfo_to_dict(database_url)
    if (params.get("host") not in LOCAL_HOSTS or params.get("hostaddr") or params.get("service")
            or os.environ.get("PGHOSTADDR") or os.environ.get("PGSERVICE")):
        raise SystemExit("El comando requiere una base local en el host db o localhost.")


@contextmanager
def first_admin_transaction(database_url: str, pilot_id: str):
    require_local_database(database_url)
    with open_connection(database_url) as conn, conn.transaction():
        conn.execute("select pg_advisory_xact_lock(854226, 2)")
        if conn.execute("select 1 from pilots where id = %s and active", (pilot_id,)).fetchone() is None:
            raise SystemExit("El piloto configurado debe existir y estar activo.")
        if conn.execute("""
            select 1 from users where pilot_id = %s and role = 'admin' and active
        """, (pilot_id,)).fetchone():
            raise SystemExit("Ya existe un administrador activo en este piloto.")
        yield conn


def promote(database_url: str, pilot_id: str, national_id: str) -> None:
    normalized_id = normalize_national_id(national_id)
    with first_admin_transaction(database_url, pilot_id) as conn:
        account = conn.execute("""
            select id, role, password_hash from users
            where pilot_id = %s and document_number = %s and active for update
        """, (pilot_id, normalized_id)).fetchone()
        if account is None:
            raise SystemExit("Create and verify the account through the normal registration endpoint first")
        if account["role"] != "cliente":
            raise SystemExit("Only an existing resident or business account can receive initial administration")
        if not account["password_hash"].startswith("$argon2"):
            raise SystemExit("Registra una cuenta con un PIN válido antes de promoverla.")
        updated = conn.execute("""
            update users set role = 'admin', collective_id = null, pilot_enabled = false
            where id = %s and pilot_id = %s and active returning id
        """, (account["id"], pilot_id)).fetchone()
        conn.execute("""
            insert into account_authorization_audit
                (pilot_id, actor_id, target_id, action, previous_role, new_role,
                 previous_collective_id, new_collective_id)
            values (%s, null, %s, 'bootstrap_first_admin', 'cliente', 'admin', null, null)
        """, (pilot_id, updated["id"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-only", action="store_true", required=True)
    parser.add_argument("--national-id", required=True)
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL", "")
    pilot_id = os.environ.get("ECO_PILOT_ID", "")
    if not database_url or not pilot_id:
        raise SystemExit("DATABASE_URL and ECO_PILOT_ID must be configured")
    if os.environ.get("ECO_ALLOW_ADMIN_BOOTSTRAP") != "true":
        raise SystemExit("Set ECO_ALLOW_ADMIN_BOOTSTRAP=true explicitly for this local one-time command")
    promote(database_url, pilot_id, args.national_id)
    print("First administrator enabled for the local pilot. No PIN or token was changed.")


if __name__ == "__main__":
    main()
