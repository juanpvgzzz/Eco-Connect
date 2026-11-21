"""Carga los datos FICTICIOS de la presentación de EcoConecta en el piloto configurado.

Uso:
    python -m db.seed_presentation --check    # valida esquema, piloto y dependencias; no escribe
    python -m db.seed_presentation --apply    # carga con confirmación interactiva explícita

Opciones de --apply / --check:
    --material-organico CODIGO     material (con regla de puntos vigente) para cierres de huerta
    --material-reciclable CODIGO   material (con regla de puntos vigente) para cierres de reciclaje

Garantías:
- Solo inserta. No modifica ni borra filas existentes, no crea el piloto ni los colectivos y
  no crea reglas de puntos, materiales ni premios (si faltan, --check lo reporta como bloqueo).
- Idempotente: los perfiles se identifican por su correo técnico
  `demo-presentacion.<perfil>@ecoconecta.invalid` y las solicitudes por su clave de reintento
  `demo-presentacion-v1:<escenario>`. Una segunda ejecución no duplica nada.
- Todo ocurre en una única transacción: ante cualquier error se revierte por completo.
- Las solicitudes, citas, cierres, puntos e insignias se generan con el servicio real de
  recolecciones (`Collections` + `CollectionTransaction`): los puntos se acreditan una sola vez
  con las reglas vigentes y los hitos de participación los otorga el trigger existente.
- Las cédulas y los PIN de los perfiles nuevos se ingresan en la terminal (el PIN con getpass),
  se validan con la política vigente (4 a 12 dígitos) y se guardan solo como hash Argon2.
  Nunca se imprimen ni se escriben en archivos o logs.
"""

import argparse
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_DOWN
from getpass import getpass
import os
from pathlib import Path
import sys
from typing import Callable
from uuid import UUID, uuid4

from psycopg.conninfo import conninfo_to_dict
from pwdlib import PasswordHash

from backend.app.accounts.postgres_store import PostgresAccountStore
from backend.app.accounts.service import AccountError, AccountService, normalize_national_id, validate_pin
from backend.app.collections.postgres import CollectionTransaction, PostgresCollections
from backend.app.collections.service import (
    BARRANQUILLA, Actor, Collections, PickupResult, Problem, Reason, Request, Schedule, WorkerNotice,
)
from backend.app.errors import InvalidInput
from db.connection import open_connection
from db.migrate import MIGRATIONS
from db.promote_admin import LOCAL_HOSTS

SEED_KEY = "demo-presentacion-v1"
EMAIL = "demo-presentacion.{}@ecoconecta.invalid"
FICTIONAL_ADDRESS = "Dirección ficticia de demostración, Villas de San Pablo"
FICTIONAL_PHONE = "3000000000"
FICTIONAL_NOTE = "DATO FICTICIO DE DEMOSTRACIÓN."
LOCK = (854226, 5)
EDUCATION_SQL = Path(__file__).with_name("publish_education.sql")


@dataclass(frozen=True)
class Profile:
    key: str
    label: str
    name: str
    role: str                      # rol en la tabla users
    kind: str = "household"
    flow: str | None = None        # colectivo (líderes y recolectores)
    pilot_enabled: bool = False
    api_role: str = ""             # rol que devuelve /accounts/me


PROFILES = (
    Profile("vecino", "Vecino", "Vecina Ficticia Demo", "cliente", pilot_enabled=True, api_role="resident"),
    Profile("unidad", "Unidad productiva", "Tienda Ficticia Demo", "cliente", kind="business",
            pilot_enabled=True, api_role="business"),
    Profile("coord-huerta", "Coordinadora de huerta", "Coordinadora Huerta Ficticia Demo", "lider",
            flow="huerta", api_role="leader"),
    Profile("coord-reciclaje", "Coordinadora de reciclaje", "Coordinadora Reciclaje Ficticia Demo", "lider",
            flow="reciclaje", api_role="leader"),
    Profile("huertero", "Huertero", "Huertero Ficticio Demo", "recolector", flow="huerta",
            api_role="field_worker"),
    Profile("reciclador", "Reciclador", "Reciclador Ficticio Demo", "recolector", flow="reciclaje",
            api_role="field_worker"),
    Profile("admin", "Administrador", "Administración Ficticia Demo", "admin", api_role="admin"),
)
BY_KEY = {p.key: p for p in PROFILES}

