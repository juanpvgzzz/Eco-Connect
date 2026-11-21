"""Verify the configured HTTP app against a separate PostgreSQL schema."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo
from pwdlib import PasswordHash

from backend.app.main import create_app
from backend.app.community.postgres import _notice
from db.connection import open_connection
from db.initialize_collectives import initialize
from db.migrate import migrate
from db.operations import close_pickup
from db.provision_admin import provision


def test_notification_keeps_the_scheduled_instant_separate_from_its_text():
    row = {
        "id": uuid4(), "client_id": uuid4(), "kind": "programada",
        "snapshot": {"cita": "2026-12-01T03:30:00Z", "nombre_responsable": "Equipo de prueba"},
        "message": None, "reason": None, "created_at": datetime(2026, 11, 20, tzinfo=timezone.utc),
    }
    notice = _notice(row)
    assert notice.scheduled_at.isoformat() == "2026-11-30T22:30:00-05:00"
    assert notice.message == "Recolección programada. Equipo de prueba"


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
                insert into field_workers (id, pilot_id, full_name, collective_id)
                values (%s, %s, 'Equipo de huerta', %s)
            """, (worker, pilot, ids["huerta"]))
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


def register(client, document, kind="household", pilot=True):
    response = client.post("/accounts", json={
        "national_id": document, "full_name": "Persona de prueba", "address": "Calle 123",
        "phone": "3000000000", "pin": "1234", "kind": kind,
    })
    assert response.status_code == 201, response.text
    account_id = response.json()["id"]
    if kind == "household" and pilot:
        # RN-08: simula la preselección del hogar por administración (probada en
        # test_rn08_household_requires_admin_pilot_enablement).
        with open_connection(client.app.state.account_store.url) as conn:
            conn.execute("update users set pilot_enabled = true where id = %s", (account_id,))
    return account_id, login(client, document)


def test_rn08_household_requires_admin_pilot_enablement(environment):
    """RN-08: un hogar nuevo no participa hasta que administración lo habilita y
    deja de participar si se deshabilita; solo administración puede cambiarlo."""
    client, _, _, _ = environment
    household_id, household = register(client, "70001", pilot=False)
    _, other = register(client, "70002")
    admin = login(client, "10002")
    form = {"residuo": "reciclable", "material": "Cartón", "contacto": "3000000000",
            "direccion": "Calle 123", "generador": "hogar", "disponibilidad": "Tardes"}
    me = client.get("/accounts/me", headers=household).json()
    assert me["profile"]["pilot_enabled"] is False
    refused = client.post("/recolecciones", headers={**household, "Idempotency-Key": "rn08-1"}, json=form)
    assert refused.status_code == 403 and refused.json() == {"detail": "Cliente fuera del piloto"}
    # Nadie distinto de administración puede habilitarlo (ni el propio hogar).
    for actor in (household, other):
        assert client.put(f"/accounts/admin/{household_id}/authorization", headers=actor, json={
            "role": "resident", "pilot_enabled": True, "collective_id": None}).status_code == 403
    enabled = client.put(f"/accounts/admin/{household_id}/authorization", headers=admin, json={
        "role": "resident", "pilot_enabled": True, "collective_id": None})
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["profile"]["pilot_enabled"] is True
    created = client.post("/recolecciones", headers={**household, "Idempotency-Key": "rn08-2"}, json=form)
    assert created.status_code == 200, created.text
    assert client.put(f"/accounts/admin/{household_id}/authorization", headers=admin, json={
        "role": "resident", "pilot_enabled": False, "collective_id": None}).status_code == 200
    assert client.post("/recolecciones", headers={**household, "Idempotency-Key": "rn08-3"},
                       json={**form, "material": "Papel"}).status_code == 403
    listed = client.get("/accounts/admin/users", headers=admin, params={"role": "resident"}).json()
    assert {u["id"]: u["pilot_enabled"] for u in listed}[household_id] is False


def test_local_admin_and_two_coordinator_inboxes(environment):
    _, url, _, _ = environment
    pilot = uuid4()
    assert initialize(url, pilot, create_pilot=True) == 2
    assert initialize(url, pilot, create_pilot=True) == 0
    admin_id = provision(url, pilot, "20001", "Administración local", "582491")
    with pytest.raises(SystemExit, match="Ya existe"):
        provision(url, pilot, "20002", "Otro perfil", "837296")

    with TestClient(create_app(database_url=url, pilot_id=pilot)) as client:
        admin = login(client, "20001", pin="582491")
        profile = client.get("/accounts/me", headers=admin).json()
        assert profile["id"] == str(admin_id) and profile["profile"]["role"] == "admin"
        collectives = {
            row["flow"]: row["id"]
            for row in client.get("/accounts/admin/collectives", headers=admin).json()
        }
        _, resident = register(client, "20003")
        assert client.get("/accounts/admin/users", headers=resident).status_code == 403
        assert client.get("/recolecciones", headers=resident).status_code == 403
        sessions = {}
        requests = {}
        for document, flow, residue in (
            ("20004", "huerta", "organico"),
            ("20005", "reciclaje", "reciclable"),
        ):
            coordinator, _ = register(client, document)
            path = f"/accounts/admin/{coordinator}/authorization"
            body = {"role": "leader", "collective_id": collectives[flow], "pilot_enabled": False}
            assert client.put(path, headers=resident, json=body).status_code == 403
            response = client.put(path, headers=admin, json=body)
            assert response.status_code == 200, response.text
            sessions[flow] = login(client, document)
            response = client.post(
                "/recolecciones", headers={**resident, "Idempotency-Key": flow},
                json={"residuo": residue, "material": "Material de prueba", "contacto": "3000000000",
                      "direccion": "Calle 123", "generador": "hogar", "disponibilidad": "Mañana"},
            )
            assert response.status_code == 200, response.text
            requests[flow] = response.json()["id"]

        path = f"/recolecciones/{requests['huerta']}/revisar"
        assert client.post(path, headers=sessions["huerta"]).status_code == 200
        boundary = "2026-11-21T00:00:00-05:00"
        with open_connection(url) as conn:
            conn.execute("update pickup_requests set created_at = %s where pilot_id = %s", (boundary, pilot))
        period = {"desde": boundary, "hasta": "2026-11-22T00:00:00-05:00"}
        for actor in (resident, admin):
            assert client.get("/recolecciones/resumen", headers=actor, params=period).status_code == 403

    with TestClient(create_app(database_url=url, pilot_id=pilot)) as restarted:
        for flow, other in (("huerta", "reciclaje"), ("reciclaje", "huerta")):
            headers = sessions[flow]
            identity = restarted.get("/accounts/me", headers=headers).json()
            assert identity["profile"]["role"] == "leader" and identity["collective_flow"] == flow
            inbox = restarted.get("/recolecciones", headers=headers).json()
            assert [row["id"] for row in inbox] == [requests[flow]]
            summary = restarted.get("/recolecciones/resumen", headers=headers, params=period)
            assert summary.status_code == 200, summary.text
            assert summary.json()["flujo"] == flow
            assert summary.json()["conteos"] == {
                "recibida": int(flow == "reciclaje"), "revision": int(flow == "huerta"),
                "programada": 0, "recolectada": 0, "cancelada": 0,
            }
            excluded = restarted.get("/recolecciones/resumen", headers=headers, params={
                "desde": "2026-11-20T00:00:00-05:00", "hasta": boundary,
            })
            assert excluded.status_code == 200, excluded.text
            assert sum(excluded.json()["conteos"].values()) == 0
            path = f"/recolecciones/{requests[other]}"
            assert restarted.get(path + "/historial", headers=headers).status_code == 404
            assert restarted.post(path + "/revisar", headers=headers).status_code == 404


