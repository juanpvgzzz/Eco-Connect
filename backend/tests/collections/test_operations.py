from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from datetime import datetime, timedelta, timezone

from backend.app.collections.api import account_actor, router
from backend.app.collections.service import Actor, Collections, Notice


# Fechas relativas a hoy (America/Bogota, UTC−5): las pruebas no caducan.
BOGOTA = timezone(timedelta(hours=-5))
_TODAY = datetime.now(BOGOTA).date()
D1, D2, D3 = (_TODAY + timedelta(days=n) for n in (30, 31, 40))
JUST_NOW = (datetime.now(BOGOTA) - timedelta(minutes=30)).replace(microsecond=0).isoformat()


class Memory:
    """Doble transaccional local. Descarta toda la copia al fallar."""
    def __init__(self, client):
        self.client = client
        self.keys = {}
        self.rows = {}
        self.events = []
        self.saved_notices = []
        self.credits = []
        self.worker = uuid4()
        self.members = {}
        self.reject_credit = False

    @contextmanager
    def transaction(self):
        working = deepcopy(self)
        yield working
        self.__dict__.update(working.__dict__)

    def pilot(self, client):
        return client == self.client

    def reserve(self, scope, owner, key, new):
        index = scope, owner, key
        if index in self.keys:
            return self.rows[self.keys[index]], False
        self.keys[index] = new.id
        self.save(new)
        return new, True

    def locked(self, flow, id):
        row = self.rows.get(id)
        return row if row and row.flujo == flow else None

    def locked_assigned(self, worker, flow, id):
        row = self.locked(flow, id)
        return row if row and row.responsable == worker and row.estado in ("programada", "recolectada") else None

    def assigned(self, worker, flow):
        return [r for r in self.rows.values() if r.responsable == worker and r.flujo == flow
                and r.estado in ("programada", "recolectada")]

    def workers(self, flow, include_inactive=False):
        base = [{"id": self.worker, "full_name": "Recolector de prueba", "active": True}] if flow == "huerta" else []
        extra = [m for m in self.members.values() if m["flow"] == flow and (m["active"] or include_inactive)]
        return base + [{k: m[k] for k in ("id", "full_name", "active")} for m in extra]

    def add_worker(self, flow, name):
        member = {"id": uuid4(), "full_name": name, "active": True, "flow": flow}
        self.members[member["id"]] = member
        return {k: member[k] for k in ("id", "full_name", "active")}

    def set_worker_active(self, flow, worker, active):
        member = self.members.get(worker)
        if not member or member["flow"] != flow:
            return None
        member["active"] = active
        return {k: member[k] for k in ("id", "full_name", "active")}

    def materials(self):
        return [{"code": "PET", "name": "Plástico PET"}]

    def worker_in_flow(self, flow, worker):
        member = self.members.get(worker)
        return (flow == "huerta" and worker == self.worker) or bool(member and member["flow"] == flow and member["active"])

    def save(self, row):
        self.rows[row.id] = row

    def event(self, row, kind, author, reason):
        self.events.append((deepcopy(row), kind, author, reason))
        notice = Notice(solicitud_id=row.id, evento=kind, motivo=reason,
                        cita=row.cita, responsable=row.responsable)
        self.saved_notices.append((row.cliente, row.flujo, notice))

    def inbox(self, flow, state):
        return [r for r in self.rows.values() if r.flujo == flow and (not state or r.estado == state)]

    def scheduled_between(self, flows, start, end):
        return [{**r.model_dump(), "nombre_responsable": None, "creada": None} for r in self.rows.values()
                if r.flujo in flows and r.responsable and r.cita and start <= r.cita < end
                and r.estado in ("programada", "recolectada")]

    def unscheduled(self, flows):
        return [{**r.model_dump(), "nombre_responsable": None, "creada": None} for r in self.rows.values()
                if r.flujo in flows and r.estado in ("recibida", "revision")]

    def notices(self, flow):
        return [notice for _, target, notice in self.saved_notices if target == flow]

    def client_notices(self, client):
        return [notice for target, _, notice in self.saved_notices
                if target == client and notice.evento != "aviso_recolector"]

    def history(self, flow, id):
        return [{"evento": kind, "motivo": why} for row, kind, _, why in self.events
                if row.id == id and row.flujo == flow]

    def on_duty(self, flow, at):
        return self.worker

    def credit(self, id, client, material, kilos):
        self.credits.append((id, client, material, kilos))
        if self.reject_credit:
            raise RuntimeError("Fallo simulado")