# Pasos: ("revisar",) ("programar", "pasada"|"futura") ("aviso",)
#        ("cerrar", "recolector"|"coordinadora", kilos) ("fallida", motivo) ("cancelar", motivo)
SCENARIOS = (
    ("vecino-organico-1", "vecino", "organico", "Cáscaras de frutas y verduras",
     [("programar", "pasada"), ("cerrar", "recolector", "3.2")]),
    ("vecino-organico-2", "vecino", "organico", "Borra de café y hojas secas",
     [("revisar",), ("programar", "pasada"), ("aviso",), ("cerrar", "coordinadora", "2.5")]),
    ("vecino-reciclable-1", "vecino", "reciclable", "Papel, cartón y botellas plásticas",
     [("programar", "pasada"), ("cerrar", "recolector", "4.0")]),
    ("vecino-reciclable-2", "vecino", "reciclable", "Botellas plásticas y latas",
     [("programar", "futura"), ("aviso",)]),
    ("vecino-reciclable-3", "vecino", "reciclable", "Cartón doblado",
     [("programar", "pasada"), ("fallida", "Nadie atendió la visita (dato ficticio)")]),
    ("vecino-organico-3", "vecino", "organico", "Restos de verduras crudas", []),
    ("unidad-reciclable-1", "unidad", "reciclable", "Cajas de cartón y papel de oficina",
     [("programar", "pasada"), ("cerrar", "recolector", "12.5")]),
    ("unidad-organico-1", "unidad", "organico", "Restos vegetales de cocina", [("programar", "futura")]),
    ("unidad-reciclable-2", "unidad", "reciclable", "Envases de vidrio limpios", [("revisar",)]),
    ("unidad-organico-2", "unidad", "organico", "Poda de jardín",
     [("cancelar", "El cliente canceló la solicitud (dato ficticio)")]),
)
FLOW_OF = {"organico": "huerta", "reciclable": "reciclaje"}
ORGANIC_HINTS = ("ORGAN", "COMPOST", "VEGET", "PODA")
RECYCLE_HINTS = ("PET", "PAPEL", "CART", "PLAST", "VIDR", "LATA", "RECIC", "METAL", "ALUM", "CHATAR")
BLOCKER_PIN_SEQUENCES = ("01234567890123456789", "98765432109876543210")


class SeedError(Exception):
    """La carga no puede continuar; el mensaje es apto para mostrarse (sin secretos)."""


@dataclass
class Report:
    rows: list = field(default_factory=list)        # (sección, detalle, estado)
    blockers: list = field(default_factory=list)
    materials: dict = field(default_factory=dict)   # flujo -> {code, name, points_per_kg}
    pilot_name: str = ""
    profiles: dict = field(default_factory=dict)    # clave -> fila existente o None
    scenarios_present: int = 0
    content_present: int = 0
    created: dict = field(default_factory=dict)

    def ok(self, section, detail, state):
        self.rows.append((section, detail, state))

    def block(self, message):
        self.blockers.append(message)


# --------------------------------------------------------------------------- utilidades

def is_local(url: str) -> bool:
    params = conninfo_to_dict(url)
    return params.get("host") in LOCAL_HOSTS and not params.get("hostaddr") and not params.get("service")


def is_production(url: str) -> bool:
    return not is_local(url) or os.environ.get("RAILWAY_ENVIRONMENT_NAME", "").lower() == "production"


def describe_target(url: str) -> str:
    params = conninfo_to_dict(url)
    return f"{params.get('host', '?')}:{params.get('port', '5432')}/{params.get('dbname', '?')}"


def pin_problem(pin: str, document: str) -> str | None:
    """Política vigente (4 a 12 dígitos) más el rechazo de PIN triviales o fijos."""
    try:
        validate_pin(pin)
    except InvalidInput:
        return "El PIN debe tener entre 4 y 12 dígitos."
    if len(set(pin)) == 1 or any(pin in seq for seq in BLOCKER_PIN_SEQUENCES):
        return "El PIN es trivial (repetido o consecutivo, como 1234). Elige otro."
    if pin == document:
        return "El PIN no puede ser igual a la cédula."
    return None