def test_request_to_redemption_with_retry_and_rollback(environment):
    client, url, _, reward = environment
    owner_id, owner = register(client, "101")
    _, other = register(client, "102")
    leader = login(client, "10001")
    admin = login(client, "10002")
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

    with open_connection(url) as conn:
        worker = conn.execute("select id from field_workers where full_name = 'Equipo de huerta'").fetchone()["id"]
    appointment = {"cita": start.isoformat(), "responsable": str(worker)}
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
    delivery = {"material": "ORG", "kilos": "2.5", "resultado": "parcial",
                "recogida_en": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                "constancia": "Llamada del recolector"}
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
    participation = client.get("/community/points/participation", headers=owner).json()
    assert participation["completed"] == 1
    assert [m["pickups"] for m in participation["milestones"] if m["unlocked_at"]] == [1]
    assert client.get("/community/points/participation", headers=other,
                      params={"owner_id": owner_id}).json()["completed"] == 0

    # La entrega directa no tiene cita ni recolector asignado: solo material y peso.
    base_delivery = {k: v for k, v in delivery.items() if k not in ("recogida_en", "constancia")}
    direct = {"cliente": owner_id, "clave": "directa-1", **base_delivery}

    def deliver_direct():
        return client.post("/recolecciones/directas", headers=leader, json=direct)

    with ThreadPoolExecutor(max_workers=2) as pool:
        direct_results = list(pool.map(lambda _: deliver_direct(), range(2)))
    assert [r.status_code for r in direct_results] == [200, 200], [r.text for r in direct_results]
    assert direct_results[0].json() == direct_results[1].json()
    assert client.get("/community/points", headers=owner).json() == {"balance": 50}
    assert client.get("/community/points/participation", headers=owner).json() == participation
    assert client.get("/community/rewards").json() == []
    reward_path = f"/community/admin/rewards/{reward}"
    reward_form = {"title": "Premio de prueba", "description": "Solo para pruebas", "cost": 15,
                   "stock": 2, "active": True, "validated": True}
    assert client.get("/community/admin/rewards", headers=owner).status_code == 403
    assert client.post("/community/admin/rewards", headers=leader, json=reward_form).status_code == 403
    draft = client.post("/community/admin/rewards", headers=admin, json={
        **reward_form, "title": "Propuesta de prueba", "active": False, "validated": False,
    })
    assert draft.status_code == 201, draft.text
    assert client.get("/community/rewards").json() == []
    assert client.post("/community/redemptions", headers=owner,
                       json={"reward_id": draft.json()["id"]}).status_code == 404
    assert client.post("/community/redemptions", headers=owner, json={"reward_id": str(reward)}).status_code == 404
    assert client.put(reward_path, headers=leader, json=reward_form).status_code == 403
    assert client.put(reward_path, headers=admin, json=reward_form).status_code == 200
    assert client.put(f"/recolecciones/existencias/{reward}", headers=leader,
                      json={"cantidad": 1}).status_code == 403
    assert client.put(f"/recolecciones/existencias/{reward}", headers=admin,
                      json={"cantidad": 1}).status_code == 200
    assert client.post("/community/redemptions", headers=other,
                       json={"reward_id": str(reward)}).status_code == 409
    def issue():
        return client.post("/community/redemptions", headers=owner, json={"reward_id": str(reward)})

    with ThreadPoolExecutor(max_workers=2) as pool:
        issued = list(pool.map(lambda _: issue(), range(2)))
    assert [r.status_code for r in issued] == [201, 201], [r.text for r in issued]
    assert issued[0].json() == issued[1].json()
    code = issued[0].json()["code"]
    assert client.get("/community/points", headers=owner).json() == {"balance": 50}
    assert client.post("/recolecciones/canjes/confirmar", headers=other,
                       json={"codigo": code}).status_code == 403
    assert client.post("/recolecciones/canjes/confirmar", headers=other_leader,
                       json={"codigo": code}).status_code == 403
    reconfigured = client.put(reward_path, headers=admin, json={
        **reward_form, "stock": None, "description": "Condiciones revisadas de prueba",
    })
    assert reconfigured.status_code == 200, reconfigured.text
    assert reconfigured.json()["stock"] == 1
    assert client.post("/recolecciones/canjes/confirmar", headers=leader,
                       json={"codigo": code}).status_code == 409
    new_code = issue()
    assert new_code.status_code == 201, new_code.text
    assert new_code.json()["code"] != code
    code = new_code.json()["code"]

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
        assert conn.execute("select count(*) as n from reward_stock_audit where reward_id = %s", (reward,)).fetchone()["n"] == 1