class Operations(TestCase):
    def setUp(self):
        self.client = Actor(uuid4(), "cliente")
        self.garden = Actor(uuid4(), "lider", "huerta")
        self.recycler = Actor(uuid4(), "lider", "reciclaje")
        self.actor = self.client
        self.db = Memory(self.client.id)
        app = FastAPI()
        app.include_router(router(Collections(self.db.transaction), lambda: self.actor))
        self.api = self.enterContext(TestClient(app, raise_server_exceptions=False))
        self.base = "/recolecciones"
        self.body = dict(residuo="organico", material="cáscaras", contacto="ficticio",
                         direccion="piloto", generador="hogar", disponibilidad="mañana")
        self.delivery = dict(material="cáscaras", kilos="1.250", resultado="parcial")
        # Cierre de recogida: fecha real y constancia de cómo informó el recolector.
        self.result = dict(self.delivery, recogida_en=JUST_NOW, constancia="Llamada del recolector")

    def create(self, key="uno"):
        return self.api.post(self.base, json=self.body, headers={"Idempotency-Key": key})

    def pending(self):
        response = self.create()
        self.assertEqual(response.status_code, 200, response.text)
        self.actor = self.garden
        return self.base + "/" + response.json()["id"]

    def test_routing_and_idempotency(self):
        a = self.create().json()
        self.assertEqual(a, self.create().json())
        self.body.update(residuo="reciclable", material="cartón")
        self.assertEqual(self.create().status_code, 409)
        b = self.create("dos").json()
        for leader, row in [(self.garden, a), (self.recycler, b)]:
            self.actor = leader
            # La bandeja añade el nombre del responsable (campo aditivo, nulo sin cita).
            inbox = self.api.get(self.base, params={"estado": "recibida"}).json()
            self.assertEqual(inbox, [{**row, "nombre_responsable": None}])
            notices = self.api.get(self.base + "/avisos").json()
            self.assertEqual([(n["evento"], n["solicitud_id"]) for n in notices], [("recibida", row["id"])])
        path = self.base + "/" + a["id"]
        self.assertEqual(self.api.get(path + "/historial").status_code, 404)
        self.assertEqual(self.api.post(path + "/cancelar", json={"motivo": "prueba"}).status_code, 404)

    @patch("socket.socket.connect", side_effect=AssertionError("Conexión externa"))
    def test_internal_notices_by_recipient(self, connect):
        path = self.pending()
        appointments = [f"{D1}T08:00:00-05:00", f"{D2}T10:00:00-05:00"]
        for at in appointments:
            response = self.api.post(path + "/programar", json={"cita": at, "motivo": "Disponibilidad", "responsable": str(self.db.worker)})
            self.assertEqual(response.status_code, 200, response.text)
        for actor in (self.client, self.garden):
            self.actor = actor
            notices = self.api.get(self.base + "/avisos").json()
            self.assertEqual([n["evento"] for n in notices], ["recibida", "programada", "reprogramada"])
            self.assertEqual([n["cita"] for n in notices[1:]], appointments)
            self.assertEqual(notices[-1]["responsable"], str(self.db.worker))
            self.assertEqual(notices[-1]["motivo"], "Disponibilidad")
        for actor in (Actor(uuid4(), "cliente"), self.recycler):
            self.actor = actor
            self.assertEqual(self.api.get(self.base + "/avisos").json(), [])
        connect.assert_not_called()

    def test_pilot(self):
        self.actor = Actor(uuid4(), "cliente")
        self.assertEqual(self.create().status_code, 403)
        self.assertFalse(self.db.rows)

    def test_account_identity_bridge(self):
        identity = SimpleNamespace(id=str(self.garden.id), profile=SimpleNamespace(role="leader"),
                                   collective_id="equipo-huerta")
        adapt = account_actor(lambda: identity, {"equipo-huerta": "huerta"})
        app = FastAPI()
        app.include_router(router(Collections(self.db.transaction), adapt))
        with TestClient(app) as api:
            self.assertEqual(api.get(self.base).status_code, 200)
            identity.collective_id = "desconocido"
            self.assertEqual(api.get(self.base).status_code, 403)
            identity.profile.role = "resident"
            self.assertEqual(api.get(self.base).status_code, 403)
            self.assertEqual(api.get(self.base + "/avisos").status_code, 200)

    def test_review_state_and_weight_limit(self):
        path = self.pending()
        reviewed = self.api.post(path + "/revisar")
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        self.assertEqual(reviewed.json()["estado"], "revision")
        self.assertEqual(self.db.events[-1][1], "revision")
        self.assertEqual(self.api.post(path + "/revisar").status_code, 409)
        next(iter(self.db.rows.values())).estado = "revision"
        listing = self.api.get(self.base, params={"estado": "revision"})
        self.assertEqual(listing.json()[0]["estado"], "revision")
        self.assertEqual(self.api.post(path + "/programar", json={"cita": f"{D1}T08:00:00", "responsable": str(self.db.worker)}).status_code, 200)
        overweight = dict(self.result, kilos="10000.001")
        self.assertEqual(self.api.post(path + "/cerrar", json=overweight).status_code, 422)
        self.assertFalse(self.db.credits)

    def test_schedule_failed_visit_cancel(self):
        path = self.pending()
        # Sin responsable, con un recolector ajeno o sin hora: no se programa.
        self.assertEqual(self.api.post(path + "/programar", json={"cita": f"{D1}T15:00:00Z"}).status_code, 422)
        stranger = {"cita": f"{D1}T15:00:00Z", "responsable": str(uuid4())}
        self.assertEqual(self.api.post(path + "/programar", json=stranger).status_code, 422)
        no_time = {"cita": f"{D1}", "responsable": str(self.db.worker)}
        self.assertEqual(self.api.post(path + "/programar", json=no_time).status_code, 422)
        self.assertEqual(len(self.db.events), 1)
        self.assertEqual(next(iter(self.db.rows.values())).estado, "recibida")
        appointment = {"cita": f"{D1}T15:00:00Z", "responsable": str(self.db.worker)}
        row = self.api.post(path + "/programar", json=appointment).json()
        self.assertEqual(row["cita"], f"{D1}T10:00:00-05:00")
        self.assertEqual(row["responsable"], str(self.db.worker))
        appointment.update(cita=f"{D2}T08:00:00", motivo="Petición del cliente")
        self.assertEqual(self.api.post(path + "/programar", json=appointment).status_code, 200)
        self.assertEqual(self.db.events[-1][3], appointment["motivo"])
        reason = {"motivo": "Nadie en casa"}
        row = self.api.post(path + "/visita-fallida", json=reason).json()
        self.assertEqual(row["estado"], "recibida")
        self.assertIsNone(row["cita"])
        self.assertEqual(self.api.post(path + "/cancelar", json=reason).json()["estado"], "cancelada")
        self.assertFalse(self.db.credits)

    def test_manual_assignment_and_coordinator_close(self):
        path = self.pending()
        invalid = self.api.post(path + "/programar", json={
            "cita": f"{D1}T08:00:00-05:00", "responsable": str(uuid4()),
        })
        self.assertEqual(invalid.status_code, 422)
        scheduled = self.api.post(path + "/programar", json={
            "cita": f"{D1}T08:00:00-05:00", "responsable": str(self.db.worker),
        })
        self.assertEqual(scheduled.status_code, 200, scheduled.text)
        # La bandeja de asignaciones es solo para cuentas de recolector.
        self.assertEqual(self.api.get(self.base + "/asignadas").status_code, 403)
        # La coordinadora registra lo que le comunicó el recolector.
        closed = self.api.post(path + "/cerrar", json=self.result)
        self.assertEqual(closed.status_code, 200, closed.text)
        body = closed.json()
        self.assertEqual((body["estado"], body["cerrada_por"]), ("recolectada", str(self.garden.id)))
        self.assertEqual(body["entrega"]["recolector"], str(self.db.worker))
        self.assertEqual(body["entrega"]["constancia"], "Llamada del recolector")
        self.assertEqual(len(self.db.credits), 1)
        # Reintento idéntico: sin segunda entrega ni puntos. Otros datos: rechazo.
        self.assertEqual(self.api.post(path + "/cerrar", json=self.result).status_code, 200)
        self.assertEqual(self.api.post(path + "/cerrar", json=dict(self.result, kilos="9")).status_code, 409)
        self.assertEqual(len(self.db.credits), 1)

    def test_close_rollback_and_retry(self):
        path = self.pending()
        self.api.post(path + "/programar", json={"cita": f"{D1}T08:00:00", "responsable": str(self.db.worker)})
        self.db.reject_credit = True
        self.assertEqual(self.api.post(path + "/cerrar", json=self.result).status_code, 500)
        self.assertEqual(next(iter(self.db.rows.values())).estado, "programada")
        self.assertEqual(len(self.db.events), 2)
        self.assertFalse(self.db.credits)
        self.db.reject_credit = False
        for _ in range(2):
            row = self.api.post(path + "/cerrar", json=self.result).json()
            self.assertEqual(row["cerrada_por"], str(self.garden.id))
        self.assertEqual(len(self.db.credits), 1)
        self.assertEqual(len(self.db.events), 3)
        self.assertEqual(str(self.db.credits[0][-1]), "1.250")

    def test_direct_and_reward_authorization(self):
        data = dict(**self.delivery, cliente=str(self.client.id), clave="directa")
        self.actor = self.recycler
        self.assertEqual(self.api.post(self.base + "/directas", json=data).status_code, 403)
        self.assertEqual(self.api.post(self.base + "/canjes/confirmar", json={"codigo": "demo"}).status_code, 403)
        self.actor = self.garden
        for _ in range(2):
            self.assertEqual(self.api.post(self.base + "/directas", json=data).status_code, 200)
        self.assertEqual(len(self.db.credits), 1)
        self.assertEqual(self.db.credits[0][1], self.client.id)