def _scenario_key(slug: str) -> str:
    return f"{SEED_KEY}:{slug}"


def _request(residuo: str, material: str, generador: str) -> Request:
    return Request(
        residuo=residuo, material=material, contacto="Contacto ficticio de demostración",
        direccion=FICTIONAL_ADDRESS, generador=generador,
        disponibilidad="Mañanas entre semana (dato ficticio)",
        observaciones=f"{FICTIONAL_NOTE} Generado por db.seed_presentation.",
    )


def _points(kilos: str, per_kg) -> int:
    return int((Decimal(kilos) * Decimal(per_kg)).to_integral_value(rounding=ROUND_DOWN))


# --------------------------------------------------------------------------- inspección

def _materials(conn) -> list[dict]:
    return conn.execute("""
        select distinct on (m.id) m.code, m.name, r.points_per_kg from materials m
        join point_rules r on r.material_id = m.id
        where m.active and r.valid_from <= now() and (r.valid_until is null or r.valid_until > now())
        order by m.id, r.valid_from desc, r.id desc
    """).fetchall()


def _pick_material(available: list[dict], flow: str, requested: str | None) -> dict | None:
    by_code = {m["code"]: m for m in available}
    if requested:
        return by_code.get(requested.strip().upper())
    organic = [m for m in available if any(h in f"{m['code']} {m['name']}".upper() for h in ORGANIC_HINTS)]
    if flow == "huerta":
        candidates = organic
    else:
        candidates = [m for m in available if m not in organic
                      and any(h in f"{m['code']} {m['name']}".upper() for h in RECYCLE_HINTS)]
    return sorted(candidates, key=lambda m: m["code"])[0] if candidates else None


def _profile_problem(row, profile: Profile) -> str | None:
    if not row["active"]:
        return "inactivo"
    if row["role"] != profile.role or row["kind"] != profile.kind:
        return "rol o tipo distinto"
    if row["flow"] != profile.flow:
        return "colectivo distinto"
    if profile.pilot_enabled and not row["pilot_enabled"]:
        return "no habilitado en el piloto"
    if profile.role == "recolector" and not row["worker_id"]:
        return "sin integrante operativo vinculado"
    if not row["document_number"]:
        return "sin cédula"
    return None