def test_all_participation_milestones_persist_and_ignore_unclosed_requests(environment):
    client, url, pilot, _ = environment
    owner_id, owner = register(client, "50001")
    with open_connection(url) as conn, conn.transaction():
        leader = conn.execute("select id from users where document_number = '10001'").fetchone()["id"]
        worker = conn.execute("select id from field_workers").fetchone()["id"]
        material = conn.execute("select id from materials where code = 'ORG'").fetchone()["id"]
        conn.execute("insert into point_rules (material_id, points_per_kg, valid_from) values (%s, 10, now())", (material,))
        conn.execute("""
            insert into pickup_requests (client_id, pilot_id, address, status)
            select %s, %s, 'Calle de prueba', status
            from (values ('cancelada'), ('recibida')) as pending(status)
        """, (owner_id, pilot))
        requests = []
        for step in range(20):
            row = conn.execute("""
                insert into pickup_requests (client_id, pilot_id, address, status)
                values (%s, %s, 'Calle de prueba', 'programada') returning id
            """, (owner_id, pilot)).fetchone()["id"]
            start = datetime(2026, 5, 1, tzinfo=timezone.utc) + timedelta(days=step)
            slot = conn.execute("""
                insert into pickup_slots (pilot_id, starts_at, ends_at)
                values (%s, %s, %s) returning id
            """, (pilot, start, start + timedelta(hours=1))).fetchone()["id"]
            conn.execute("""
                insert into pickup_appointments (request_id, pilot_id, slot_id, leader_id, worker_id)
                values (%s, %s, %s, %s, %s)
            """, (row, pilot, slot, leader, worker))
            requests.append(row)

    path = "/community/points/participation"
    assert client.get(path).status_code == 401
    initial = client.get(path, headers=owner).json()
    assert initial["completed"] == 0
    assert [m["pickups"] for m in initial["milestones"]] == [1, 3, 5, 10, 20]
    assert all(m["unlocked_at"] is None for m in initial["milestones"])

    def close(row):
        return close_pickup(url, row, leader, worker, [{"material_id": str(material), "weight_kg": "1"}])

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(result[1] == 10 for result in pool.map(close, requests + requests[:2]))
    result = client.get(path, headers=owner).json()
    assert result["completed"] == 20
    assert all(m["unlocked_at"] for m in result["milestones"])
    assert client.get("/community/points", headers=owner).json() == {"balance": 200}
    with open_connection(url) as conn:
        assert conn.execute("select count(*) n from participation_recognitions where client_id = %s",
                            (owner_id,)).fetchone()["n"] == 5
    with TestClient(create_app(database_url=url, pilot_id=pilot)) as restarted:
        assert restarted.get(path, headers=owner).json() == result
        assert restarted.get("/community/points", headers=owner).json() == {"balance": 200}


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


def test_manual_assignment_and_programming_by_collective(environment):
    """Fase 2 contra PostgreSQL real: integrantes sin cuenta, asignación manual por
    colectivo, programación con fecha/hora/responsable, auditoría y vista del vecino."""
    _, url, _, _ = environment
    pilot = uuid4()
    initialize(url, pilot, create_pilot=True)
    provision(url, pilot, "30001", "Administración", "582491")
    bogota = ZoneInfo("America/Bogota")
    future = (datetime.now(bogota) + timedelta(days=3)).replace(second=0, microsecond=0)
    when = {"huerta": future.replace(hour=8, minute=30), "reciclaje": future.replace(hour=22, minute=30)}

    with TestClient(create_app(database_url=url, pilot_id=pilot)) as client:
        admin = login(client, "30001", pin="582491")
        collectives = {row["flow"]: row["id"] for row in client.get("/accounts/admin/collectives", headers=admin).json()}
        _, resident = register(client, "30002")
        coordinators, ids, members, requests = {}, {}, {}, {}
        for document, flow, residue, name in (
            ("30003", "huerta", "organico", "Hugo Huertero"),
            ("30004", "reciclaje", "reciclable", "Rosa Recicladora"),
        ):
            ids[flow], _ = register(client, document)
            body = {"role": "leader", "collective_id": collectives[flow], "pilot_enabled": False}
            assert client.put(f"/accounts/admin/{ids[flow]}/authorization", headers=admin, json=body).status_code == 200
            coordinators[flow] = login(client, document)
            created = client.post("/recolecciones/recolectores", headers=coordinators[flow], json={"nombre": name})
            assert created.status_code == 201, created.text
            members[flow] = created.json()["id"]
            response = client.post(
                "/recolecciones", headers={**resident, "Idempotency-Key": "fase2-" + flow},
                json={"residuo": residue, "material": f"Material {flow}", "contacto": "3000000000",
                      "direccion": "Manzana 1, Casa 2", "generador": "hogar", "disponibilidad": "Lunes · Mañana"},
            )
            assert response.status_code == 200, response.text
            requests[flow] = response.json()["id"]

        garden, recycling = coordinators["huerta"], coordinators["reciclaje"]
        # Cada coordinadora ve solo los integrantes y solicitudes de su colectivo.
        assert [m["id"] for m in client.get("/recolecciones/recolectores", headers=garden).json()] == [members["huerta"]]
        assert [r["id"] for r in client.get("/recolecciones", headers=garden).json()] == [requests["huerta"]]
        assert [r["id"] for r in client.get("/recolecciones", headers=recycling).json()] == [requests["reciclaje"]]

        organic = f"/recolecciones/{requests['huerta']}"
        at = when["huerta"].isoformat()
        # No se puede asignar un integrante de otro colectivo.
        assert client.post(organic + "/programar", headers=garden,
                           json={"cita": at, "responsable": members["reciclaje"]}).status_code == 422
        # No se puede programar sin responsable, sin fecha o sin hora.
        assert client.post(organic + "/programar", headers=garden, json={"cita": at}).status_code == 422
        assert client.post(organic + "/programar", headers=garden, json={"responsable": members["huerta"]}).status_code == 422
        assert client.post(organic + "/programar", headers=garden,
                           json={"cita": when["huerta"].date().isoformat(), "responsable": members["huerta"]}).status_code == 422
        assert client.get(f"/community/collections/{requests['huerta']}", headers=resident).json()["status"] == "received"
        # Sin autorización: vecino, la otra coordinadora y gestión de integrantes ajenos.
        assert client.post(organic + "/programar", headers=resident,
                           json={"cita": at, "responsable": members["huerta"]}).status_code == 403
        assert client.post(organic + "/programar", headers=recycling,
                           json={"cita": at, "responsable": members["reciclaje"]}).status_code == 404
        assert client.get("/recolecciones/recolectores", headers=resident).status_code == 403
        assert client.patch(f"/recolecciones/recolectores/{members['huerta']}", headers=recycling,
                            json={"activo": False}).status_code == 404
        # El aviso al recolector solo se registra cuando ya está programada.
        assert client.post(organic + "/aviso-recolector", headers=garden, json={"canal": "llamada"}).status_code == 409

        for flow, headers in (("huerta", garden), ("reciclaje", recycling)):
            path = f"/recolecciones/{requests[flow]}"
            scheduled = client.post(path + "/programar", headers=headers,
                                    json={"cita": when[flow].isoformat(), "responsable": members[flow]})
            assert scheduled.status_code == 200, scheduled.text
            assert scheduled.json()["estado"] == "programada"
            noted = client.post(path + "/aviso-recolector", headers=headers,
                                json={"canal": "whatsapp", "nota": "Confirmó la hora"})
            assert noted.status_code == 200, noted.text

    # Persistencia: una instancia nueva de la API lee lo guardado en PostgreSQL.
    with TestClient(create_app(database_url=url, pilot_id=pilot)) as restarted:
        names = {"huerta": "Hugo Huertero", "reciclaje": "Rosa Recicladora"}
        for flow, headers in (("huerta", garden), ("reciclaje", recycling)):
            row = restarted.get("/recolecciones", headers=headers).json()[0]
            assert (row["estado"], row["responsable"], row["nombre_responsable"]) == ("programada", members[flow], names[flow])
            assert row["programada_por"] == ids[flow]
            assert datetime.fromisoformat(row["cita"]).astimezone(bogota) == when[flow]
            history = restarted.get(f"/recolecciones/{requests[flow]}/historial", headers=headers).json()
            assignment = next(e for e in history if e["evento"] == "programada")
            assert assignment["autora"] == ids[flow] and assignment["fecha"]
            assert assignment["registro"]["responsable"] == members[flow]
            assert assignment["registro"]["nombre_responsable"] == names[flow]
            notice = next(e for e in history if e["evento"] == "aviso_recolector")
            assert notice["motivo"] == "WhatsApp: Confirmó la hora" and notice["autora"] == ids[flow]
        # El vecino ve ambas programaciones confirmadas, sin la comunicación interna.
        own = restarted.get("/community/appointments", headers=resident).json()
        assert sorted(a["responsible_name"] for a in own) == ["Hugo Huertero", "Rosa Recicladora"]
        assert {a["collection_id"]: a["scheduled_at"] for a in own} == {
            requests[flow]: at.isoformat() for flow, at in when.items()
        }
        notices = restarted.get("/community/notifications", headers=resident).json()
        assert not any("recolector registrado" in n["title"] for n in notices)
        assert sum(n["title"] == "Recolección programada" for n in notices) == 2
        assert {n["scheduled_at"] for n in notices if n["title"] == "Recolección programada"} == {
            at.isoformat() for at in when.values()
        }

    with open_connection(url) as conn:
        rows = conn.execute("""
            select a.leader_id, a.worker_id, a.created_at, w.account_id, s.starts_at
            from pickup_appointments a join field_workers w on w.id = a.worker_id
            join pickup_slots s on s.id = a.slot_id
            where a.pilot_id = %s order by w.full_name
        """, (pilot,)).fetchall()
        assert [(str(r["leader_id"]), str(r["worker_id"])) for r in rows] == [
            (ids["huerta"], members["huerta"]), (ids["reciclaje"], members["reciclaje"]),
        ]
        assert all(r["created_at"] and r["account_id"] is None for r in rows)
        assert [r["starts_at"].astimezone(bogota) for r in rows] == [when["huerta"], when["reciclaje"]]


