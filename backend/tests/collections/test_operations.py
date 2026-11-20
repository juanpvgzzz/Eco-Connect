from contextlib import contextmanager
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.collections.api import router
from backend.app.collections.service import Actor, Collections, Notice


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

    def save(self, row):
        self.rows[row.id] = row

    def event(self, row, kind, author, reason):
        self.events.append((deepcopy(row), kind, author, reason))
        notice = Notice(solicitud_id=row.id, evento=kind, motivo=reason,
                        cita=row.cita, responsable=row.responsable)
        self.saved_notices.append((row.cliente, row.flujo, notice))

    def inbox(self, flow, state):
        return [r for r in self.rows.values() if r.flujo == flow and (not state or r.estado == state)]

    def notices(self, flow):
        return [notice for _, target, notice in self.saved_notices if target == flow]

    def client_notices(self, client):
        return [notice for target, _, notice in self.saved_notices if target == client]

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
            self.assertEqual(self.api.get(self.base, params={"estado": "recibida"}).json(), [row])
            notices = self.api.get(self.base + "/avisos").json()
            self.assertEqual([(n["evento"], n["solicitud_id"]) for n in notices], [("recibida", row["id"])])
        path = self.base + "/" + a["id"]
        self.assertEqual(self.api.get(path + "/historial").status_code, 404)
        self.assertEqual(self.api.post(path + "/cancelar", json={"motivo": "prueba"}).status_code, 404)

    @patch("socket.socket.connect", side_effect=AssertionError("Conexión externa"))
    def test_internal_notices_by_recipient(self, connect):
        path = self.pending()
        appointments = ["2026-11-21T08:00:00-05:00", "2026-11-22T10:00:00-05:00"]
        for at in appointments:
            response = self.api.post(path + "/programar", json={"cita": at, "motivo": "Disponibilidad"})
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

    def test_schedule_failed_visit_cancel(self):
        path = self.pending()
        appointment = {"cita": "2026-11-21T15:00:00Z"}
        self.db.worker = None
        self.assertEqual(self.api.post(path + "/programar", json=appointment).status_code, 409)
        self.assertEqual(len(self.db.events), 1)
        self.db.worker = uuid4()
        row = self.api.post(path + "/programar", json=appointment).json()
        self.assertEqual(row["cita"], "2026-11-21T10:00:00-05:00")
        self.assertEqual(row["responsable"], str(self.db.worker))
        appointment.update(cita="2026-11-22T08:00:00", motivo="Petición del cliente")
        self.assertEqual(self.api.post(path + "/programar", json=appointment).status_code, 200)
        self.assertEqual(self.db.events[-1][3], appointment["motivo"])
        reason = {"motivo": "Nadie en casa"}
        row = self.api.post(path + "/visita-fallida", json=reason).json()
        self.assertEqual(row["estado"], "recibida")
        self.assertIsNone(row["cita"])
        self.assertEqual(self.api.post(path + "/cancelar", json=reason).json()["estado"], "cancelada")
        self.assertFalse(self.db.credits)

    def test_close_rollback_and_retry(self):
        path = self.pending()
        self.api.post(path + "/programar", json={"cita": "2026-11-21T08:00:00"})
        self.db.reject_credit = True
        self.assertEqual(self.api.post(path + "/cerrar", json=self.delivery).status_code, 500)
        self.assertEqual(next(iter(self.db.rows.values())).estado, "programada")
        self.assertEqual(len(self.db.events), 2)
        self.assertFalse(self.db.credits)
        self.db.reject_credit = False
        for _ in range(2):
            row = self.api.post(path + "/cerrar", json=self.delivery).json()
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
