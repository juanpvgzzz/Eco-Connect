"""Transactional bridge from collection operations to the shared PostgreSQL tables."""

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from backend.app.collections.service import Actor, CalendarItem, Flow, InboxRecord, Notice, Problem, Record, State
from db.connection import open_connection
from db.operations import DomainError, _authorized_close, _credit_items, confirm_redemption_in_transaction


PICKUPS = """
    select p.*, s.starts_at as scheduled_at, a.leader_id,
        coalesce(a.worker_id, a.leader_id) as responsible_id,
        coalesce(w.full_name, u.full_name) as responsible_name,
        d.api_result, d.closed_by_id
    from pickup_requests p
    left join pickup_appointments a on a.request_id = p.id
    left join pickup_slots s on s.id = a.slot_id
    left join field_workers w on w.id = a.worker_id
    left join users u on u.id = a.leader_id
    left join deliveries d on d.request_id = p.id
"""

EVENT_TITLES = {
    "recibida": "Solicitud recibida",
    "revision": "Solicitud en revisión",
    "programada": "Recolección programada",
    "reprogramada": "Recolección reprogramada",
    "visita_fallida": "Visita fallida. Se requiere una nueva cita",
    "cancelada": "Recolección cancelada",
    "recolectada": "Recolección completada",
    "entrega_directa": "Entrega directa registrada",
    "aviso_recolector": "Aviso al recolector registrado",
}


def _pickup(row):
    return Record(
        id=row["id"], cliente=row["client_id"], flujo=row["flow"], estado=row["status"],
        solicitud=row["form"], cita=row["scheduled_at"], responsable=row["responsible_id"],
        programada_por=row["leader_id"], entrega=row["api_result"], cerrada_por=row["closed_by_id"],
    )


def _calendar(row):
    return CalendarItem(**_pickup(row).model_dump(), nombre_responsable=row["responsible_name"],
                        creada=row["created_at"])


def _direct(row):
    return Record(
        id=row["id"], cliente=row["client_id"], flujo=row["flow"], estado="recolectada",
        entrega=row["api_result"], cerrada_por=row["closed_by_id"],
    )


def _notice(row):
    data = row["snapshot"]
    return Notice(
        solicitud_id=data["id"], evento=row["kind"], cita=data.get("cita"),
        responsable=data.get("responsable"), motivo=row["reason"],
    )


class PostgresCollections:
    def __init__(self, url: str, pilot_id: UUID):
        self.url = url
        self.pilot_id = pilot_id

    @contextmanager
    def transaction(self):
        with open_connection(self.url) as conn, conn.transaction():
            yield CollectionTransaction(conn, self.pilot_id)

    def actor(self, identity):
        account_id = UUID(identity.id)
        if identity.profile.role in ("resident", "business"):
            generator = "unidad_productiva" if identity.profile.kind == "business" else "hogar"
            return Actor(account_id, "cliente", generador=generator)
        if identity.profile.role == "admin":
            return Actor(account_id, "admin")
        if identity.profile.role == "field_worker" and identity.worker_id and identity.collective_id:
            # Vínculo verificado en PostgreSQL: integrante activo, de su colectivo y con esta cuenta.
            with open_connection(self.url) as conn:
                row = conn.execute("""
                    select c.flow, w.id as worker_id from field_workers w
                    join collectives c on c.id = w.collective_id and c.pilot_id = w.pilot_id
                    where w.id = %s and w.account_id = %s and w.pilot_id = %s and w.active and c.id = %s
                """, (identity.worker_id, account_id, self.pilot_id, identity.collective_id)).fetchone()
            if row:
                return Actor(account_id, "recolector", row["flow"], trabajador_id=row["worker_id"])
        if identity.profile.role == "leader" and identity.collective_id:
            with open_connection(self.url) as conn:
                row = conn.execute("""
                    select flow from collectives where id = %s and pilot_id = %s
                """, (identity.collective_id, self.pilot_id)).fetchone()
            if row:
                return Actor(account_id, "lider", row["flow"])
        raise Problem(403, "Perfil sin acceso a recolecciones")


