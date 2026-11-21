"""db.prepare_demo contra PostgreSQL real en un esquema temporal."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from backend.app.main import create_app
from db.connection import open_connection
from db.initialize_collectives import initialize
from db.migrate import migrate
from db.prepare_demo import prepare


@pytest.fixture
def local_pilot():
    base = os.environ.get("TEST_DATABASE_URL")
    if not base:
        pytest.skip("TEST_DATABASE_URL is required")
    schema = sql.Identifier(f"ec_demo_{uuid4().hex}")
    with open_connection(base) as conn:
        conn.execute(sql.SQL("create schema {}").format(schema))
    url = make_conninfo(base, options=f"-c search_path={schema.as_string()}")
    try:
        migrate(url)
        pilot = uuid4()
        initialize(url, pilot, create_pilot=True)
        yield url, pilot
    finally:
        with open_connection(base) as conn:
            conn.execute(sql.SQL("drop schema {} cascade").format(schema))


def test_prepare_demo_creates_seven_profiles_once_and_they_log_in(local_pilot):
    url, pilot = local_pilot
    pins = {}
    report = prepare(url, pilot, create=True, show=lambda label, doc, pin: pins.setdefault(doc, pin))
    assert {r[0] for r in report.rows} == {
        "Vecino", "Coordinadora de huerteros", "Coordinadora de recicladores",
        "Unidad productiva", "Huertero", "Reciclador", "Administrador"}
    # Sin reglas de puntos vigentes el comando lo reporta como bloqueo, sin inventarlas.
    assert report.blockers == [
        "No hay reglas de puntos vigentes: el administrador debe configurarlas en «Reglas de puntos»"]
    assert set(pins) == {"40001", "50001", "60001", "70001"}

    with open_connection(url) as conn:
        before = conn.execute("select count(*) as n from users").fetchone()["n"]
    again = prepare(url, pilot, create=True, show=lambda *a: pytest.fail("no debe generar PIN nuevos"))
    with open_connection(url) as conn:
        assert conn.execute("select count(*) as n from users").fetchone()["n"] == before
        assert conn.execute("select count(*) as n from field_workers where account_id is not null").fetchone()["n"] == 2
    assert all("creada" not in r[3] for r in again.rows)

    expected = {"10001": ("resident", None), "20001": ("leader", "huerta"), "30001": ("leader", "reciclaje"),
                "40001": ("business", None), "50001": ("field_worker", "huerta"),
                "60001": ("field_worker", "reciclaje"), "70001": ("admin", None)}
    with TestClient(create_app(database_url=url, pilot_id=pilot)) as client:
        for doc, (role, flow) in expected.items():
            login = client.post("/accounts/login", json={"national_id": doc, "pin": pins.get(doc, "1234")})
            assert login.status_code == 200, doc
            me = client.get("/accounts/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}).json()
            assert me["profile"]["role"] == role and me["collective_flow"] == flow, doc
            if role in ("resident", "business"):
                assert me["profile"]["pilot_enabled"] is True
            if role == "field_worker":
                assert me["worker_id"]


def test_prepare_demo_never_modifies_existing_documented_accounts(local_pilot):
    url, pilot = local_pilot
    with open_connection(url) as conn:
        conn.execute("""
            insert into users (pilot_id, email, document_number, full_name, role, password_hash)
            values (%s, 'x@example.invalid', '20001', 'Otra persona', 'admin', 'sin-pin')
        """, (pilot,))
    report = prepare(url, pilot, create=False, show=lambda *a: None)
    assert any("20001" in b and "no se modifica" in b for b in report.blockers)
    with open_connection(url) as conn:
        row = conn.execute("select role, full_name from users where document_number = '20001'").fetchone()
    assert (row["role"], row["full_name"]) == ("admin", "Otra persona")


def test_prepare_demo_refuses_non_local_database():
    with pytest.raises(SystemExit):
        prepare("postgresql://user@db.example.com/eco", uuid4(), create=True, show=lambda *a: None)
