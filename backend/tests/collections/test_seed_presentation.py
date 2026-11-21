"""db.seed_presentation contra PostgreSQL real en un esquema temporal."""

from datetime import datetime, timedelta
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from backend.app.collections.service import BARRANQUILLA
from backend.app.main import create_app
from db import seed_presentation as seed
from db.connection import open_connection
from db.initialize_collectives import initialize
from db.migrate import migrate

TABLES = ("users", "field_workers", "pickup_requests", "pickup_slots", "pickup_appointments",
          "collection_events", "deliveries", "delivery_items", "point_movements",
          "participation_recognitions", "content_entries", "account_authorization_audit",
          "pilots", "collectives", "materials", "point_rules", "rewards")
CREDS = {
    "vecino": ("900000101", "582913"), "unidad": ("900000102", "704152"),
    "coord-huerta": ("900000103", "819374"), "coord-reciclaje": ("900000104", "263951"),
    "huertero": ("900000105", "470286"), "reciclador": ("900000106", "915037"),
    "admin": ("900000107", "638402"),
}


@pytest.fixture
def pilot_db():
    base = os.environ.get("TEST_DATABASE_URL")
    if not base:
        pytest.skip("TEST_DATABASE_URL is required")
    schema = sql.Identifier(f"ec_seed_{uuid4().hex}")
    with open_connection(base) as conn:
        conn.execute(sql.SQL("create schema {}").format(schema))
    url = make_conninfo(base, options=f"-c search_path={schema.as_string()}")
    try:
        migrate(url)
        pilot = uuid4()
        initialize(url, pilot, create_pilot=True)  # el piloto y los colectivos ya existen en producción
        yield url, pilot
    finally:
        with open_connection(base) as conn:
            conn.execute(sql.SQL("drop schema {} cascade").format(schema))


def _rules(url):
    with open_connection(url) as conn:
        for code, name, per_kg in (("ORGANICO", "Orgánicos", 10), ("PET", "Plástico PET", 15)):
            conn.execute("""
                with m as (insert into materials (code, name) values (%s, %s) returning id)
                insert into point_rules (material_id, points_per_kg, valid_from) select id, %s, now() - interval '1 day' from m
            """, (code, name, per_kg))


def _existing_data(url, pilot):
    """Datos previos de producción que la carga no debe tocar."""
    with open_connection(url) as conn:
        conn.execute("""
            insert into users (pilot_id, email, document_number, full_name, role, password_hash, pilot_enabled)
            values (%s, 'real@example.invalid', '123450', 'Vecino Real', 'cliente', 'x', true)
        """, (pilot,))


def _snapshot(url):
    with open_connection(url) as conn:
        return {t: conn.execute(sql.SQL("select md5(coalesce(string_agg(t::text, '|' order by t::text), '')) as h, "
                                        "count(*) as n from {} t").format(sql.Identifier(t))).fetchone()
                for t in TABLES}


def _credentials(profile, docs, pins):
    return CREDS[profile.key]


def test_check_reports_missing_rules_without_writing(pilot_db):
    url, pilot = pilot_db
    before = _snapshot(url)
    report = seed.check(url, pilot)
    assert any("reglas de puntos" in b for b in report.blockers)
    assert _snapshot(url) == before
    # --apply con bloqueos no pide credenciales ni escribe.
    report, creds = seed.apply(url, pilot, credentials=lambda *a: pytest.fail("no debe pedir"),
                               confirm=lambda r: pytest.fail("no debe confirmar"))
    assert report.blockers and creds == {} and _snapshot(url) == before


def test_check_blocks_unknown_pilot(pilot_db):
    url, _ = pilot_db
    assert any("piloto activo" in b for b in seed.check(url, uuid4()).blockers)


def test_weak_and_fixed_pins_are_rejected():
    for pin in ("1234", "0000", "987654", "12", "abcd", "900000101"):
        assert seed.pin_problem(pin, "900000101"), pin
    assert seed.pin_problem("582913", "900000101") is None


def test_rejects_documented_fixed_pin_before_writing(pilot_db):
    url, pilot = pilot_db
    _rules(url)
    before = _snapshot(url)
    with pytest.raises(seed.SeedError, match="trivial"):
        seed.apply(url, pilot, credentials=lambda p, d, s: ("900000999", "1234"), confirm=lambda r: True)
    assert _snapshot(url) == before


def test_operator_cancel_writes_nothing(pilot_db):
    url, pilot = pilot_db
    _rules(url)
    before = _snapshot(url)
    with pytest.raises(seed.SeedError, match="cancelada"):
        seed.apply(url, pilot, credentials=_credentials, confirm=lambda r: False)
    assert _snapshot(url) == before


