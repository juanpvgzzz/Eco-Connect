"""Prepare the administrator and both coordinator panels on a local pilot."""

import argparse
from getpass import getpass
import os
import secrets
import sys
from uuid import UUID, uuid4

from backend.app.accounts.models import AccountKind, AccountRecord, AccountRole
from backend.app.accounts.ports import DuplicateNationalId
from backend.app.accounts.postgres_store import PostgresAccountStore
from backend.app.accounts.service import AccountError, AccountService
from backend.app.errors import InvalidInput
from db.connection import open_connection
from db.initialize_collectives import initialize
from db.provision_admin import provision
from db.promote_admin import require_local_database


PANELS = (
    ("huerta", "Coordinación de Huerteros"),
    ("reciclaje", "Coordinación de Recicladores"),
)


def new_credentials() -> tuple[str, str]:
    document = str(10**14 + secrets.randbelow(9 * 10**14))
    pin = f"{secrets.randbelow(10**12):012d}"
    return document, pin


def show_access(label: str, document: str, pin: str | None = None) -> None:
    access = f"PIN nuevo: {pin}" if pin is not None else "usa el PIN existente"
    print(f"{label} | Cédula: {document} | {access}", flush=True)


def prepare(database_url: str, pilot_id: UUID) -> None:
    require_local_database(database_url)
    initialize(database_url, pilot_id, create_pilot=True)
    store = PostgresAccountStore(database_url, pilot_id)
    service = AccountService(store)
    with open_connection(database_url) as conn, conn.transaction():
        # Serializa ejecuciones de este comando sobre la misma base local.
        conn.execute("select pg_advisory_xact_lock(854226, 3)")
        admins = conn.execute("""
            select document_number from users
            where pilot_id = %s and role = 'admin' and active
              and document_number is not null
            order by full_name, id
        """, (pilot_id,)).fetchall()
        for account in admins:
            show_access("Administración", account["document_number"])

        missing = []
        for flow, label in PANELS:
            accounts = conn.execute("""
                select u.document_number from users u
                join collectives c on c.id = u.collective_id and c.pilot_id = u.pilot_id
                where u.pilot_id = %s and u.role = 'lider' and u.active
                  and c.flow = %s and u.document_number is not null
                order by u.full_name, u.id
            """, (pilot_id, flow)).fetchall()
            if accounts:
                for account in accounts:
                    show_access(label, account["document_number"])
            else:
                missing.append((flow, label))

        if admins:
            if not missing:
                return
            document = input("Cédula del administrador que autoriza las cuentas: ").strip()
            pin = getpass("PIN del administrador: ")
        else:
            document, pin = new_credentials()
            provision(database_url, pilot_id, document, "Administración local", pin)
            show_access("Administración", document, pin)

        login = service.login(document, pin)
        try:
            collectives = {row["flow"]: row["id"] for row in service.admin_collectives(actor=login.identity)}
            for flow, label in missing:
                collective_id = collectives[flow]
                document, pin = new_credentials()
                account = store.create_account(AccountRecord(
                    id=str(uuid4()), national_id=document, full_name=f"{label} Local",
                    address="", phone="", kind=AccountKind.HOUSEHOLD,
                    pin_hash=service.password_hash.hash(pin), role=AccountRole.RESIDENT,
                ))
                service.set_authorization(
                    actor=login.identity, account_id=account.id, role=AccountRole.LEADER,
                    collective_id=collective_id, pilot_enabled=False,
                )
                show_access(label, document, pin)
        finally:
            service.logout(login.access_token)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-only", action="store_true", required=True)
    parser.parse_args()
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        parser.error("Ejecuta el comando en una terminal interactiva.")
    try:
        prepare(os.environ["DATABASE_URL"], UUID(os.environ["ECO_PILOT_ID"]))
    except (KeyError, ValueError):
        parser.error("Revisa DATABASE_URL y ECO_PILOT_ID.")
    except AccountError:
        parser.error("Se requiere una sesión válida de administrador para autorizar las cuentas.")
    except (DuplicateNationalId, InvalidInput):
        parser.error("No se pudo completar el alta. Revisa los accesos que aparecieron en la terminal.")


if __name__ == "__main__":
    main()
