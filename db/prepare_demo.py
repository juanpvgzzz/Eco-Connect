"""Prepara y verifica los 7 perfiles de demostración del piloto LOCAL (solo desarrollo).

Uso (pila Docker local):
    docker compose exec api python -m db.prepare_demo --local-only            # verifica y crea faltantes
    docker compose exec api python -m db.prepare_demo --local-only --check    # solo verifica
    docker compose exec api python -m db.prepare_demo --local-only --set-pin CEDULA

- Rechaza cualquier base que no sea local (host `db` o localhost): nunca corre en producción.
- Idempotente y no destructivo: no borra ni reinicia solicitudes, citas ni puntos.
- Reutiliza cuentas existentes por perfil; solo crea las que faltan.
- Las cuentas 10001, 20001 y 30001 (PIN 1234, documentadas en frontend/CONTRATO.md) se
  crean si faltan y nunca se modifican si ya existen.
- Los PIN nuevos solo se muestran en una terminal interactiva; no se guardan en archivos.
"""

import argparse
from getpass import getpass
import os
import secrets
import sys
from uuid import UUID, uuid4

from pwdlib import PasswordHash

from backend.app.accounts.postgres_store import PostgresAccountStore
from backend.app.accounts.service import AccountError, AccountService, validate_pin
from backend.app.errors import InvalidInput
from db.connection import open_connection
from db.initialize_collectives import initialize
from db.promote_admin import require_local_database

# Cuentas documentadas del modo demo: (cédula, nombre, rol BD, flujo del colectivo)
FIXED = (
    ("10001", "María Torres", "cliente", None),
    ("20001", "Ana Pérez", "lider", "huerta"),
    ("30001", "Sara Díaz", "lider", "reciclaje"),
)
FIXED_PIN = "1234"
FIXED_DOCS = {doc for doc, *_ in FIXED}
# Perfiles reutilizables: (clave, etiqueta, cédula si hay que crearla, nombre ficticio)
NEW = {
    "business": ("Unidad productiva", "40001", "Tienda Demo Villas"),
    "huerta": ("Huertero", "50001", "Huertero Demo"),
    "reciclaje": ("Reciclador", "60001", "Recicladora Demo"),
    "admin": ("Administrador", "70001", "Administración Demo"),
}


class Report:
    def __init__(self):
        self.rows, self.blockers = [], []

    def ok(self, profile, doc, name, note):
        self.rows.append((profile, doc, name, note))

    def block(self, message):
        self.blockers.append(message)


def _audit(conn, pilot, target, role, collective):
    conn.execute("""
        insert into account_authorization_audit (pilot_id, target_id, action, new_role, new_collective_id)
        values (%s, %s, 'dev_demo_provision', %s, %s)
    """, (pilot, target, role, collective))


def _insert_user(conn, pilot, doc, name, role, kind, pin_hash, collective=None, pilot_enabled=False):
    account = uuid4()
    conn.execute("""
        insert into users (id, pilot_id, email, document_number, full_name, address, phone, kind,
                           role, password_hash, pilot_enabled, collective_id)
        values (%s, %s, %s, %s, %s, 'Villas de San Pablo (dirección ficticia)', '3000000000', %s, %s, %s, %s, %s)
    """, (account, pilot, f"{account}@ecoconecta.invalid", doc, name, kind, role, pin_hash, pilot_enabled, collective))
    _audit(conn, pilot, account, role, collective)
    return account