def inspect(conn, pilot: UUID, materials: dict[str, str | None]) -> Report:
    report = Report()

    expected = sorted(p.name for p in MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"))
    has_table = conn.execute("select to_regclass('schema_migrations') is not null as ok").fetchone()["ok"]
    applied = {r["name"] for r in conn.execute("select name from schema_migrations").fetchall()} if has_table else set()
    missing = [name for name in expected if name not in applied]
    if missing:
        report.block(f"Migraciones sin aplicar: {', '.join(missing)}")
    else:
        report.ok("Esquema", f"{len(expected)} migraciones", "aplicadas")

    pilot_row = conn.execute("select name, active from pilots where id = %s", (pilot,)).fetchone()
    if pilot_row is None or not pilot_row["active"]:
        report.block("ECO_PILOT_ID no corresponde a un piloto activo (no se crea).")
        return report
    report.pilot_name = pilot_row["name"]
    report.ok("Piloto", pilot_row["name"], "activo")

    flows = {r["flow"]: r["id"] for r in conn.execute(
        "select id, flow from collectives where pilot_id = %s", (pilot,)).fetchall()}
    for flow in ("huerta", "reciclaje"):
        if flow in flows:
            report.ok("Colectivo", flow, "existe")
        else:
            report.block(f"Falta el colectivo {flow} (no se crea).")

    available = _materials(conn)
    if not available:
        report.block("No hay reglas de puntos vigentes. Adminístralas en «Reglas de puntos»; "
                     "este comando no inventa equivalencias.")
    for flow, option in (("huerta", "--material-organico"), ("reciclaje", "--material-reciclable")):
        if not available:
            break
        chosen = _pick_material(available, flow, materials.get(flow))
        if chosen is None:
            codes = ", ".join(sorted(m["code"] for m in available))
            report.block(f"No se identificó material para {flow}. Indica {option} con uno de: {codes}")
            continue
        planned = [Decimal(s[2]) for _, _, residuo, _, steps in SCENARIOS if FLOW_OF[residuo] == flow
                   for s in steps if s[0] == "cerrar"]
        if any(_points(str(k), chosen["points_per_kg"]) <= 0 for k in planned):
            report.block(f"La regla vigente de {chosen['code']} no otorga puntos con los pesos de la demo.")
            continue
        report.materials[flow] = chosen
        report.ok("Material", f"{flow}: {chosen['code']} ({chosen['points_per_kg']} pts/kg, provisional)",
                  "regla vigente")

    for profile in PROFILES:
        row = conn.execute("""
            select u.id, u.document_number, u.role, u.kind, u.active, u.pilot_enabled, u.pilot_id,
                   c.flow, w.id as worker_id
            from users u
            left join collectives c on c.id = u.collective_id and c.pilot_id = u.pilot_id
            left join field_workers w on w.account_id = u.id and w.active and w.collective_id = u.collective_id
            where lower(u.email) = %s
        """, (EMAIL.format(profile.key),)).fetchone()
        report.profiles[profile.key] = row
        if row is None:
            report.ok("Perfil", profile.label, "por crear")
        elif row["pilot_id"] != pilot:
            report.block(f"{profile.label}: el perfil ficticio existe en otro piloto (no se modifica).")
        elif problem := _profile_problem(row, profile):
            report.block(f"{profile.label}: existe pero está {problem} (no se modifica).")
        else:
            report.ok("Perfil", f"{profile.label} · cédula {row['document_number']}", "existente")

    report.scenarios_present = conn.execute("""
        select count(*) as n from pickup_requests where pilot_id = %s and idempotency_key like %s
    """, (pilot, f"{SEED_KEY}:%")).fetchone()["n"]
    report.ok("Solicitudes ficticias", f"{report.scenarios_present}/{len(SCENARIOS)}", "presentes")

    slugs = _education_slugs(pilot)
    report.content_present = conn.execute(
        "select count(*) as n from content_entries where slug = any(%s)", (slugs,)).fetchone()["n"]
    report.ok("Contenido educativo", f"{report.content_present}/{len(slugs)} guías generales", "publicadas")
    return report


def _education_slugs(pilot: UUID) -> list[str]:
    text = EDUCATION_SQL.read_text(encoding="utf-8")
    return [f"{pilot}-{line.split(chr(39))[1]}" for line in text.splitlines()
            if line.strip().startswith("('") and "', '" in line]


def check(url: str, pilot: UUID, materials: dict[str, str | None] | None = None) -> Report:
    with open_connection(url) as conn, conn.transaction():
        conn.execute("set transaction read only")
        return inspect(conn, pilot, materials or {})


# --------------------------------------------------------------------------- carga

def _insert_profile(conn, pilot: UUID, profile: Profile, document: str, pin_hash: str,
                    collectives: dict) -> UUID:
    account = uuid4()
    collective = collectives.get(profile.flow)
    row = conn.execute("""
        insert into users (id, pilot_id, email, document_number, full_name, address, phone, kind,
                           role, password_hash, pilot_enabled, collective_id)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict do nothing returning id
    """, (account, pilot, EMAIL.format(profile.key), document, profile.name, FICTIONAL_ADDRESS,
          FICTIONAL_PHONE, profile.kind, profile.role, pin_hash, profile.pilot_enabled, collective)).fetchone()
    if row is None:
        raise SeedError(f"{profile.label}: la cédula o el perfil ya existen; no se modificó nada.")
    if profile.role == "recolector":
        conn.execute("""
            insert into field_workers (pilot_id, full_name, collective_id, account_id)
            values (%s, %s, %s, %s)
        """, (pilot, profile.name, collective, account))
    conn.execute("""
        insert into account_authorization_audit (pilot_id, target_id, action, new_role, new_collective_id)
        values (%s, %s, 'presentation_seed', %s, %s)
    """, (pilot, account, profile.role, collective))
    return account


def _free_slot(conn, pilot: UUID, collective: UUID, used: set, future: bool) -> datetime:
    """Primera hora sin franja registrada en el colectivo (no reutiliza ni toca franjas existentes)."""
    today = datetime.now(BARRANQUILLA).date()
    days = range(2, 30) if future else range(-1, -30, -1)
    for offset in days:
        day: date = today + timedelta(days=offset)
        if day.weekday() == 6:
            continue
        for hour in (9, 10, 11, 14, 15):
            at = datetime.combine(day, time(hour, 0), BARRANQUILLA)
            if (collective, at) in used:
                continue
            taken = conn.execute("""
                select 1 from pickup_slots where pilot_id = %s and collective_id = %s and starts_at = %s
            """, (pilot, collective, at)).fetchone()
            if not taken:
                used.add((collective, at))
                return at
    raise SeedError("No se encontró una franja libre para las citas de demostración.")


def _run_scenarios(conn, pilot: UUID, ids: dict, workers: dict, collectives: dict,
                   materials: dict) -> tuple[int, int]:
    @contextmanager
    def same_transaction():
        # Cada operación del servicio usa la transacción externa: un fallo revierte toda la carga.
        yield CollectionTransaction(conn, pilot)

    service = Collections(same_transaction)
    actors = {
        "vecino": Actor(ids["vecino"], "cliente", generador="hogar"),
        "unidad": Actor(ids["unidad"], "cliente", generador="unidad_productiva"),
    }
    leaders = {"huerta": Actor(ids["coord-huerta"], "lider", "huerta"),
               "reciclaje": Actor(ids["coord-reciclaje"], "lider", "reciclaje")}
    worker_keys = {"huerta": "huertero", "reciclaje": "reciclador"}
    used: set = set()
    created = closed = 0
    for slug, owner, residuo, material, steps in SCENARIOS:
        flow = FLOW_OF[residuo]
        client = actors[owner]
        if conn.execute("""
            select 1 from pickup_requests where client_id = %s and idempotency_key = %s
        """, (client.id, _scenario_key(slug))).fetchone():
            continue  # cargado en una ejecución anterior (quizá atendido en vivo): no se toca
        row = service.create(client, _scenario_key(slug), _request(residuo, material, client.generador))
        created += 1
        leader, worker_id = leaders[flow], workers[flow]
        worker_actor = Actor(ids[worker_keys[flow]], "recolector", flow, trabajador_id=worker_id)
        cita = None
        for step in steps:
            kind = step[0]
            if kind == "revisar":
                service.review(leader, row.id)
            elif kind == "programar":
                cita = _free_slot(conn, pilot, collectives[flow], used, future=step[1] == "futura")
                if step[1] == "futura":
                    schedule = Schedule(cita=cita, responsable=worker_id)
                else:
                    # Registro histórico: la validación «cita futura» es de entrada en la API.
                    schedule = Schedule.model_construct(cita=cita, responsable=worker_id, motivo=None)
                service.schedule(leader, row.id, schedule)
            elif kind == "aviso":
                service.notify_worker(leader, row.id, WorkerNotice(canal="llamada", nota="Aviso ficticio de demostración"))
            elif kind == "cerrar":
                by, kilos = step[1], step[2]
                result = PickupResult(
                    material=materials[flow]["code"], kilos=Decimal(kilos), resultado="total",
                    recogida_en=cita + timedelta(minutes=20), observaciones=FICTIONAL_NOTE,
                    constancia="Llamada del recolector (dato ficticio)" if by == "coordinadora" else None,
                )
                service.close(worker_actor if by == "recolector" else leader, row.id, result)
                closed += 1
            elif kind == "fallida":
                service.interrupt(leader, row.id, Reason(motivo=step[1]), failed=True)
            elif kind == "cancelar":
                service.interrupt(leader, row.id, Reason(motivo=step[1]), failed=False)
    return created, closed


def _publish_education(conn, pilot: UUID) -> int:
    """Reutiliza db/publish_education.sql (guía general, sin rutas ni horarios oficiales)."""
    sql = EDUCATION_SQL.read_text(encoding="utf-8")
    sql = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    sql = sql.replace(":'pilot_id'", "%(pilot)s").rstrip().rstrip(";")
    return len(conn.execute(sql + " returning slug", {"pilot": str(pilot)}).fetchall())


CredentialsPrompt = Callable[[Profile, set[str], set[str]], tuple[str, str]]


def apply(url: str, pilot: UUID, *, credentials: CredentialsPrompt, confirm: Callable[[Report], bool],
          materials: dict[str, str | None] | None = None) -> tuple[Report, dict[str, tuple[str, str]]]:
    """Carga todo en una transacción. Devuelve el reporte y {perfil: (cédula, PIN)} de los perfiles
    creados en esta ejecución (solo en memoria, para verificar el acceso)."""
    report = check(url, pilot, materials)
    if report.blockers:
        return report, {}
    missing = [p for p in PROFILES if report.profiles[p.key] is None]

    # Credenciales antes de abrir la transacción: no se mantiene un bloqueo durante la captura.
    creds: dict[str, tuple[str, str]] = {}
    docs: set[str] = set()
    pins: set[str] = set()
    with open_connection(url) as conn:
        for profile in missing:
            document, pin = credentials(profile, docs, pins)
            document = normalize_national_id(document)
            if document in docs or conn.execute(
                    "select 1 from users where document_number = %s", (document,)).fetchone():
                raise SeedError(f"{profile.label}: la cédula ya está registrada; usa otra.")
            if problem := pin_problem(pin, document):
                raise SeedError(f"{profile.label}: {problem}")
            if pin in pins:
                raise SeedError(f"{profile.label}: usa un PIN distinto para cada perfil.")
            docs.add(document)
            pins.add(pin)
            creds[profile.key] = (document, pin)

    if not confirm(report):
        raise SeedError("Carga cancelada por el operador. No se escribió nada.")

    hasher = PasswordHash.recommended()
    with open_connection(url) as conn, conn.transaction():
        conn.execute("set local lock_timeout = '10s'")
        conn.execute("select pg_advisory_xact_lock(%s, %s)", LOCK)
        again = inspect(conn, pilot, materials or {})  # bajo el bloqueo: nada cambió desde --check
        if again.blockers or any((again.profiles[k] is None) != (k in creds) for k in BY_KEY):
            raise SeedError("El estado cambió durante la confirmación. Vuelve a ejecutar --check.")
        collectives = {r["flow"]: r["id"] for r in conn.execute(
            "select id, flow from collectives where pilot_id = %s", (pilot,)).fetchall()}
        ids = {k: row["id"] for k, row in again.profiles.items() if row is not None}
        for profile in missing:
            document, pin = creds[profile.key]
            ids[profile.key] = _insert_profile(conn, pilot, profile, document, hasher.hash(pin), collectives)
        workers = {r["flow"]: r["id"] for r in conn.execute("""
            select c.flow, w.id from field_workers w join collectives c on c.id = w.collective_id
            where w.account_id = any(%s) and w.active
        """, ([ids["huertero"], ids["reciclador"]],)).fetchall()}
        try:
            created, closed = _run_scenarios(conn, pilot, ids, workers, collectives, again.materials)
        except Problem as exc:
            raise SeedError(f"Una operación de la demo fue rechazada por las reglas: {exc}") from exc
        content = _publish_education(conn, pilot)
        report.created = {"perfiles": len(missing), "solicitudes": created, "cierres": closed,
                          "contenidos": content}
    return report, creds


# --------------------------------------------------------------------------- verificación

def verify_access(url: str, pilot: UUID, creds: dict[str, tuple[str, str]]) -> list[tuple[str, str]]:
    """Inicia y cierra sesión con cada perfil nuevo y comprueba que su panel lo reconozca."""
    service = AccountService(PostgresAccountStore(url, pilot))
    panels = PostgresCollections(url, pilot)
    results = []
    for key, (document, pin) in creds.items():
        profile = BY_KEY[key]
        try:
            login = service.login(document, pin)
        except AccountError:
            results.append((profile.label, "FALLO: no pudo iniciar sesión"))
            continue
        try:
            identity = login.identity
            ok = identity.profile.role == profile.api_role and identity.collective_flow == profile.flow
            if ok and profile.role != "admin":
                actor = panels.actor(identity)
                ok = actor.flujo == profile.flow
            results.append((profile.label, "acceso al panel verificado" if ok else "FALLO: rol o colectivo"))
        except Problem:
            results.append((profile.label, "FALLO: sin acceso al panel"))
        finally:
            service.logout(login.access_token)
    return results


# --------------------------------------------------------------------------- terminal

def _print_report(report: Report) -> None:
    for section, detail, state in report.rows:
        print(f"  {section:<22} {detail:<58} {state}")
    if report.blockers:
        print("\nBLOQUEOS:")
        for message in report.blockers:
            print(f"  - {message}")


def _prompt_credentials(profile: Profile, docs: set[str], pins: set[str]) -> tuple[str, str]:
    print(f"\n{profile.label} ({profile.name}):")
    while True:
        try:
            document = normalize_national_id(input("  Cédula: ").strip())
        except InvalidInput:
            print("  La cédula solo admite dígitos.")
            continue
        if document in docs:
            print("  Esa cédula ya se asignó a otro perfil de esta carga.")
            continue
        pin = getpass("  PIN (no se muestra): ")
        if pin != getpass("  Confirmar PIN: "):
            print("  Los PIN no coinciden.")
            continue
        if problem := pin_problem(pin, document):
            print(f"  {problem}")
            continue
        if pin in pins:
            print("  Usa un PIN distinto para cada perfil.")
            continue
        return document, pin


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Validar sin escribir")
    mode.add_argument("--apply", action="store_true", help="Cargar con confirmación interactiva")
    parser.add_argument("--material-organico", metavar="CODIGO")
    parser.add_argument("--material-reciclable", metavar="CODIGO")
    args = parser.parse_args()
    try:
        url, pilot = os.environ["DATABASE_URL"], UUID(os.environ["ECO_PILOT_ID"])
    except (KeyError, ValueError):
        parser.error("Revisa DATABASE_URL y ECO_PILOT_ID.")
    materials = {"huerta": args.material_organico, "reciclaje": args.material_reciclable}
    production = is_production(url)
    print(f"Destino: {describe_target(url)}  ·  entorno: {'PRODUCCIÓN' if production else 'local'}")

    if args.check:
        report = check(url, pilot, materials)
        _print_report(report)
        if report.blockers:
            raise SystemExit(1)
        print("\nListo para --apply. No se escribió nada.")
        return

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        parser.error("--apply requiere una terminal interactiva (cédulas, PIN y confirmación).")

    def confirm(report: Report) -> bool:
        _print_report(report)
        missing = sum(1 for row in report.profiles.values() if row is None)
        print(f"\nSe insertarán (solo datos FICTICIOS, sin modificar ni borrar nada):"
              f"\n  - {missing} perfiles nuevos"
              f"\n  - hasta {len(SCENARIOS) - report.scenarios_present} solicitudes con su historial, citas,"
              f" cierres y puntos"
              f"\n  - hasta {len(_education_slugs(pilot)) - report.content_present} guías educativas generales")
        if production:
            phrase = f"CARGAR DEMO {report.pilot_name}"
            return input(f"\nEsto escribe en PRODUCCIÓN. Escribe exactamente «{phrase}» para continuar: ") == phrase
        return input("\n¿Continuar? Escribe «si»: ").strip().lower() == "si"

    try:
        report, creds = apply(url, pilot, credentials=_prompt_credentials, confirm=confirm, materials=materials)
    except (SeedError, InvalidInput) as exc:
        raise SystemExit(f"\nNo se cargó nada: {exc}") from None
    except KeyboardInterrupt:
        raise SystemExit("\nInterrumpido. No se cargó nada.") from None
    if report.blockers:
        _print_report(report)
        raise SystemExit(1)
    print("\nCarga confirmada (transacción completa):")
    for name, total in report.created.items():
        print(f"  {name:<12} {total}")
    for label, state in verify_access(url, pilot, creds):
        print(f"  {label:<28} {state}")
    print("\nPerfiles ficticios (los PIN no se muestran ni se guardan):")
    for key, (document, _) in creds.items():
        print(f"  {BY_KEY[key].label:<28} cédula {document}")
    creds.clear()


if __name__ == "__main__":
    main()