class AssignmentPhase(TestCase):
    """Fase 2: integrantes por colectivo, asignación manual y aviso al recolector."""
    setUp = Operations.setUp
    create = Operations.create
    pending = Operations.pending

    def test_members_are_scoped_to_each_collective(self):
        self.actor = self.recycler
        created = self.api.post(self.base + "/recolectores", json={"nombre": "  Rosa Reciclaje "})
        self.assertEqual(created.status_code, 201, created.text)
        member = created.json()
        self.assertEqual(member["full_name"], "Rosa Reciclaje")
        self.assertEqual([w["full_name"] for w in self.api.get(self.base + "/recolectores").json()], ["Rosa Reciclaje"])
        # La coordinadora de huerta no ve ni modifica integrantes de reciclaje.
        self.actor = self.garden
        self.assertNotIn(member["id"], [str(w["id"]) for w in self.api.get(self.base + "/recolectores").json()])
        self.assertEqual(self.api.patch(self.base + "/recolectores/" + member["id"], json={"activo": False}).status_code, 404)
        # Un vecino no gestiona integrantes.
        self.actor = self.client
        self.assertEqual(self.api.get(self.base + "/recolectores").status_code, 403)
        self.assertEqual(self.api.post(self.base + "/recolectores", json={"nombre": "Intruso"}).status_code, 403)

    def test_cannot_assign_other_collective_or_inactive_member(self):
        self.actor = self.recycler
        recycler_member = self.api.post(self.base + "/recolectores", json={"nombre": "Rosa"}).json()["id"]
        self.actor = self.client
        path = self.pending()  # solicitud orgánica, actor = coordinadora de huerta
        at = f"{D3}T09:30:00-05:00"
        foreign = self.api.post(path + "/programar", json={"cita": at, "responsable": recycler_member})
        self.assertEqual(foreign.status_code, 422)
        own = self.api.post(self.base + "/recolectores", json={"nombre": "Hugo Huerta"}).json()["id"]
        self.assertEqual(self.api.patch(self.base + "/recolectores/" + own, json={"activo": False}).status_code, 200)
        self.assertEqual(self.api.post(path + "/programar", json={"cita": at, "responsable": own}).status_code, 422)
        self.assertEqual(self.api.patch(self.base + "/recolectores/" + own, json={"activo": True}).status_code, 200)
        scheduled = self.api.post(path + "/programar", json={"cita": at, "responsable": own})
        self.assertEqual(scheduled.status_code, 200, scheduled.text)
        row = scheduled.json()
        self.assertEqual((row["estado"], row["responsable"], row["programada_por"]), ("programada", own, str(self.garden.id)))

    def test_worker_notice_is_recorded_but_hidden_from_resident(self):
        path = self.pending()
        self.assertEqual(self.api.post(path + "/aviso-recolector", json={"canal": "llamada"}).status_code, 409)
        self.api.post(path + "/programar", json={"cita": f"{D3}T09:30:00-05:00", "responsable": str(self.db.worker)})
        self.assertEqual(self.api.post(path + "/aviso-recolector", json={"canal": "paloma"}).status_code, 422)
        ok = self.api.post(path + "/aviso-recolector", json={"canal": "whatsapp", "nota": "Confirmó la visita"})
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(self.db.events[-1][1:], ("aviso_recolector", self.garden.id, "WhatsApp: Confirmó la visita"))
        self.actor = self.client
        self.assertNotIn("aviso_recolector", [n["evento"] for n in self.api.get(self.base + "/avisos").json()])