def prepare(url: str, pilot: UUID, *, create: bool, show, interactive: bool = True) -> Report:
    """`interactive=False` crea solo cuentas con PIN documentado; las de PIN generado quedan como bloqueo."""
    require_local_database(url)
    report = Report()
    hasher = PasswordHash.recommended()
    initialize(url, pilot, create_pilot=False)
    with open_connection(url) as conn, conn.transaction():
        conn.execute("select pg_advisory_xact_lock(854226, 4)")
        flows = {r["flow"]: r["id"] for r in conn.execute(
            "select id, flow from collectives where pilot_id = %s", (pilot,)).fetchall()}

        # 1-3. Cuentas documentadas: crear si faltan; si existen, solo verificar.
        for doc, name, role, flow in FIXED:
            row = conn.execute("""
                select u.id, u.role, u.kind, u.active, u.pilot_enabled, c.flow from users u
                left join collectives c on c.id = u.collective_id
                where u.document_number = %s
            """, (doc,)).fetchone()
            label = "Vecino" if role == "cliente" else f"Coordinadora de {'huerteros' if flow == 'huerta' else 'recicladores'}"
            if row is None:
                if not create:
                    report.block(f"{label} {doc}: no existe")
                    continue
                _insert_user(conn, pilot, doc, name, role, "household", hasher.hash(FIXED_PIN),
                             collective=flows[flow] if flow else None, pilot_enabled=role == "cliente")
                report.ok(label, doc, name, "creada (PIN documentado)")
                continue
            expected = row["active"] and row["role"] == role and row["flow"] == flow and (
                role != "cliente" or row["pilot_enabled"])
            if expected:
                report.ok(label, doc, name, "existente, sin cambios")
            else:
                report.block(f"{label} {doc}: existe con rol/colectivo/habilitación distintos (no se modifica)")

        # 4. Unidad productiva habilitada para el piloto.
        business = conn.execute("""
            select document_number, full_name from users
            where pilot_id = %s and role = 'cliente' and kind = 'business' and active and pilot_enabled
            order by created_at limit 1
        """, (pilot,)).fetchone()
        if business:
            report.ok("Unidad productiva", business["document_number"], business["full_name"], "reutilizada")
        elif create and interactive:
            _, doc, name = NEW["business"]
            pin = _new_pin()
            _insert_user(conn, pilot, doc, name, "cliente", "business", hasher.hash(pin), pilot_enabled=True)
            report.ok("Unidad productiva", doc, name, "creada")
            show("Unidad productiva", doc, pin)
        else:
            report.block("Unidad productiva habilitada: no existe")

        # 5-6. Recolectores con cuenta vinculada a un integrante activo de su colectivo.
        for flow in ("huerta", "reciclaje"):
            label, doc, name = NEW[flow]
            row = conn.execute("""
                select u.document_number, u.full_name, w.full_name as member from users u
                join field_workers w on w.account_id = u.id and w.active and w.collective_id = u.collective_id
                where u.pilot_id = %s and u.role = 'recolector' and u.active and u.collective_id = %s
                order by u.created_at limit 1
            """, (pilot, flows[flow])).fetchone()
            if row:
                report.ok(label, row["document_number"], row["full_name"], f"reutilizada · integrante «{row['member']}»")
            elif create and interactive:
                pin = _new_pin()
                account = _insert_user(conn, pilot, doc, name, "recolector", "household", hasher.hash(pin),
                                       collective=flows[flow])
                conn.execute("""
                    insert into field_workers (pilot_id, full_name, collective_id, account_id)
                    values (%s, %s, %s, %s)
                """, (pilot, name, flows[flow], account))
                report.ok(label, doc, name, "creada y vinculada a field_workers")
                show(label, doc, pin)
            else:
                report.block(f"{label}: no hay cuenta vinculada a un integrante activo")

        # 7. Administrador (nunca por endpoint público).
        admin = conn.execute("""
            select document_number, full_name from users
            where pilot_id = %s and role = 'admin' and active and document_number is not null
            order by created_at limit 1
        """, (pilot,)).fetchone()
        if admin:
            report.ok("Administrador", admin["document_number"], admin["full_name"], "reutilizada")
        elif create and interactive:
            _, doc, name = NEW["admin"]
            pin = _new_pin()
            _insert_user(conn, pilot, doc, name, "admin", "household", hasher.hash(pin))
            report.ok("Administrador", doc, name, "creada")
            show("Administrador", doc, pin)
        else:
            report.block("Administrador: no existe")

        # Requisitos operativos de la demostración.
        for flow in ("huerta", "reciclaje"):
            if not conn.execute("select 1 from field_workers where collective_id = %s and active",
                                (flows[flow],)).fetchone():
                report.block(f"Colectivo {flow}: sin integrantes activos")
        if not conn.execute("""
            select 1 from point_rules r join materials m on m.id = r.material_id
            where m.active and r.valid_from <= now() and (r.valid_until is null or r.valid_until > now())
        """).fetchone():
            report.block("No hay reglas de puntos vigentes: el administrador debe configurarlas en «Reglas de puntos»")

    # Login real de las cuentas con PIN documentado.
    service = AccountService(PostgresAccountStore(url, pilot))
    for doc, *_ in FIXED:
        try:
            result = service.login(doc, FIXED_PIN)
            service.logout(result.access_token)
        except AccountError:
            report.block(f"{doc}: el PIN documentado no permite iniciar sesión")
    return report