def test_full_cycle_close_history_and_points_per_collective(environment):
    """Fase 3 contra PostgreSQL real: solicitud → asignación → programación →
    cierre trazado → puntos, para orgánicos y reciclables por separado."""
    _, url, _, _ = environment
    pilot = uuid4()
    initialize(url, pilot, create_pilot=True)
    provision(url, pilot, "40001", "Administración", "582491")
    with open_connection(url) as conn:
        # Reglas parametrizables de prueba (no son equivalencias oficiales).
        for code, name, per_kg in (("ORG-F3", "Orgánico mixto", 10), ("PET-F3", "Plástico PET", 4)):
            material = conn.execute("insert into materials (code, name) values (%s, %s) returning id", (code, name)).fetchone()["id"]
            conn.execute("insert into point_rules (material_id, points_per_kg, valid_from) values (%s, %s, now() - interval '1 day')",
                         (material, per_kg))
    soon = datetime.now(timezone.utc) + timedelta(days=2)
    collected = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    with TestClient(create_app(database_url=url, pilot_id=pilot)) as client:
        admin = login(client, "40001", pin="582491")
        collectives = {row["flow"]: row["id"] for row in client.get("/accounts/admin/collectives", headers=admin).json()}
        resident_id, resident = register(client, "40002")
        _, stranger = register(client, "40009")
        coord, coord_id, member, request_ids = {}, {}, {}, {}
        for document, flow, residue, name in (("40003", "huerta", "organico", "Hugo Huertero"),
                                              ("40004", "reciclaje", "reciclable", "Rosa Recicladora")):
            coord_id[flow], _ = register(client, document)
            body = {"role": "leader", "collective_id": collectives[flow], "pilot_enabled": False}
            assert client.put(f"/accounts/admin/{coord_id[flow]}/authorization", headers=admin, json=body).status_code == 200
            coord[flow] = login(client, document)
            member[flow] = client.post("/recolecciones/recolectores", headers=coord[flow], json={"nombre": name}).json()["id"]
            created = client.post("/recolecciones", headers={**resident, "Idempotency-Key": "f3-" + flow},
                                  json={"residuo": residue, "material": f"Material {flow}", "contacto": "3000000000",
                                        "direccion": "Manzana 1, Casa 2", "generador": "hogar", "disponibilidad": "Lunes"})
            assert created.status_code == 200, created.text
            request_ids[flow] = created.json()["id"]

        # Compatibilidad: solicitud creada por la API pública anterior (/community/collections).
        legacy = client.post("/community/collections", headers={**resident, "Idempotency-Key": "f3-legacy"}, json={
            "description": "Solicitud del formulario anterior", "contact": "3000000000", "address": "Calle 123",
            "flow": "organic", "preferred_from": soon.isoformat(), "preferred_until": (soon + timedelta(hours=2)).isoformat(),
        })
        assert legacy.status_code == 201, legacy.text

        results = {}
        for flow, material, kilos, expected in (("huerta", "ORG-F3", "2.5", 25), ("reciclaje", "PET-F3", "3.750", 15)):
            headers, other = coord[flow], coord["reciclaje" if flow == "huerta" else "huerta"]
            path = f"/recolecciones/{request_ids[flow]}"
            # Programación en el pasado rechazada (hora de Bogotá).
            past = (datetime.now(timezone(timedelta(hours=-5))) - timedelta(minutes=10)).isoformat()
            assert client.post(path + "/programar", headers=headers, json={"cita": past, "responsable": member[flow]}).status_code == 422
            assert client.post(path + "/programar", headers=headers,
                               json={"cita": soon.isoformat(), "responsable": member[flow]}).status_code == 200
            result = {"material": material, "kilos": kilos, "resultado": "total", "recogida_en": collected,
                      "constancia": f"Llamada de {flow}", "observaciones": "Material limpio"}
            # Otro colectivo no puede cerrar; dos cierres simultáneos crean una sola entrega.
            assert client.post(path + "/cerrar", headers=other, json=result).status_code == 404
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _: client.post(path + "/cerrar", headers=headers, json=result), range(2)))
            assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
            # Cierre duplicado con otros datos: rechazado.
            assert client.post(path + "/cerrar", headers=headers, json={**result, "kilos": "99"}).status_code == 409
            results[flow] = expected

        # Solicitud antigua: se programa y cierra con el mismo flujo.
        legacy_path = f"/recolecciones/{legacy.json()['id']}"
        # Otra hora: el colectivo no admite dos visitas a la misma hora exacta.
        assert client.post(legacy_path + "/programar", headers=coord["huerta"],
                           json={"cita": (soon + timedelta(hours=3)).isoformat(), "responsable": member["huerta"]}).status_code == 200
        closed = client.post(legacy_path + "/cerrar", headers=coord["huerta"], json={
            "material": "ORG-F3", "kilos": "1", "resultado": "parcial", "recogida_en": collected, "constancia": "En persona"})
        assert closed.status_code == 200, closed.text

    with TestClient(create_app(database_url=url, pilot_id=pilot)) as restarted:
        # Saldo y movimientos persistidos: 25 + 15 + 10 puntos, una acreditación por entrega.
        assert restarted.get("/community/points", headers=resident).json()["balance"] == 50
        assert sorted(m["points"] for m in restarted.get("/community/points/movements", headers=resident).json()) == [10, 15, 25]
        for flow in ("huerta", "reciclaje"):
            timeline = restarted.get(f"/community/collections/{request_ids[flow]}/history", headers=resident).json()
            kinds = [e["event"] for e in timeline]
            assert kinds[:2] == ["recibida", "programada"] and "recolectada" in kinds and kinds[-1] == "puntos_acreditados"
            done = next(e for e in timeline if e["event"] == "recolectada")
            assert done["result"] == "total" and done["collected_at"] and done["kilos"]
            assert next(e for e in timeline if e["event"] == "programada")["responsible_name"]
            assert timeline[-1]["points"] == results[flow]
            assert all("autora" not in e and "aviso" not in e["event"] for e in timeline)
            # Nadie más ve el historial de esta solicitud.
            assert restarted.get(f"/community/collections/{request_ids[flow]}/history", headers=stranger).status_code == 404
            # Historial operativo de la coordinadora: quién registró, quién recogió y puntos.
            history = restarted.get(f"/recolecciones/{request_ids[flow]}/historial", headers=coord[flow]).json()
            closing = next(e for e in history if e["evento"] == "recolectada")
            assert closing["autora"] == coord_id[flow]
            assert closing["registro"]["entrega"]["constancia"] == f"Llamada de {flow}"
            assert closing["registro"]["entrega"]["recolector"] == member[flow]
            assert closing["registro"]["nombre_recolector"] in ("Hugo Huertero", "Rosa Recicladora")
            assert next(e for e in history if e["evento"] == "puntos_acreditados")["registro"]["puntos"] == results[flow]
            completed = restarted.get("/recolecciones", headers=coord[flow], params={"estado": "recolectada"}).json()
            assert request_ids[flow] in [r["id"] for r in completed]

    with open_connection(url) as conn:
        rows = conn.execute("""
            select d.request_id, d.field_worker_id, d.closed_by_id, d.closed_at, d.api_result,
                   (select count(*) from point_movements m where m.delivery_id = d.id) as credits
            from deliveries d where d.pilot_id = %s and d.kind = 'pickup'
        """, (pilot,)).fetchall()
        assert len(rows) == 3 and all(r["credits"] == 1 for r in rows)
        by_request = {str(r["request_id"]): r for r in rows}
        for flow in ("huerta", "reciclaje"):
            row = by_request[request_ids[flow]]
            assert (str(row["field_worker_id"]), str(row["closed_by_id"])) == (member[flow], coord_id[flow])
            assert row["closed_at"] and row["api_result"]["recogida_en"] and row["api_result"]["constancia"]

        # Acceso digital de recolectores deshabilitado: una cuenta antigua con ese rol no entra.
        worker_account = uuid4()
        conn.execute("""
            insert into users (id, pilot_id, email, document_number, full_name, role, password_hash)
            values (%s, %s, %s, '40010', 'Cuenta antigua de recolector', 'recolector', %s)
        """, (worker_account, pilot, f"{worker_account}@example.invalid", PasswordHash.recommended().hash("1234")))
    with TestClient(create_app(database_url=url, pilot_id=pilot)) as client:
        response = client.post("/accounts/login", json={"national_id": "40010", "pin": "1234"})
        assert response.status_code == 401
        assert client.get("/recolecciones/asignadas").status_code in (401, 404)


