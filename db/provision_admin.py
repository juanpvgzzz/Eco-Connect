"""Create an administrator for the configured pilot from a trusted terminal."""

import argparse
from getpass import getpass
import os
from uuid import UUID, uuid4

from pwdlib import PasswordHash

from backend.app.accounts.service import normalize_national_id, validate_pin
from backend.app.errors import InvalidInput
from db.promote_admin import first_admin_transaction, require_local_database


def provision(database_url: str, pilot_id: UUID, national_id: str, full_name: str, pin: str) -> UUID:
    national_id = normalize_national_id(national_id)
    validate_pin(pin)
    full_name = full_name.strip()
    if not full_name:
        raise InvalidInput("Ingresa el nombre del administrador")
    require_local_database(database_url)
    account_id = uuid4()
    pin_hash = PasswordHash.recommended().hash(pin)
    with first_admin_transaction(database_url, pilot_id) as conn:
        row = conn.execute("""
            insert into users (id, pilot_id, email, document_number, full_name, role, password_hash)
            values (%s, %s, %s, %s, %s, 'admin', %s)
            on conflict (document_number) where document_number is not null do nothing
            returning id
        """, (account_id, pilot_id, f"{account_id}@ecoconecta.invalid", national_id, full_name, pin_hash)).fetchone()
        if row is None:
            raise InvalidInput("El documento ya se encuentra registrado")
        conn.execute("""
            insert into account_authorization_audit (pilot_id, target_id, action, new_role)
            values (%s, %s, 'bootstrap_first_admin', 'admin')
        """, (pilot_id, account_id))
    return account_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-only", action="store_true", required=True)
    parser.add_argument("national_id")
    parser.add_argument("full_name")
    args = parser.parse_args()
    try:
        pilot_id = UUID(os.environ["ECO_PILOT_ID"])
        database_url = os.environ["DATABASE_URL"]
        require_local_database(database_url)
        pin = getpass("PIN: ")
        if pin != getpass("Confirmar PIN: "):
            parser.error("Los PIN deben coincidir")
        account_id = provision(database_url, pilot_id, args.national_id, args.full_name, pin)
    except (KeyError, ValueError, InvalidInput):
        parser.error("Revisa la configuración, el documento único y el formato del PIN o del piloto")
    print(f"Administrador creado: {account_id}")


if __name__ == "__main__":
    main()