def set_pin(url: str, pilot: UUID, doc: str) -> None:
    require_local_database(url)
    if doc in FIXED_DOCS:
        raise SystemExit("Las cuentas 10001, 20001 y 30001 conservan su PIN documentado.")
    pin = getpass("Nuevo PIN temporal (4 a 12 dígitos): ")
    if pin != getpass("Confirmar PIN: "):
        raise SystemExit("Los PIN no coinciden.")
    try:
        validate_pin(pin)
    except InvalidInput:
        raise SystemExit("El PIN debe tener entre 4 y 12 dígitos.") from None
    with open_connection(url) as conn, conn.transaction():
        row = conn.execute("""
            update users set password_hash = %s
            where document_number = %s and pilot_id = %s and active returning id, role
        """, (PasswordHash.recommended().hash(pin), doc, pilot)).fetchone()
        if row is None:
            raise SystemExit("No existe una cuenta activa con esa cédula en el piloto local.")
        conn.execute("update account_sessions set revoked_at = now() where account_id = %s and revoked_at is null",
                     (row["id"],))
        _audit(conn, pilot, row["id"], row["role"], None)
    print("PIN actualizado. Las sesiones abiertas de esa cuenta se cerraron.")


def _new_pin() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--local-only", action="store_true", required=True)
    parser.add_argument("--check", action="store_true", help="Solo verificar; no crear cuentas")
    parser.add_argument("--set-pin", metavar="CEDULA", help="Asignar un PIN temporal de forma interactiva")
    args = parser.parse_args()
    try:
        url, pilot = os.environ["DATABASE_URL"], UUID(os.environ["ECO_PILOT_ID"])
    except (KeyError, ValueError):
        parser.error("Revisa DATABASE_URL y ECO_PILOT_ID.")
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if args.set_pin:
        if not interactive:
            parser.error("--set-pin requiere una terminal interactiva.")
        return set_pin(url, pilot, args.set_pin)

    def show(label, doc, pin):
        print(f"  PIN nuevo · {label} · cédula {doc}: {pin}  (anótelo; no se guarda)", flush=True)

    report = prepare(url, pilot, create=not args.check, show=show, interactive=interactive)
    if not args.check and not interactive:
        print("Aviso: sin terminal interactiva no se crean cuentas con PIN generado (no se muestran en logs).")
    print("\nPerfil                        Cédula            Nombre                              Estado")
    for profile, doc, name, note in report.rows:
        print(f"{profile:<29} {doc:<17} {name:<35} {note}")
    if report.blockers:
        print("\nBLOQUEOS:")
        for message in report.blockers:
            print(f"  - {message}")
        raise SystemExit(1)
    print("\nLos 7 perfiles están listos. Las solicitudes existentes no se modificaron.")


if __name__ == "__main__":
    main()