def test_concurrent_overlapping_appointments_do_not_double_book_worker(environment):
    client, url, _, _ = environment
    leader = login(client, "10001")
    owner_id, owner = register(client, "91001")
    member = client.post("/recolecciones/recolectores", headers=leader, json={"nombre": "Prueba de agenda"})
    assert member.status_code == 201
    worker = member.json()["id"]
    form = {
        "residuo": "organico", "material": "Restos de fruta", "contacto": "3000000000",
        "direccion": "Dirección ficticia", "generador": "hogar", "disponibilidad": "Mañana",
    }
    ids = []
    for i in range(3):
        response = client.post("/recolecciones", headers={**owner, "Idempotency-Key": f"agenda-{i}"}, json=form)
        assert response.status_code == 200
        ids.append(response.json()["id"])
    start = (datetime.now(timezone.utc) + timedelta(days=2)).replace(second=0, microsecond=0)
    times = [start, start + timedelta(minutes=15)]

    def schedule(id_, at, reason=None):
        return client.post(f"/recolecciones/{id_}/programar", headers=leader, json={
            "cita": at.isoformat(), "responsable": worker, "motivo": reason,
        })

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda pair: schedule(*pair), zip(ids, times)))
    assert sorted(r.status_code for r in outcomes) == [200, 409]
    winner = next(i for i, r in enumerate(outcomes) if r.status_code == 200)
    rejected = ids[1 - winner]
    chosen = times[winner]
    before = client.get(f"/recolecciones/{rejected}/historial", headers=leader).json()
    assert [event["evento"] for event in before] == ["recibida"]

    assert schedule(ids[2], chosen).status_code == 409
    assert schedule(rejected, chosen + timedelta(hours=1)).status_code == 200
    assert schedule(rejected, chosen + timedelta(minutes=30), "Cambio solicitado").status_code == 409
    with open_connection(url) as conn:
        slots = conn.execute("""
            select s.starts_at from pickup_appointments a
            join pickup_slots s on s.id = a.slot_id and s.pilot_id = a.pilot_id
            where a.worker_id = %s order by s.starts_at
        """, (worker,)).fetchall()
        assert [row["starts_at"] for row in slots] == [chosen, chosen + timedelta(hours=1)]
        assert conn.execute("select count(*) as total from point_movements where client_id = %s",
                            (owner_id,)).fetchone()["total"] == 0