class ClosingPhase(TestCase):
    """Fase 3: fechas futuras, cierre trazado y sin acceso de recolectores."""
    setUp = Operations.setUp
    create = Operations.create
    pending = Operations.pending

    def schedule(self, path):
        response = self.api.post(path + "/programar", json={"cita": f"{D1}T09:00:00-05:00", "responsable": str(self.db.worker)})
        self.assertEqual(response.status_code, 200, response.text)

    def test_rejects_past_appointments_in_bogota_time(self):
        path = self.pending()
        now = datetime.now(BOGOTA)
        for when in (now - timedelta(days=1), now - timedelta(minutes=5)):
            response = self.api.post(path + "/programar", json={"cita": when.isoformat(), "responsable": str(self.db.worker)})
            self.assertEqual(response.status_code, 422, when)
        # Misma hora expresada en UTC sigue siendo pasada.
        past_utc = (now - timedelta(minutes=5)).astimezone(timezone.utc).isoformat()
        self.assertEqual(self.api.post(path + "/programar", json={"cita": past_utc, "responsable": str(self.db.worker)}).status_code, 422)
        self.assertEqual(next(iter(self.db.rows.values())).estado, "recibida")
        soon = (now + timedelta(hours=2)).isoformat()
        self.assertEqual(self.api.post(path + "/programar", json={"cita": soon, "responsable": str(self.db.worker)}).status_code, 200)

    def test_close_requires_traceable_result(self):
        path = self.pending()
        # No se cierra lo que no está programado.
        self.assertEqual(self.api.post(path + "/cerrar", json=self.result).status_code, 409)
        self.schedule(path)
        future = (datetime.now(BOGOTA) + timedelta(days=1)).isoformat()
        for bad in (
            {k: v for k, v in self.result.items() if k != "constancia"},
            {k: v for k, v in self.result.items() if k != "recogida_en"},
            dict(self.result, recogida_en=future),
            dict(self.result, recolector=str(uuid4())),
            dict(self.result, resultado="dudoso"),
        ):
            self.assertEqual(self.api.post(path + "/cerrar", json=bad).status_code, 422, bad)
        self.assertFalse(self.db.credits)
        # Otro colectivo no puede cerrar.
        self.actor = self.recycler
        self.assertEqual(self.api.post(path + "/cerrar", json=self.result).status_code, 404)
        self.assertFalse(self.db.credits)

    def test_field_worker_sees_and_closes_only_own_assignments(self):
        path = self.pending()
        request_id = path.rsplit("/", 1)[1]
        self.schedule(path)
        outsider = Actor(uuid4(), "recolector", "huerta", trabajador_id=uuid4())
        assigned = Actor(uuid4(), "recolector", "huerta", trabajador_id=self.db.worker)
        other_flow = Actor(uuid4(), "recolector", "reciclaje", trabajador_id=self.db.worker)
        own_result = {k: v for k, v in self.result.items() if k != "constancia"}
        for actor in (outsider, other_flow):
            self.actor = actor
            self.assertEqual(self.api.get(self.base + "/asignadas").json(), [])
            self.assertEqual(self.api.post(path + "/cerrar", json=own_result).status_code, 404)
            self.assertEqual(self.api.get(path + "/historial").status_code, 404)
        self.actor = assigned
        self.assertEqual([r["id"] for r in self.api.get(self.base + "/asignadas").json()], [request_id])
        # No opera como coordinadora: ni bandeja, ni programar, ni integrantes.
        self.assertEqual(self.api.get(self.base).status_code, 403)
        self.assertEqual(self.api.post(path + "/programar", json={"cita": f"{D2}T09:00:00-05:00", "responsable": str(self.db.worker)}).status_code, 403)
        self.assertEqual(self.api.post(self.base + "/recolectores", json={"nombre": "Yo mismo"}).status_code, 403)
        self.assertEqual(self.api.get(self.base + "/materiales").status_code, 200)
        closed = self.api.post(path + "/cerrar", json=own_result)
        self.assertEqual(closed.status_code, 200, closed.text)
        body = closed.json()
        self.assertEqual((body["estado"], body["cerrada_por"], body["entrega"]["recolector"]), ("recolectada", str(assigned.id), str(self.db.worker)))
        self.assertEqual(body["entrega"]["unidad"], "kg")
        self.assertEqual(len(self.db.credits), 1)
        self.assertEqual(self.api.post(path + "/cerrar", json=own_result).status_code, 200)
        self.assertEqual(self.api.post(path + "/cerrar", json=dict(own_result, kilos="7")).status_code, 409)
        self.assertEqual(len(self.db.credits), 1)

    def test_coordinator_close_requires_confirmation_record(self):
        path = self.pending()
        self.schedule(path)
        without = {k: v for k, v in self.result.items() if k != "constancia"}
        self.assertEqual(self.api.post(path + "/cerrar", json=without).status_code, 422)
        self.assertFalse(self.db.credits)

