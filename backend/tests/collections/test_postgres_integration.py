"""Verify the configured HTTP app against a separate PostgreSQL schema."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo
from pwdlib import PasswordHash

from backend.app.main import create_app
from db.connection import open_connection
from db.migrate import migrate


@pytest.fixture
def environment():
    base = os.environ.get("TEST_DATABASE_URL")
    if not base:
        pytest.skip("TEST_DATABASE_URL is required")
    schema = sql.Identifier(f"ec_http_{uuid4().hex}")
    with open_connection(base) as conn:
        conn.execute(sql.SQL("create schema {}").format(schema))
    url = make_conninfo(base, options=f"-c search_path={schema.as_string()}")
    try:
        migrate(url)
        pilot, leader, admin, other_leader, worker, material, reward = (uuid4() for _ in range(7))
        password_hash = PasswordHash.recommended().hash("1234")
        with open_connection(url) as conn:
            conn.execute("insert into pilots (id, name, city) values (%s, 'Prueba', 'Barranquilla')",
                         (pilot,))
            collectives = conn.execute("""
                insert into collectives (pilot_id, flow) values (%s, 'huerta'), (%s, 'reciclaje')
                returning id, flow
            """, (pilot, pilot)).fetchall()
            ids = {row["flow"]: row["id"] for row in collectives}
            for id_, document, role, collective in (
                (leader, "10001", "lider", ids["huerta"]),
                (admin, "10002", "admin", None),
                (other_leader, "10003", "lider", ids["reciclaje"]),
            ):
                conn.execute("""
                    insert into users
                        (id, pilot_id, email, document_number, full_name, role, password_hash, collective_id)
                    values (%s, %s, %s, %s, 'Perfil de prueba', %s, %s, %s)
                """, (id_, pilot, f"{id_}@example.invalid", document, role, password_hash, collective))
            conn.execute("""
                insert into field_workers (id, pilot_id, full_name) values (%s, %s, 'Equipo de huerta')
            """, (worker, pilot))
            conn.execute("""
                insert into collection_shifts (collective_id, pilot_id, worker_id, starts_at, ends_at)
                values (%s, %s, %s, now() - interval '1 day', now() + interval '7 days')
            """, (ids["huerta"], pilot, worker))
            conn.execute("insert into materials (id,code,name) values (%s, 'ORG', 'Orgánico')",
                         (material,))
            conn.execute("insert into rewards (id,pilot_id,code,name,points_cost,stock) "
                         "values (%s,%s,'P-1','Plántula',15,2)", (reward, pilot))
        with TestClient(create_app(database_url=url, pilot_id=pilot)) as client:
            yield client, url, pilot, reward
    finally:
        with open_connection(base) as conn:
            conn.execute(sql.SQL("drop schema {} cascade").format(schema))


def login(client, document, pin="1234"):
    response = client.post("/accounts/login", json={"national_id": document, "pin": pin})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def register(client, document, kind="household"):
    response = client.post("/accounts", json={
        "national_id": document, "full_name": "Persona de prueba", "address": "Calle 123",
        "phone": "3000000000", "pin": "1234", "kind": kind,
    })
    assert response.status_code == 201, response.text
    return response.json()["id"], login(client, document)


def test_request_to_redemption_with_retry_and_rollback(environment):
    client, url, _, reward = environment
    owner_id, owner = register(client, "101")
    _, other = register(client, "102")
    leader = login(client, "10001")
    other_leader = login(client, "10003")
    start = datetime.now(timezone.utc) + timedelta(days=1)
    form = {
        "flow": "organic", "description": "Restos de frutas y verduras",
        "address": "Calle 123", "contact": "3000000000",
        "preferred_from": start.isoformat(),
        "preferred_until": (start + timedelta(hours=2)).isoformat(),
    }
    headers = {**owner, "Idempotency-Key": "solicitud-1"}

    def submit():
        return client.post("/community/collections", headers=headers, json=form)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: submit(), range(2)))
    assert [r.status_code for r in responses] == [201, 201], [r.text for r in responses]
    request_id = responses[0].json()["id"]
    assert responses[1].json()["id"] == request_id
    assert client.post("/community/collections", headers=headers,
                       json={**form, "description": "Otros residuos"}).status_code == 409
    base = f"/recolecciones/{request_id}"
    assert client.get(f"/community/collections/{request_id}", headers=other).status_code == 404
    assert client.get(base + "/historial", headers=other_leader).status_code == 404
    assert client.get("/recolecciones", headers=other_leader).json() == []
    assert len(client.get("/community/notifications", headers=owner).json()) == 1

    appointment = {"cita": start.isoformat()}
    scheduled = client.post(base + "/programar", headers=leader, json=appointment)
    assert scheduled.status_code == 200, scheduled.text
    own = client.get("/community/appointments", headers=owner).json()
    assert own[0]["responsible_name"] == "Equipo de huerta"
    assert own[0]["scheduled_at"].endswith("-05:00")
    assert client.get("/community/appointments", headers=other).json() == []
    failed = client.post(base + "/visita-fallida", headers=leader, json={"motivo": "Visita sin acceso"})
    assert failed.status_code == 200, failed.text
    assert client.get("/community/appointments", headers=owner).json() == []
    assert client.post(base + "/programar", headers=leader, json=appointment).status_code == 200
    delivery = {"material": "ORG", "kilos": "2.5", "resultado": "parcial"}
    # Missing points rules fail after the state and delivery writes have started.
    rejected = client.post(base + "/cerrar", headers=leader, json=delivery)
    assert rejected.status_code == 409, rejected.text
    assert client.get(f"/community/collections/{request_id}", headers=owner).json()["status"] == "scheduled"
    assert [e["evento"] for e in client.get(base + "/historial", headers=leader).json()] == [
        "recibida", "programada", "visita_fallida", "programada",
    ]
    with open_connection(url) as conn:
        assert conn.execute("select count(*) as n from deliveries").fetchone()["n"] == 0
        assert conn.execute("select count(*) as n from point_movements").fetchone()["n"] == 0
        conn.execute("""
            insert into point_rules (material_id, points_per_kg, valid_from)
            select id, 10, now() - interval '1 day' from materials where code = 'ORG'
        """)

    def close():
        return client.post(base + "/cerrar", headers=leader, json=delivery)

    with ThreadPoolExecutor(max_workers=2) as pool:
        closed = list(pool.map(lambda _: close(), range(2)))
    assert [r.status_code for r in closed] == [200, 200], [r.text for r in closed]
    assert closed[0].json() == closed[1].json()
    assert client.get("/community/points", headers=owner).json() == {"balance": 25}
    assert client.get("/community/points", headers=other).json() == {"balance": 0}
    assert client.get("/community/notifications", headers=other).json() == []
    assert len(client.get("/community/points/movements", headers=owner).json()) == 1

    direct = {"cliente": owner_id, "clave": "directa-1", **delivery}

    def deliver_direct():
        return client.post("/recolecciones/directas", headers=leader, json=direct)

    with ThreadPoolExecutor(max_workers=2) as pool:
        direct_results = list(pool.map(lambda _: deliver_direct(), range(2)))
    assert [r.status_code for r in direct_results] == [200, 200], [r.text for r in direct_results]
    assert direct_results[0].json() == direct_results[1].json()
    assert client.get("/community/points", headers=owner).json() == {"balance": 50}
    assert client.put(f"/recolecciones/existencias/{reward}", headers=leader,
                      json={"cantidad": 1}).status_code == 200
    assert client.post("/community/redemptions", headers=other,
                       json={"reward_id": str(reward)}).status_code == 409
    issued = client.post("/community/redemptions", headers=owner, json={"reward_id": str(reward)})
    assert issued.status_code == 201, issued.text
    code = issued.json()["code"]
    assert client.get("/community/points", headers=owner).json() == {"balance": 50}
    assert client.post("/recolecciones/canjes/confirmar", headers=other_leader,
                       json={"codigo": code}).status_code == 403

    def confirm():
        return client.post("/recolecciones/canjes/confirmar", headers=leader, json={"codigo": code})

    with ThreadPoolExecutor(max_workers=2) as pool:
        confirmed = list(pool.map(lambda _: confirm(), range(2)))
    assert [r.status_code for r in confirmed] == [200, 200], [r.text for r in confirmed]
    assert confirmed[0].json() == confirmed[1].json()
    assert client.get("/community/points", headers=owner).json() == {"balance": 35}
    assert client.get("/community/rewards").json() == []
    with open_connection(url) as conn:
        assert conn.execute("select count(*) as n from redemptions").fetchone()["n"] == 1
        assert conn.execute("select count(*) as n from reward_stock_audit").fetchone()["n"] == 1


def test_accounts_business_authorization_sessions_and_content(environment):
    client, url, pilot, _ = environment
    business_id, business = register(client, "203", "business")
    admin = login(client, "10002")
    start = datetime.now(timezone.utc) + timedelta(days=1)
    form = {
        "residuo": "organico", "material": "Compost", "contacto": "3000000000",
        "direccion": "Calle 123", "generador": "hogar", "disponibilidad": start.isoformat(),
    }
    headers = {**business, "Idempotency-Key": "empresa-1"}
    assert client.post("/recolecciones", headers=headers, json=form).status_code == 403
    authorized = client.put(f"/accounts/admin/{business_id}/authorization", headers=admin, json={
        "role": "business", "pilot_enabled": True, "collective_id": None,
    })
    assert authorized.status_code == 200, authorized.text
    request = client.post("/recolecciones", headers=headers, json=form)
    assert request.status_code == 200, request.text
    assert request.json()["solicitud"]["generador"] == "unidad_productiva"
    with TestClient(create_app(database_url=url, pilot_id=pilot)) as restarted:
        assert restarted.get("/accounts/me", headers=business).json()["id"] == business_id
        assert restarted.post("/accounts/logout", headers=business).status_code == 204
    assert client.get("/accounts/me", headers=business).status_code == 401
    with open_connection(url) as conn:
        token = business["Authorization"].removeprefix("Bearer ")
        assert conn.execute("select 1 from account_sessions where token_digest = %s",
                            (token,)).fetchone() is None
    for _ in range(5):
        refused = client.post("/accounts/login", json={"national_id": "203", "pin": "0000"})
        assert refused.status_code == 401, refused.text
    assert client.post("/accounts/login", json={"national_id": "203", "pin": "1234"}).status_code == 429

    response = client.post("/content/admin", headers=admin, json={
        "title": "Separación en casa", "body": "Separar el cartón seco.", "category": "separation",
    })
    assert response.status_code == 201, response.text
    content_id = response.json()["id"]
    assert client.get("/content").json() == []
    assert client.post(f"/content/admin/{content_id}/publish", headers=admin).status_code == 200
    assert client.get(f"/content/{content_id}").json()["status"] == "published"
    assert [x["id"] for x in client.get("/content?category=separation").json()] == [content_id]