def test_weekly_calendar_by_collective_in_bogota_time(environment):
    """Fase 4 contra PostgreSQL real: calendario semanal filtrado por rango y colectivo."""
    _, url, _, _ = environment
    pilot = uuid4()
    initialize(url, pilot, create_pilot=True)
    provision(url, pilot, "50001", "Administración", "582491")
    bogota = timezone(timedelta(hours=-5))
    today = datetime.now(bogota).date()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=2)
    sunday_late = datetime.combine(monday + timedelta(days=6), datetime.min.time(), bogota).replace(hour=23, minute=30)
    monday_morning = datetime.combine(monday, datetime.min.time(), bogota).replace(hour=8)

    with TestClient(create_app(database_url=url, pilot_id=pilot)) as client:
        admin = login(client, "50001", pin="582491")
        collectives = {row["flow"]: row["id"] for row in client.get("/accounts/admin/collectives", headers=admin).json()}
        _, resident = register(client, "50002")
        coord, member, ids = {}, {}, {}
        for document, flow in (("50003", "huerta"), ("50004", "reciclaje")):
            account, _ = register(client, document)
            body = {"role": "leader", "collective_id": collectives[flow], "pilot_enabled": False}
            assert client.put(f"/accounts/admin/{account}/authorization", headers=admin, json=body).status_code == 200
            coord[flow] = login(client, document)
            member[flow] = client.post("/recolecciones/recolectores", headers=coord[flow], json={"nombre": f"Integrante {flow}"}).json()["id"]
        for key, residue in (("org", "organico"), ("rec", "reciclable"), ("pend", "organico")):
            created = client.post("/recolecciones", headers={**resident, "Idempotency-Key": "f4-" + key},
                                  json={"residuo": residue, "material": f"Material {key}", "contacto": "3000000000",
                                        "direccion": "Calle 1", "generador": "hogar", "disponibilidad": "Lunes"})
            assert created.status_code == 200, created.text
            ids[key] = created.json()["id"]
        for key, flow, when in (("org", "huerta", sunday_late), ("rec", "reciclaje", monday_morning)):
            scheduled = client.post(f"/recolecciones/{ids[key]}/programar", headers=coord[flow],
                                    json={"cita": when.isoformat(), "responsable": member[flow]})
            assert scheduled.status_code == 200, scheduled.text

    week = {"desde": str(monday)}
    with TestClient(create_app(database_url=url, pilot_id=pilot)) as restarted:  # persistencia
        garden = restarted.get("/recolecciones/calendario", headers=coord["huerta"], params=week).json()
        assert (garden["desde"], garden["hasta"]) == (str(monday), str(monday + timedelta(days=6)))
        assert [r["id"] for r in garden["programadas"]] == [ids["org"]]
        item = garden["programadas"][0]
        # Domingo 23:30 en Bogotá (lunes 04:30 UTC) queda en el domingo de esta semana.
        assert datetime.fromisoformat(item["cita"]).astimezone(bogota) == sunday_late
        assert item["nombre_responsable"] == "Integrante huerta" and item["creada"] and item["creada"] != item["cita"]
        # La solicitud sin programación va aparte, nunca en la cuadrícula.
        assert [r["id"] for r in garden["pendientes"]] == [ids["pend"]]
        recycling = restarted.get("/recolecciones/calendario", headers=coord["reciclaje"], params=week).json()
        assert [r["id"] for r in recycling["programadas"]] == [ids["rec"]] and recycling["pendientes"] == []
        assert restarted.get("/recolecciones/calendario", headers=coord["reciclaje"],
                             params={**week, "flujo": "huerta"}).status_code == 403
        everything = restarted.get("/recolecciones/calendario", headers=admin, params=week).json()
        assert sorted(r["id"] for r in everything["programadas"]) == sorted([ids["org"], ids["rec"]])
        only_recycling = restarted.get("/recolecciones/calendario", headers=admin, params={**week, "flujo": "reciclaje"}).json()
        assert [r["id"] for r in only_recycling["programadas"]] == [ids["rec"]]
        assert restarted.get("/recolecciones/calendario", headers=resident, params=week).status_code == 403
        assert restarted.get("/recolecciones", headers=admin).status_code == 403  # administración solo consulta
        # Semana siguiente y semana que cruza de año: vacías y con rango correcto.
        assert restarted.get("/recolecciones/calendario", headers=coord["huerta"],
                             params={"desde": str(monday + timedelta(days=7))}).json()["programadas"] == []
        new_year = restarted.get("/recolecciones/calendario", headers=admin, params={"desde": "2029-12-31"}).json()
        assert (new_year["hasta"], new_year["programadas"]) == ("2030-01-06", [])
        assert restarted.get("/recolecciones/calendario", headers=admin, params={"desde": str(monday + timedelta(days=1))}).status_code == 422