class CalendarPhase(TestCase):
    """Fase 4: calendario semanal por colectivo, en hora de Bogotá."""
    setUp = Operations.setUp
    create = Operations.create
    pending = Operations.pending

    def monday(self, offset_weeks=0):
        day = datetime.now(BOGOTA).date() + timedelta(weeks=offset_weeks)
        return day - timedelta(days=day.weekday())

    def test_week_shows_only_confirmed_schedules_of_own_collective(self):
        path = self.pending()
        week = self.monday(5)
        at = datetime.combine(week + timedelta(days=2), datetime.min.time(), BOGOTA).replace(hour=9, minute=30)
        response = self.api.get(self.base + "/calendario", params={"desde": str(week)})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual((body["programadas"], len(body["pendientes"])), ([], 1))
        self.api.post(path + "/programar", json={"cita": at.isoformat(), "responsable": str(self.db.worker)})
        body = self.api.get(self.base + "/calendario", params={"desde": str(week)}).json()
        self.assertEqual([r["cita"] for r in body["programadas"]], [at.isoformat()])
        self.assertEqual(body["pendientes"], [])
        self.assertEqual((body["desde"], body["hasta"]), (str(week), str(week + timedelta(days=6))))
        # La semana siguiente no la contiene.
        self.assertEqual(self.api.get(self.base + "/calendario", params={"desde": str(week + timedelta(days=7))}).json()["programadas"], [])
        # La otra coordinadora no la ve ni puede pedir el calendario ajeno.
        self.actor = self.recycler
        self.assertEqual(self.api.get(self.base + "/calendario", params={"desde": str(week)}).json()["programadas"], [])
        self.assertEqual(self.api.get(self.base + "/calendario", params={"desde": str(week), "flujo": "huerta"}).status_code, 403)

    def test_permissions_and_week_start(self):
        week = self.monday()
        self.actor = self.client
        self.assertEqual(self.api.get(self.base + "/calendario", params={"desde": str(week)}).status_code, 403)
        self.actor = Actor(uuid4(), "admin")
        self.assertEqual(self.api.get(self.base + "/calendario", params={"desde": str(week)}).status_code, 200)
        self.assertEqual(self.api.get(self.base + "/calendario", params={"desde": str(week), "flujo": "reciclaje"}).status_code, 200)
        self.assertEqual(self.api.get(self.base + "/calendario", params={"desde": str(week + timedelta(days=1))}).status_code, 422)
        # Administración solo consulta: no opera la bandeja.
        self.assertEqual(self.api.get(self.base).status_code, 403)