class CollectionTransaction:
    def __init__(self, conn, pilot_id: UUID):
        self.conn = conn
        self.pilot_id = pilot_id
        self.pending: Record | None = None
        self.direct_key: str | None = None

    def pilot(self, client: UUID) -> bool:
        return self.conn.execute("""
            select 1 from users u join pilots p on p.id = u.pilot_id
            where u.id = %s and p.id = %s and p.active and u.active and u.role = 'cliente'
              and u.pilot_enabled  -- RN-08: hogares y unidades productivas habilitados por administración
        """, (client, self.pilot_id)).fetchone() is not None

    def reserve(self, scope: str, owner: UUID, key: str, new: Record) -> tuple[Record, bool]:
        if scope == "directa":
            # Serialize the same logical delivery before the delivery row exists.
            self.conn.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                              (f"directa:{owner}:{key}",))
            existing = self.conn.execute("""
                select * from deliveries where pilot_id = %s and closed_by_id = %s and api_key = %s
            """, (self.pilot_id, owner, key)).fetchone()
            if existing:
                return _direct(existing), False
            self.direct_key = key
            return new, True

        request = new.solicitud
        inserted = self.conn.execute("""
            insert into pickup_requests (id, client_id, pilot_id, address, notes, flow,
                                         idempotency_key, form)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (client_id, idempotency_key) do nothing returning id
        """, (new.id, owner, self.pilot_id, request.direccion, request.observaciones, new.flujo,
              key, Jsonb(request.model_dump(mode="json")))).fetchone()
        if inserted:
            return new, True
        row = self.conn.execute(PICKUPS + """
            where p.client_id = %s and p.pilot_id = %s and p.idempotency_key = %s for update of p
        """, (owner, self.pilot_id, key)).fetchone()
        return _pickup(row), False

    def locked(self, flow: Flow, id: UUID) -> Record | None:
        # Lock first, then read dependent rows using a fresh statement snapshot.
        pickup = self.conn.execute("""
            select id from pickup_requests where id = %s and pilot_id = %s and flow = %s for update
        """, (id, self.pilot_id, flow)).fetchone()
        if pickup:
            return _pickup(self.conn.execute(PICKUPS + " where p.id = %s", (id,)).fetchone())
        direct = self.conn.execute("""
            select * from deliveries where id = %s and pilot_id = %s and flow = %s and kind = 'direct'
        """, (id, self.pilot_id, flow)).fetchone()
        return _direct(direct) if direct else None

    def workers(self, flow: Flow, include_inactive: bool = False) -> list[dict]:
        return self.conn.execute("""
            select w.id, w.full_name, w.active from field_workers w
            join collectives c on c.id = w.collective_id and c.pilot_id = w.pilot_id
            where w.pilot_id = %s and c.flow = %s and (w.active or %s)
            order by w.active desc, w.full_name, w.id
        """, (self.pilot_id, flow, include_inactive)).fetchall()

    def add_worker(self, flow: Flow, name: str) -> dict:
        # Registro operativo sin cuenta de usuario (account_id queda nulo).
        row = self.conn.execute("""
            insert into field_workers (pilot_id, full_name, collective_id)
            select %s, %s, c.id from collectives c where c.pilot_id = %s and c.flow = %s
            returning id, full_name, active
        """, (self.pilot_id, name, self.pilot_id, flow)).fetchone()
        if row is None:
            raise Problem(409, "El colectivo no está configurado")
        return row

    def set_worker_active(self, flow: Flow, worker: UUID, active: bool) -> dict | None:
        return self.conn.execute("""
            update field_workers w set active = %s from collectives c
            where w.id = %s and w.pilot_id = %s and c.id = w.collective_id
              and c.pilot_id = w.pilot_id and c.flow = %s
            returning w.id, w.full_name, w.active
        """, (active, worker, self.pilot_id, flow)).fetchone()

    def materials(self) -> list[dict]:
        return self.conn.execute("""
            select distinct m.code, m.name from materials m
            join point_rules r on r.material_id = m.id
            where m.active and r.valid_from <= now()
              and (r.valid_until is null or r.valid_until > now())
            order by m.name, m.code
        """).fetchall()

    def worker_in_flow(self, flow: Flow, worker: UUID) -> bool:
        return self.conn.execute("""
            select 1 from field_workers w
            join collectives c on c.id = w.collective_id and c.pilot_id = w.pilot_id
            where w.id = %s and w.pilot_id = %s and c.flow = %s and w.active
            for update of w
        """, (worker, self.pilot_id, flow)).fetchone() is not None

    def save(self, row: Record) -> None:
        if row.entrega:
            self.pending = row
            if self.direct_key is not None:
                return
        self.conn.execute("""
            update pickup_requests set status = %s, updated_at = now() where id = %s
        """, (row.estado, row.id))
        if row.estado != "programada":
            if row.estado != "recolectada":
                self.conn.execute("delete from pickup_appointments where request_id = %s", (row.id,))
            return

        slot = self.conn.execute("""
            insert into pickup_slots (pilot_id, collective_id, starts_at, ends_at)
            select %s, id, %s, %s::timestamptz + interval '1 hour'
            from collectives where pilot_id = %s and flow = %s
            on conflict (pilot_id, collective_id, starts_at)
            do update set starts_at = excluded.starts_at returning id, active, ends_at
        """, (self.pilot_id, row.cita, row.cita, self.pilot_id, row.flujo)).fetchone()
        if not slot or not slot["active"]:
            raise Problem(409, "Horario no disponible")
        # schedule() mantiene bloqueada la fila del recolector durante la comprobación
        # y la escritura. Los límites abiertos permiten citas contiguas.
        conflict = self.conn.execute("""
            select 1
            from pickup_appointments a
            join pickup_slots s on s.id = a.slot_id and s.pilot_id = a.pilot_id
            join pickup_requests p on p.id = a.request_id and p.pilot_id = a.pilot_id
            where a.pilot_id = %s and a.worker_id = %s
              and a.request_id <> %s and p.status = 'programada'
              and s.starts_at < %s and s.ends_at > %s
            limit 1
        """, (self.pilot_id, row.responsable, row.id, slot["ends_at"], row.cita)).fetchone()
        if conflict:
            raise Problem(409, "El recolector ya tiene una recogida en ese intervalo")
        try:
            self.conn.execute("""
                insert into pickup_appointments (request_id, pilot_id, slot_id, leader_id, worker_id)
                values (%s, %s, %s, %s, %s)
                on conflict (request_id) do update set
                    slot_id = excluded.slot_id, leader_id = excluded.leader_id,
                    worker_id = excluded.worker_id
            """, (row.id, self.pilot_id, slot["id"], row.programada_por, row.responsable))
        except UniqueViolation as exc:
            if exc.diag.constraint_name != "pickup_appointments_slot_id_key":
                raise
            raise Problem(409, "Horario no disponible") from exc

    def on_duty(self, flow: Flow, at: datetime) -> UUID | None:
        worker = self.conn.execute("""
            select s.worker_id from collection_shifts s
            join collectives c on c.id = s.collective_id
            join field_workers w on w.id = s.worker_id
            where c.pilot_id = %s and c.flow = %s and w.active
              and (w.collective_id is null or w.collective_id = c.id)
              and s.starts_at <= %s and s.ends_at > %s
            order by s.starts_at desc, s.id limit 1
        """, (self.pilot_id, flow, at, at)).fetchone()
        return worker["worker_id"] if worker else None

    def event(self, row: Record, kind: str, author: UUID, reason: str | None) -> None:
        direct = kind == "entrega_directa"
        snapshot = row.model_dump(mode="json")
        if row.cita and row.responsable:
            person = self.conn.execute(
                "select full_name from field_workers where id = %s", (row.responsable,)
            ).fetchone()
            if person:
                snapshot["nombre_responsable"] = person["full_name"]
        if row.entrega and getattr(row.entrega, "recolector", None):
            person = self.conn.execute(
                "select full_name from field_workers where id = %s", (row.entrega.recolector,)
            ).fetchone()
            if person:
                snapshot["nombre_recolector"] = person["full_name"]
        self.conn.execute("""
            insert into collection_events
                (pilot_id, request_id, delivery_id, client_id, flow, author_id, kind, snapshot, reason)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (self.pilot_id, None if direct else row.id, row.id if direct else None,
              row.cliente, row.flujo, author, kind, Jsonb(snapshot), reason))

    def credit(self, delivery_id: UUID, client: UUID, material: str, kilos: Decimal) -> None:
        row = self.pending
        direct = self.direct_key is not None
        # Recogida: quien hizo el trabajo según la coordinadora (por defecto, el asignado).
        worker = self.on_duty(row.flujo, datetime.now(timezone.utc)) if direct else (row.entrega.recolector or row.responsable)
        if worker is None:
            raise Problem(409, "Sin responsable de turno para la entrega")
        item = self.conn.execute("""
            select id from materials where active and (code = %s or id::text = %s)
            order by (code = %s) desc limit 1
        """, (material, material, material)).fetchone()
        if not item:
            raise Problem(422, "Material desconocido")
        try:
            _authorized_close(self.conn, row.cerrada_por, worker, self.pilot_id)
            inserted = self.conn.execute("""
                insert into deliveries (id, kind, request_id, client_id, pilot_id, field_worker_id,
                                        closed_by_id, external_key, flow, api_result, api_key)
                values (coalesce(%s, gen_random_uuid()), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning id
            """, (delivery_id if direct else None, "direct" if direct else "pickup",
                  None if direct else row.id, client, self.pilot_id, worker, row.cerrada_por,
                  f"api:{row.cerrada_por}:{self.direct_key}" if direct else None, row.flujo,
                  Jsonb(row.entrega.model_dump(mode="json")), self.direct_key)
            ).fetchone()
            _credit_items(self.conn, inserted["id"], client, [(item["id"], kilos)])
        except DomainError as exc:
            raise Problem(409, str(exc)) from exc

    def inbox(self, flow: Flow, state: State | None) -> list[Record]:
        rows = self.conn.execute(PICKUPS + """
            where p.pilot_id = %s and p.flow = %s and (%s::text is null or p.status = %s)
            order by p.created_at, p.id
        """, (self.pilot_id, flow, state, state)).fetchall()
        return [
            InboxRecord(**_pickup(row).model_dump(), nombre_responsable=row["responsible_name"])
            for row in rows
        ]

    def locked_assigned(self, worker: UUID, flow: Flow, id: UUID) -> Record | None:
        row = self.conn.execute("""
            select p.id from pickup_requests p
            join pickup_appointments a on a.request_id = p.id and a.pilot_id = p.pilot_id
            where p.id = %s and p.pilot_id = %s and p.flow = %s
              and a.worker_id = %s and p.status in ('programada', 'recolectada')
            for update of p
        """, (id, self.pilot_id, flow, worker)).fetchone()
        if not row:
            return None
        return _pickup(self.conn.execute(PICKUPS + " where p.id = %s", (id,)).fetchone())

    def assigned(self, worker: UUID, flow: Flow) -> list[Record]:
        rows = self.conn.execute(PICKUPS + """
            where p.pilot_id = %s and p.flow = %s and a.worker_id = %s
              and p.status in ('programada', 'recolectada')
            order by s.starts_at nulls last, p.id
        """, (self.pilot_id, flow, worker)).fetchall()
        return [InboxRecord(**_pickup(row).model_dump(), nombre_responsable=row["responsible_name"]) for row in rows]

    def scheduled_between(self, flows, start: datetime, end: datetime) -> list[CalendarItem]:
        # Solo programaciones confirmadas (fecha, hora y responsable) del rango visible.
        rows = self.conn.execute(PICKUPS + """
            where p.pilot_id = %s and p.flow = any(%s)
              and p.status in ('programada', 'recolectada') and a.worker_id is not null
              and s.starts_at >= %s and s.starts_at < %s
            order by s.starts_at, p.id
        """, (self.pilot_id, list(flows), start, end)).fetchall()
        return [_calendar(row) for row in rows]

    def unscheduled(self, flows) -> list[CalendarItem]:
        rows = self.conn.execute(PICKUPS + """
            where p.pilot_id = %s and p.flow = any(%s) and p.status in ('recibida', 'revision')
            order by p.created_at, p.id limit 200
        """, (self.pilot_id, list(flows))).fetchall()
        return [_calendar(row) for row in rows]

    def notices(self, flow: Flow) -> list[Notice]:
        rows = self.conn.execute("""
            select kind, snapshot, reason from collection_events
            where pilot_id = %s and flow = %s order by created_at desc, id desc
        """, (self.pilot_id, flow)).fetchall()
        return [_notice(row) for row in rows]

    def client_notices(self, client: UUID) -> list[Notice]:
        rows = self.conn.execute("""
            select kind, snapshot, reason from collection_events
            where pilot_id = %s and client_id = %s and kind <> 'aviso_recolector'
            order by created_at desc, id desc
        """, (self.pilot_id, client)).fetchall()
        return [_notice(row) for row in rows]

    def history(self, flow: Flow, id: UUID) -> list[dict]:
        return self.conn.execute("""
            select id, kind as evento, snapshot as registro, reason as motivo,
                   author_id as autora, created_at as fecha
            from collection_events where pilot_id = %s and flow = %s
                and (request_id = %s or delivery_id = %s)
            union all
            select null, a.to_status, a.detail, null, a.actor_id, a.created_at
            from request_audit a join pickup_requests p on p.id = a.request_id
            where p.pilot_id = %s and p.flow = %s and p.id = %s
            union all
            select null, 'puntos_acreditados', jsonb_build_object('puntos', m.amount), null, null, m.created_at
            from point_movements m join deliveries d on d.id = m.delivery_id
            where d.pilot_id = %s and d.flow = %s and (d.request_id = %s or d.id = %s)
            order by fecha, id
        """, (self.pilot_id, flow, id, id, self.pilot_id, flow, id, self.pilot_id, flow, id, id)).fetchall()

    def summary(self, flow: Flow, start: datetime, end: datetime) -> dict:
        rows = self.conn.execute("""
            select status, count(*) as total from pickup_requests
            where pilot_id = %s and flow = %s and created_at >= %s and created_at < %s
            group by status
        """, (self.pilot_id, flow, start, end)).fetchall()
        totals = dict.fromkeys(("recibida", "revision", "programada", "recolectada", "cancelada"), 0)
        totals.update((row["status"], row["total"]) for row in rows)
        return {"flujo": flow, "desde": start, "hasta": end, "conteos": totals}

    def stock(self) -> list[dict]:
        return self.conn.execute("""
            select id, code as codigo, name as nombre, stock as cantidad
            from rewards where pilot_id = %s order by name, id
        """, (self.pilot_id,)).fetchall()

    def set_stock(self, reward: UUID, quantity: int, author: UUID) -> dict:
        row = self.conn.execute("""
            update rewards set stock = %s where pilot_id = %s and id = %s
            returning id, stock as cantidad
        """, (quantity, self.pilot_id, reward)).fetchone()
        if row is None:
            raise Problem(404, "Premio desconocido")
        self.conn.execute("""
            insert into reward_stock_audit (reward_id, pilot_id, author_id, quantity)
            values (%s, %s, %s, %s)
        """, (reward, self.pilot_id, author, quantity))
        return row

    def redeem(self, code: str, author: UUID) -> dict:
        issued = self.conn.execute("""
            select * from redemption_codes where code = %s and pilot_id = %s for update
        """, (code, self.pilot_id)).fetchone()
        if not issued:
            raise Problem(404, "Código desconocido")
        # Re-read after locking the code in case another confirmation just committed.
        confirmed = self.conn.execute("""
            select id, points_cost from redemptions where code = %s
                and pilot_id = %s and client_id = %s and reward_id = %s
        """, (code, self.pilot_id, issued["client_id"], issued["reward_id"])).fetchone()
        if confirmed:
            return {"id": confirmed["id"], "codigo": code, "puntos": confirmed["points_cost"]}
        if issued["expires_at"] <= datetime.now(timezone.utc):
            raise Problem(409, "Código vencido")
        if issued["reward_validated_at"] is None:
            raise Problem(409, "El código no corresponde a una recompensa validada")
        try:
            id_, points = confirm_redemption_in_transaction(
                self.conn, issued["client_id"], issued["reward_id"], code,
                validated_at=issued["reward_validated_at"],
            )
        except DomainError as exc:
            raise Problem(409, str(exc)) from exc
        self.conn.execute("""
            update redemptions set confirmed_by = %s where id = %s
        """, (author, id_))
        return {"id": id_, "codigo": code, "puntos": points}