def test_mvp_end_to_end_both_flows_with_field_worker_accounts(environment):
    """Escenario oficial contra PostgreSQL real: unidad productiva (orgánico) y residente
    (reciclable) → coordinadora → asignación → programación → el recolector registra la
    recolección desde su acceso operativo → estado y puntos según regla provisional."""
    _, url, _, _ = environment
    pilot = uuid4()
    initialize(url, pilot, create_pilot=True)
    provision(url, pilot, "60001", "Administración", "582491")
    bogota = timezone(timedelta(hours=-5))
    soon = (datetime.now(bogota) + timedelta(days=2)).replace(microsecond=0)
    collected = (datetime.now(bogota) - timedelta(minutes=20)).replace(microsecond=0).isoformat()
    period = {"desde": (datetime.now(bogota) - timedelta(days=1)).isoformat(),
              "hasta": (datetime.now(bogota) + timedelta(days=1)).isoformat()}

    with TestClient(create_app(database_url=url, pilot_id=pilot)) as client:
        admin = login(client, "60001", pin="582491")
        collectives = {row["flow"]: row["id"] for row in client.get("/accounts/admin/collectives", headers=admin).json()}
        # Reglas parametrizables: valores provisionales configurados por administración.
        rules = {}
        for code, name, per_kg in (("ORG-MVP", "Orgánico de cocina", "8"), ("PET-MVP", "Plástico PET", "5")):
            created = client.post("/accounts/admin/point-rules", headers=admin,
                                  json={"material_code": code, "material_name": name, "points_per_kg": per_kg,
                                        "note": "Valor provisional de demostración"})
            assert created.status_code == 201, created.text
            assert created.json()["provisional"] is True
            rules[code] = created.json()["id"]
        _, resident = register(client, "60002")
        assert client.post("/accounts/admin/point-rules", headers=resident, json={
            "material_code": "X", "material_name": "Intento", "points_per_kg": "1"}).status_code == 403

        # Piloto: la unidad productiva no solicita hasta que administración la habilita.
        business_id, business = register(client, "60003", kind="business")
        body = {"residuo": "organico", "material": "Restos de cocina", "contacto": "3001112233",
                "direccion": "Local 4, Villas de San Pablo", "generador": "unidad_productiva", "disponibilidad": "Mañanas"}
        assert client.post("/recolecciones", headers={**business, "Idempotency-Key": "mvp-org"}, json=body).status_code == 403
        assert client.put(f"/accounts/admin/{business_id}/authorization", headers=admin,
                          json={"role": "business", "pilot_enabled": True, "collective_id": None}).status_code == 200

        coord, member, worker, worker_ids, requests = {}, {}, {}, {}, {}
        for n, flow in ((4, "huerta"), (5, "reciclaje")):
            account, _ = register(client, f"6000{n}")
            assert client.put(f"/accounts/admin/{account}/authorization", headers=admin, json={
                "role": "leader", "collective_id": collectives[flow], "pilot_enabled": False}).status_code == 200
            coord[flow] = login(client, f"6000{n}")
            member[flow] = client.post("/recolecciones/recolectores", headers=coord[flow],
                                       json={"nombre": f"Recolector {flow}"}).json()["id"]
            # Cuenta operativa vinculada al integrante (sin duplicar field_workers).
            worker_ids[flow], _ = register(client, f"6001{n}")
            wrong = client.put(f"/accounts/admin/{worker_ids[flow]}/authorization", headers=admin, json={
                "role": "field_worker", "collective_id": collectives[flow], "pilot_enabled": False})
            assert wrong.status_code == 422  # sin integrante vinculado
            linked = client.put(f"/accounts/admin/{worker_ids[flow]}/authorization", headers=admin, json={
                "role": "field_worker", "collective_id": collectives[flow], "pilot_enabled": False, "worker_id": member[flow]})
            assert linked.status_code == 200, linked.text
            worker[flow] = login(client, f"6001{n}")
        # Un integrante no puede vincularse a dos cuentas ni a otro colectivo.
        extra, _ = register(client, "60020")
        assert client.put(f"/accounts/admin/{extra}/authorization", headers=admin, json={
            "role": "field_worker", "collective_id": collectives["huerta"], "pilot_enabled": False,
            "worker_id": member["huerta"]}).status_code == 422
        assert client.put(f"/accounts/admin/{extra}/authorization", headers=admin, json={
            "role": "field_worker", "collective_id": collectives["huerta"], "pilot_enabled": False,
            "worker_id": member["reciclaje"]}).status_code == 422

        created = client.post("/recolecciones", headers={**business, "Idempotency-Key": "mvp-org"}, json=body)
        assert created.status_code == 200, created.text
        requests["huerta"] = created.json()["id"]
        created = client.post("/recolecciones", headers={**resident, "Idempotency-Key": "mvp-rec"}, json={
            **body, "residuo": "reciclable", "material": "Botellas", "generador": "hogar", "direccion": "Manzana 3, Casa 9"})
        requests["reciclaje"] = created.json()["id"]
        cancelled = client.post("/recolecciones", headers={**resident, "Idempotency-Key": "mvp-can"}, json={
            **body, "residuo": "reciclable", "material": "Cartón", "generador": "hogar"}).json()["id"]

        # RN-01: cada solicitud llega solo a su colectivo.
        assert [r["id"] for r in client.get("/recolecciones", headers=coord["huerta"]).json()] == [requests["huerta"]]
        assert sorted(r["id"] for r in client.get("/recolecciones", headers=coord["reciclaje"]).json()) == sorted([requests["reciclaje"], cancelled])
        # Antes de programar, el recolector no tiene nada asignado.
        assert client.get("/recolecciones/asignadas", headers=worker["huerta"]).json() == []

        for i, flow in enumerate(("huerta", "reciclaje")):
            path = f"/recolecciones/{requests[flow]}"
            assert client.post(path + "/revisar", headers=coord[flow]).status_code == 200
            assert client.post(path + "/programar", headers=coord[flow], json={
                "cita": (soon + timedelta(hours=i)).isoformat(), "responsable": member[flow]}).status_code == 200
        client.post(f"/recolecciones/{cancelled}/programar", headers=coord["reciclaje"], json={
            "cita": (soon + timedelta(hours=5)).isoformat(), "responsable": member["reciclaje"]})
        assert client.post(f"/recolecciones/{cancelled}/cancelar", headers=coord["reciclaje"],
                           json={"motivo": "El vecino desistió"}).status_code == 200
        # RN-05: sin puntos antes de registrar la recolección.
        assert client.get("/community/points", headers=business).json()["balance"] == 0

        # El solicitante ve la programación: día, hora y persona encargada.
        appointment = client.get("/community/appointments", headers=business).json()
        assert appointment[0]["responsible_name"] == "Recolector huerta"
        notices = [n["title"] for n in client.get("/community/notifications", headers=business).json()]
        assert "Solicitud recibida" in notices and "Recolección programada" in notices

        # Recolector: solo sus asignaciones, con lo necesario para atender.
        own = client.get("/recolecciones/asignadas", headers=worker["huerta"]).json()
        assert [r["id"] for r in own] == [requests["huerta"]]
        assert own[0]["solicitud"]["direccion"] and own[0]["solicitud"]["contacto"]
        assert client.get("/recolecciones/asignadas", headers=worker["reciclaje"]).json()[0]["id"] == requests["reciclaje"]
        assert client.get("/recolecciones", headers=worker["huerta"]).status_code == 403
        assert client.post(f"/recolecciones/{requests['huerta']}/programar", headers=worker["huerta"], json={
            "cita": soon.isoformat(), "responsable": member["huerta"]}).status_code == 403

        result = {"material": "ORG-MVP", "kilos": "2.5", "resultado": "total", "recogida_en": collected,
                  "observaciones": "Dos bolsas"}
        # Recolector ajeno o de otro colectivo: no cierra ni consulta.
        assert client.post(f"/recolecciones/{requests['huerta']}/cerrar", headers=worker["reciclaje"], json=result).status_code == 404
        assert client.get(f"/recolecciones/{requests['huerta']}/historial", headers=worker["reciclaje"]).status_code == 404
        # Cancelada: no se cierra.
        assert client.post(f"/recolecciones/{cancelled}/cerrar", headers=worker["reciclaje"],
                           json={**result, "material": "PET-MVP"}).status_code == 404
        assert client.post(f"/recolecciones/{cancelled}/cerrar", headers=coord["reciclaje"],
                           json={**result, "material": "PET-MVP", "constancia": "Llamada"}).status_code == 409

        # El huertero registra; dos peticiones simultáneas → una sola entrega y un solo abono.
        path = f"/recolecciones/{requests['huerta']}"
        with ThreadPoolExecutor(max_workers=2) as pool:
            closed = list(pool.map(lambda _: client.post(path + "/cerrar", headers=worker["huerta"], json=result), range(2)))
        assert [r.status_code for r in closed] == [200, 200], [r.text for r in closed]
        assert closed[0].json()["estado"] == "recolectada" and closed[0].json()["cerrada_por"] == worker_ids["huerta"]
        assert client.post(path + "/cerrar", headers=worker["huerta"], json={**result, "kilos": "9"}).status_code == 409
        recycled = client.post(f"/recolecciones/{requests['reciclaje']}/cerrar", headers=worker["reciclaje"],
                               json={**result, "material": "PET-MVP", "kilos": "3"})
        assert recycled.status_code == 200, recycled.text
        assert client.get("/recolecciones/asignadas", headers=worker["huerta"]).json()[0]["estado"] == "recolectada"

        # Regla parametrizable: un cambio solo afecta recolecciones posteriores.
        assert client.post("/accounts/admin/point-rules", headers=admin, json={
            "material_code": "ORG-MVP", "material_name": "Orgánico de cocina", "points_per_kg": "100"}).status_code == 201
        history_rules = [r for r in client.get("/accounts/admin/point-rules", headers=admin).json() if r["material_code"] == "ORG-MVP"]
        assert len(history_rules) == 2 and sum(r["valid_until"] is None for r in history_rules) == 1

    with TestClient(create_app(database_url=url, pilot_id=pilot)) as restarted:  # persistencia
        # Puntos: floor(2.5 × 8) = 20 para la unidad productiva y floor(3 × 5) = 15 para el residente.
        assert restarted.get("/community/points", headers=business).json()["balance"] == 20
        assert restarted.get("/community/points", headers=resident).json()["balance"] == 15
        timeline = restarted.get(f"/community/collections/{requests['huerta']}/history", headers=business).json()
        assert [e["event"] for e in timeline] == ["recibida", "revision", "programada", "recolectada", "puntos_acreditados"]
        assert timeline[-1]["points"] == 20 and float(timeline[3]["kilos"]) == 2.5
        assert restarted.get(f"/community/collections/{requests['huerta']}/history", headers=resident).status_code == 404
        history = restarted.get(f"/recolecciones/{requests['huerta']}/historial", headers=coord["huerta"]).json()
        closing = next(e for e in history if e["evento"] == "recolectada")
        assert closing["autora"] == worker_ids["huerta"] and closing["registro"]["entrega"]["unidad"] == "kg"
        assert closing["registro"]["entrega"]["recolector"] == member["huerta"]
        # RN-07: administración consulta el calendario sin contacto ni dirección.
        monday = soon.date() - timedelta(days=soon.weekday())
        week = restarted.get("/recolecciones/calendario", headers=admin, params={"desde": str(monday)}).json()
        assert week["programadas"] and all(i["solicitud"] is None and i["material"] for i in week["programadas"])
        # Resúmenes por flujo, estado y período.
        report = restarted.get("/accounts/admin/reports", headers=admin, params=period).json()
        assert report["solicitudes"]["huerta"]["recolectada"] == 1
        assert report["solicitudes"]["reciclaje"] == {"recibida": 0, "revision": 0, "programada": 0, "recolectada": 1, "cancelada": 1}
        assert report["recogidas_completadas"] == 2 and report["puntos_acreditados"] == 35
        summary = restarted.get("/recolecciones/resumen", headers=coord["reciclaje"], params=period).json()
        assert summary["conteos"]["recolectada"] == 1 and summary["conteos"]["cancelada"] == 1
        # Cuenta operativa desactivada en su colectivo: pierde el acceso.
        assert restarted.patch(f"/recolecciones/recolectores/{member['huerta']}", headers=coord["huerta"],
                               json={"activo": False}).status_code == 200
        assert restarted.get("/recolecciones/asignadas", headers=worker["huerta"]).status_code in (401, 403)

    with open_connection(url) as conn:
        rows = conn.execute("""
            select d.request_id, d.field_worker_id, d.closed_by_id, i.rule_id,
                   (select count(*) from point_movements m where m.delivery_id = d.id) as credits
            from deliveries d join delivery_items i on i.delivery_id = d.id where d.pilot_id = %s
        """, (pilot,)).fetchall()
        assert len(rows) == 2 and all(r["credits"] == 1 for r in rows)
        by_request = {str(r["request_id"]): r for r in rows}
        assert str(by_request[requests["huerta"]]["rule_id"]) == rules["ORG-MVP"]  # regla aplicada registrada
        assert str(by_request[requests["huerta"]]["closed_by_id"]) == worker_ids["huerta"]
        linked = conn.execute("select count(*) as n from field_workers where pilot_id = %s and account_id is not null", (pilot,)).fetchone()
        assert linked["n"] == 2  # un vínculo por cuenta, sin integrantes duplicados


