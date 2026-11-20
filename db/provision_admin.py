"""Create an administrator for the configured pilot from a trusted terminal."""

import argparse
from getpass import getpass
import os
from uuid import UUID, uuid4

from pwdlib import PasswordHash

from backend.app.accounts.models import AccountKind, AccountRecord, AccountRole
from backend.app.accounts.ports import DuplicateNationalId
from backend.app.accounts.postgres_store import PostgresAccountStore
from backend.app.accounts.service import normalize_national_id, validate_pin
from backend.app.errors import InvalidInput
from db.connection import open_connection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("national_id")
    parser.add_argument("full_name")
    args = parser.parse_args()
    try:
        national_id = normalize_national_id(args.national_id)
        pin = getpass("PIN: ")
        validate_pin(pin)
        if pin != getpass("Confirmar PIN: "):
            parser.error("Los PIN deben coincidir")
        pilot_id = UUID(os.environ["ECO_PILOT_ID"])
        database_url = os.environ["DATABASE_URL"]
        full_name = args.full_name.strip()
        if not full_name:
            parser.error("Ingresa el nombre del administrador")
        with open_connection(database_url) as conn:
            if conn.execute("select 1 from pilots where id = %s and active", (pilot_id,)).fetchone() is None:
                parser.error("El piloto configurado debe existir y estar activo")
        store = PostgresAccountStore(database_url, pilot_id)
        account = store.create_account(AccountRecord(
            id=str(uuid4()), national_id=national_id, full_name=full_name, address="", phone="",
            kind=AccountKind.HOUSEHOLD, pin_hash=PasswordHash.recommended().hash(pin),
            role=AccountRole.ADMIN,
        ))
    except (KeyError, ValueError, InvalidInput, DuplicateNationalId):
        parser.error("Revisa la configuración, el documento único y el formato del PIN o del piloto")
    print(f"Administrador creado: {account.id}")


if __name__ == "__main__":
    main()