def test_failure_mid_load_rolls_back_everything(pilot_db, monkeypatch):
    url, pilot = pilot_db
    _rules(url)
    before = _snapshot(url)

    def boom(conn, pilot_id):
        raise RuntimeError("fallo simulado al publicar contenido")

    monkeypatch.setattr(seed, "_publish_education", boom)
    with pytest.raises(RuntimeError):
        seed.apply(url, pilot, credentials=_credentials, confirm=lambda r: True)
    assert _snapshot(url) == before


def test_apply_loads_once_and_all_panels_and_flows_work(pilot_db):
    url, pilot = pilot_db
    _rules(url)
    _existing_data(url, pilot)
    with open_connection(url) as conn:
        real = conn.execute("select * from users where document_number = '123450'").fetchone()

    assert seed.check(url, pilot).blockers == []
    report, creds = seed.apply(url, pilot, credentials=_credentials, confirm=lambda r: True)
    assert report.blockers == []
    assert report.created == {"perfiles": 7, "solicitudes": 10, "cierres": 4, "contenidos": 5}
    assert all(state == "acceso al panel verificado" for _, state in seed.verify_access(url, pilot, creds))

    with open_connection(url) as conn:
        assert conn.execute("select * from users where document_number = '123450'").fetchone() == real
        hashes = conn.execute("select password_hash from users where email like 'demo-presentacion.%'").fetchall()
        assert len(hashes) == 7 and all(h["password_hash"].startswith("$argon2") for h in hashes)
        assert all(pin not in h["password_hash"] for h in hashes for _, pin in CREDS.values())
        assert conn.execute("select count(*) as n from field_workers where account_id is not null").fetchone()["n"] == 2
        states = {r["status"]: r["n"] for r in conn.execute(
            "select status, count(*) as n from pickup_requests group by status").fetchall()}
        assert states == {"recolectada": 4, "programada": 2, "recibida": 2, "revision": 1, "cancelada": 1}
        # Puntos: un único movimiento por entrega, calculado por la regla vigente.
        points = {r["email"].split(".")[1].split("@")[0]: r["points_balance"] for r in conn.execute(
            "select email, points_balance from users where role = 'cliente' and email like 'demo-presentacion.%'")}
        assert points == {"vecino": 32 + 25 + 60, "unidad": 187}
        assert conn.execute("select count(*) as n from point_movements").fetchone()["n"] == 4
        badges = conn.execute("""
            select r.pickups from participation_recognitions r join users u on u.id = r.client_id
            where u.email = 'demo-presentacion.vecino@ecoconecta.invalid' order by 1
        """).fetchall()
        assert [b["pickups"] for b in badges] == [1, 3]
        assert conn.execute("select count(*) as n from content_entries where status = 'publicado'").fetchone()["n"] == 5
        assert conn.execute("select count(*) as n from rewards").fetchone()["n"] == 0

    # Segunda ejecución: no pide credenciales ni duplica nada.
    after_first = _snapshot(url)
    again, creds_again = seed.apply(url, pilot, credentials=lambda *a: pytest.fail("no debe pedir"),
                                    confirm=lambda r: True)
    assert again.created == {"perfiles": 0, "solicitudes": 0, "cierres": 0, "contenidos": 0}
    assert creds_again == {} and _snapshot(url) == after_first

    with TestClient(create_app(database_url=url, pilot_id=pilot)) as client:
        def session(key):
            doc, pin = CREDS[key]
            login = client.post("/accounts/login", json={"national_id": doc, "pin": pin})
            assert login.status_code == 200, key
            return {"Authorization": f"Bearer {login.json()['access_token']}"}

        h = {key: session(key) for key in CREDS}
        expected = {k: (p.api_role, p.flow) for k, p in seed.BY_KEY.items()}
        for key, headers in h.items():
            me = client.get("/accounts/me", headers=headers).json()
            assert (me["profile"]["role"], me["collective_flow"]) == expected[key], key

        # Paneles con datos: historial, puntos, insignias, bandejas, asignaciones y reportes.
        own = client.get("/community/collections", headers=h["vecino"]).json()
        assert len(own) == 6
        assert client.get("/community/points", headers=h["vecino"]).json()["balance"] == 117
        assert len(client.get("/community/points/movements", headers=h["vecino"]).json()) == 3
        assert client.get("/community/points/participation", headers=h["vecino"]).status_code == 200
        closed = next(c for c in own if c["status"] == "collected" and c.get("flow") == "organic")
        assert client.get(f"/community/collections/{closed['id']}/history", headers=h["vecino"]).status_code == 200
        assert client.get("/community/notifications", headers=h["vecino"]).json()
        assert len(client.get("/community/collections", headers=h["unidad"]).json()) == 4
        assert len(client.get("/recolecciones", headers=h["coord-huerta"]).json()) == 5
        assert len(client.get("/recolecciones", headers=h["coord-reciclaje"]).json()) == 5
        assert len(client.get("/recolecciones/asignadas", headers=h["huertero"]).json()) == 3
        assert len(client.get("/recolecciones/asignadas", headers=h["reciclador"]).json()) == 3
        now = datetime.now(BARRANQUILLA)
        report = client.get("/accounts/admin/reports", headers=h["admin"], params={
            "desde": (now - timedelta(days=1)).isoformat(), "hasta": (now + timedelta(days=1)).isoformat()})
        assert report.status_code == 200, report.text
        assert report.json()["recogidas_completadas"] == 4
        assert client.get("/content").json()

        # Flujo completo de huerta en vivo: pendiente → programar → cerrar por el huertero.
        pending = next(r for r in client.get("/recolecciones", headers=h["coord-huerta"],
                                             params={"estado": "recibida"}).json())
        worker = client.get("/recolecciones/recolectores", headers=h["coord-huerta"]).json()
        huertero = next(w for w in worker if w["full_name"] == "Huertero Ficticio Demo")
        cita = (now + timedelta(days=3)).replace(hour=16, minute=30, second=0, microsecond=0)
        scheduled = client.post(f"/recolecciones/{pending['id']}/programar", headers=h["coord-huerta"],
                                json={"cita": cita.isoformat(), "responsable": str(huertero["id"])})
        assert scheduled.status_code == 200, scheduled.text
        result = {"material": "ORGANICO", "kilos": "1.5", "resultado": "total",
                  "recogida_en": now.isoformat()}
        closed = client.post(f"/recolecciones/{pending['id']}/cerrar", headers=h["huertero"], json=result)
        assert closed.status_code == 200, closed.text
        assert client.post(f"/recolecciones/{pending['id']}/cerrar", headers=h["huertero"],
                           json=result).status_code == 200  # reintento idéntico: sin puntos dobles
        assert client.get("/community/points", headers=h["vecino"]).json()["balance"] == 117 + 15

        # Flujo completo de reciclaje en vivo: nueva solicitud del vecino → programar → cerrar.
        preferred = now + timedelta(days=4)
        created = client.post("/community/collections", headers={**h["vecino"], "Idempotency-Key": f"vivo-{uuid4()}"}, json={
            "flow": "recyclable", "description": "Botellas (prueba)", "address": "Dirección ficticia 123",
            "contact": "Contacto ficticio", "preferred_from": preferred.isoformat(),
            "preferred_until": (preferred + timedelta(hours=2)).isoformat()})
        assert created.status_code in (200, 201), created.text
        request_id = created.json()["id"]
        reciclador = next(w for w in client.get("/recolecciones/recolectores", headers=h["coord-reciclaje"]).json()
                          if w["full_name"] == "Reciclador Ficticio Demo")
        cita = (now + timedelta(days=5)).replace(hour=16, minute=30, second=0, microsecond=0)
        assert client.post(f"/recolecciones/{request_id}/programar", headers=h["coord-reciclaje"],
                           json={"cita": cita.isoformat(), "responsable": str(reciclador["id"])}).status_code == 200
        closed = client.post(f"/recolecciones/{request_id}/cerrar", headers=h["reciclador"], json={
            "material": "PET", "kilos": "2", "resultado": "total", "recogida_en": now.isoformat()})
        assert closed.status_code == 200, closed.text
        assert client.get("/community/points", headers=h["vecino"]).json()["balance"] == 117 + 15 + 30

        # La cita futura precargada también puede cerrarse en vivo por el reciclador.
        upcoming = next(r for r in client.get("/recolecciones/asignadas", headers=h["reciclador"]).json()
                        if r["estado"] == "programada" and r["id"] != request_id)
        closed = client.post(f"/recolecciones/{upcoming['id']}/cerrar", headers=h["reciclador"], json={
            "material": "PET", "kilos": "1", "resultado": "total", "recogida_en": now.isoformat()})
        assert closed.status_code == 200, closed.text

    # Tras la demo en vivo, una nueva ejecución sigue sin tocar nada.
    after_live = _snapshot(url)
    seed.apply(url, pilot, credentials=lambda *a: pytest.fail("no debe pedir"), confirm=lambda r: True)
    assert _snapshot(url) == after_live


def test_existing_demo_profile_with_other_role_blocks(pilot_db):
    url, pilot = pilot_db
    _rules(url)
    with open_connection(url) as conn:
        conn.execute("""
            insert into users (pilot_id, email, document_number, full_name, role, password_hash)
            values (%s, 'demo-presentacion.vecino@ecoconecta.invalid', '777777', 'Otro', 'admin', 'x')
        """, (pilot,))
    report = seed.check(url, pilot)
    assert any("Vecino" in b and "no se modifica" in b for b in report.blockers)