def test_past_or_incomplete_schedule_is_rejected_and_request_stays_consistent(environment):
    """No se programa en el pasado (hora de Bogotá) ni sin fecha, hora o responsable;
    un intento rechazado no deja cita, evento ni cambio de estado en PostgreSQL."""
    client, url, _, _ = environment
    _, resident = register(client, "71001")
    leader = login(client, "10001")
    request_id = client.post("/recolecciones", headers={**resident, "Idempotency-Key": "past-1"}, json={
        "residuo": "organico", "material": "Cáscaras", "contacto": "3000000000",
        "direccion": "Calle 123", "generador": "hogar", "disponibilidad": "Mañanas"}).json()["id"]
    worker = client.get("/recolecciones/recolectores", headers=leader).json()[0]["id"]
    bogota = ZoneInfo("America/Bogota")
    path = f"/recolecciones/{request_id}/programar"
    for body in (
        {"cita": (datetime.now(bogota) - timedelta(minutes=5)).isoformat(), "responsable": worker},
        {"cita": (datetime.now(bogota) - timedelta(days=1)).replace(tzinfo=None).isoformat(), "responsable": worker},
        {"cita": (datetime.now(bogota) + timedelta(days=1)).isoformat()},
        {"responsable": worker},
        {"cita": (datetime.now(bogota) + timedelta(days=1)).date().isoformat(), "responsable": worker},
    ):
        assert client.post(path, headers=leader, json=body).status_code == 422, body
    with open_connection(url) as conn:
        assert conn.execute("select status from pickup_requests where id = %s", (request_id,)).fetchone()["status"] == "recibida"
        assert conn.execute("select count(*) as n from pickup_appointments where request_id = %s", (request_id,)).fetchone()["n"] == 0
        assert [r["kind"] for r in conn.execute(
            "select kind from collection_events where request_id = %s", (request_id,)).fetchall()] == ["recibida"]
