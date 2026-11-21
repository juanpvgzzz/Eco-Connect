"""Adapt the public community API to the shared collections and points data."""

import secrets
from datetime import datetime, timezone
from uuid import UUID

from backend.app.accounts.models import AccountIdentity, AccountKind
from backend.app.accounts.service import ForbiddenAction
from backend.app.collections.postgres import EVENT_TITLES, PICKUPS
from backend.app.collections.service import Actor, Collections, Problem, Request, local
from backend.app.community.models import (
    AppointmentRecord, CollectionRecord, CollectionStatus, CreateCollectionCommand,
    NotificationRecord, ParticipationMilestone, ParticipationRecord, PointsMovementRecord,
    PointsRecord, RedemptionRecord, RewardRecord, RewardSettings, WasteFlow,
)
from backend.app.community.ports import InsufficientPoints
from backend.app.community.service import CommunityNotFound
from db.connection import open_connection


STATUS = {
    "recibida": CollectionStatus.RECEIVED,
    "revision": CollectionStatus.UNDER_REVIEW,
    "programada": CollectionStatus.SCHEDULED,
    "recolectada": CollectionStatus.COLLECTED,
    "cancelada": CollectionStatus.CANCELLED,
}


FLOWS = {"huerta": WasteFlow.ORGANIC, "reciclaje": WasteFlow.RECYCLABLE}
REWARD_SETTINGS_COLUMNS = """
    id::text, name as title, description, points_cost as cost, stock, active,
    validated_at is not null as validated
"""


def _collection(row):
    appointment = None
    if row["scheduled_at"] and row["responsible_name"]:
        appointment = AppointmentRecord(row["scheduled_at"], row["responsible_name"])
    form = row["form"] or {}
    return CollectionRecord(
        id=str(row["id"]), owner_id=str(row["client_id"]), status=STATUS[row["status"]],
        description=row["notes"] or form.get("material") or "Recolección",
        address=row["address"], created_at=row["created_at"], appointment=appointment,
        flow=FLOWS.get(row["flow"]), material=form.get("material"),
        availability=form.get("disponibilidad"), notes=form.get("observaciones") or row["notes"],
    )


def _notice(row):
    title = EVENT_TITLES.get(row["kind"], "Aviso de recolección")
    snapshot = row["snapshot"] or {}
    message_parts = [row["message"] or title]
    appointment = None
    if snapshot.get("cita") and row["kind"] in ("programada", "reprogramada", "visita_fallida"):
        try:
            appointment = local(datetime.fromisoformat(snapshot["cita"]))
        except (ValueError, TypeError):
            pass
        if snapshot.get("nombre_responsable"):
            message_parts.append(snapshot["nombre_responsable"])
    if row["reason"]:
        message_parts.append(row["reason"])
    return NotificationRecord(
        str(row["id"]), str(row["client_id"]), title, ". ".join(message_parts), row["created_at"],
        scheduled_at=appointment,
    )


class PostgresCommunityCollections:
    def __init__(self, url: str, pilot_id: UUID, service: Collections):
        self.url = url
        self.pilot_id = pilot_id
        self.service = service

    def create_for_user(
        self, actor: AccountIdentity, request: CreateCollectionCommand, idempotency_key: str,
    ) -> CollectionRecord:
        if actor.profile.role not in ("resident", "business"):
            raise Problem(403, "Se requiere perfil de cliente")
        organic = request.flow == WasteFlow.ORGANIC
        # This form does not identify a catalog material. The leader chooses it at close.
        data = Request(
            residuo="organico" if organic else "reciclable",
            material="Orgánico" if organic else "Reciclable",
            contacto=request.contact, direccion=request.address,
            generador="unidad_productiva" if actor.profile.kind == AccountKind.BUSINESS else "hogar",
            disponibilidad=(
                f"{request.preferred_from.astimezone(timezone.utc).isoformat()}/"
                f"{request.preferred_until.astimezone(timezone.utc).isoformat()}"
            ),
            observaciones=request.description,
        )
        row = self.service.create(Actor(UUID(actor.id), "cliente"), idempotency_key, data)
        result = self.get_for_user(actor.id, str(row.id))
        if result is None:
            raise CommunityNotFound
        return result

    def list_for_user(self, owner_id: str) -> list[CollectionRecord]:
        with open_connection(self.url) as conn:
            rows = conn.execute(PICKUPS + """
                where p.pilot_id = %s and p.client_id = %s order by p.created_at desc, p.id
            """, (self.pilot_id, owner_id)).fetchall()
        return [_collection(row) for row in rows]

    def get_for_user(self, owner_id: str, request_id: str) -> CollectionRecord | None:
        try:
            request_uuid = UUID(request_id)
        except ValueError:
            return None
        with open_connection(self.url) as conn:
            row = conn.execute(PICKUPS + """
                where p.pilot_id = %s and p.client_id = %s and p.id = %s
            """, (self.pilot_id, owner_id, request_uuid)).fetchone()
        return _collection(row) if row else None

    def list_notifications_for_user(self, owner_id: str) -> list[NotificationRecord]:
        with open_connection(self.url) as conn:
            rows = conn.execute("""
                select id, client_id, kind, snapshot, reason, created_at, null as message
                from collection_events where pilot_id = %s and client_id = %s
                    and kind <> 'aviso_recolector'  -- comunicación interna con el recolector
                union all
                select n.id, p.client_id, 'legacy', '{}'::jsonb, null, n.created_at, n.message
                from pickup_notices n join pickup_requests p on p.id = n.request_id
                where p.pilot_id = %s and p.client_id = %s
                order by created_at desc, id desc
            """, (self.pilot_id, owner_id, self.pilot_id, owner_id)).fetchall()
        return [_notice(row) for row in rows]

    def history_for_user(self, owner_id: str, request_id: str) -> list[dict] | None:
        try:
            request_uuid = UUID(request_id)
        except ValueError:
            return None
        with open_connection(self.url) as conn:
            owned = conn.execute("""
                select 1 from pickup_requests where id = %s and client_id = %s and pilot_id = %s
            """, (request_uuid, owner_id, self.pilot_id)).fetchone()
            return _history(conn, owner_id, request_uuid) if owned else None

    def list_appointments_for_user(self, owner_id: str) -> list[CollectionRecord]:
        with open_connection(self.url) as conn:
            rows = conn.execute(PICKUPS + """
                where p.pilot_id = %s and p.client_id = %s and p.status = 'programada'
                    and a.id is not null
                order by s.starts_at, p.id
            """, (self.pilot_id, owner_id)).fetchall()
        return [_collection(row) for row in rows]


def _history(conn, owner_id: str, request_uuid: UUID) -> list[dict]:
    rows = conn.execute("""
        select kind, created_at, snapshot, reason from collection_events
        where request_id = %s and client_id = %s and kind <> 'aviso_recolector'
        order by created_at, id
    """, (request_uuid, owner_id)).fetchall()
    events = []
    for row in rows:
        snap, delivery = row["snapshot"] or {}, (row["snapshot"] or {}).get("entrega") or {}
        events.append({
            "event": row["kind"], "at": row["created_at"],
            "scheduled_at": snap.get("cita") if row["kind"] in ("programada", "reprogramada") else None,
            "responsible_name": snap.get("nombre_responsable") if row["kind"] in ("programada", "reprogramada") else None,
            "result": delivery.get("resultado"), "material": delivery.get("material"),
            "kilos": delivery.get("kilos"), "collected_at": delivery.get("recogida_en"),
            "reason": row["reason"],
        })
    points = conn.execute("""
        select m.amount, m.created_at from point_movements m
        join deliveries d on d.id = m.delivery_id
        where d.request_id = %s and m.client_id = %s
    """, (request_uuid, owner_id)).fetchall()
    events += [{"event": "puntos_acreditados", "at": p["created_at"], "points": p["amount"]} for p in points]
    return sorted(events, key=lambda e: e["at"])


class PostgresCommunityPoints:
    def __init__(self, url: str, pilot_id: UUID):
        self.url = url
        self.pilot_id = pilot_id

    def get_points_for_user(self, owner_id: str) -> PointsRecord:
        with open_connection(self.url) as conn:
            row = conn.execute("""
                select points_balance from users where id = %s and pilot_id = %s and active
            """, (owner_id, self.pilot_id)).fetchone()
        if row is None:
            raise CommunityNotFound
        return PointsRecord(owner_id, row["points_balance"])

    def list_movements_for_user(self, owner_id: str) -> list[PointsMovementRecord]:
        with open_connection(self.url) as conn:
            rows = conn.execute("""
                select m.id, m.amount, m.created_at from point_movements m
                join users u on u.id = m.client_id
                where u.pilot_id = %s and u.id = %s and u.active
                order by m.id desc
            """, (self.pilot_id, owner_id)).fetchall()
        return [
            PointsMovementRecord(str(row["id"]), owner_id, row["amount"],
                                 "Entrega" if row["amount"] > 0 else "Canje", row["created_at"])
            for row in rows
        ]

    def list_rewards(self) -> list[RewardRecord]:
        with open_connection(self.url) as conn:
            rows = conn.execute("""
                select id, name, description, points_cost, stock from rewards
                where pilot_id = %s and active and validated_at is not null and stock > 0
                order by name, id
            """, (self.pilot_id,)).fetchall()
        return [RewardRecord(str(row["id"]), row["name"], row["description"], row["points_cost"], row["stock"])
                for row in rows]

    def get_participation_for_user(self, owner_id: str) -> ParticipationRecord:
        with open_connection(self.url) as conn:
            rows = conn.execute("""
                select m.pickups, m.title, r.unlocked_at, (
                    select count(*) from confirmed_pickup_credits c where c.client_id = u.id
                ) as completed
                from users u cross join participation_milestones m
                left join participation_recognitions r on r.client_id = u.id and r.pickups = m.pickups
                where u.id = %s and u.pilot_id = %s and u.active
                order by m.pickups
            """, (owner_id, self.pilot_id)).fetchall()
        if not rows:
            raise CommunityNotFound
        return ParticipationRecord(rows[0]["completed"], [
            ParticipationMilestone(row["pickups"], row["title"], row["unlocked_at"]) for row in rows
        ])

    def list_reward_settings(self) -> list[dict]:
        with open_connection(self.url) as conn:
            return conn.execute(f"""
                select {REWARD_SETTINGS_COLUMNS} from rewards where pilot_id = %s order by name, id
            """, (self.pilot_id,)).fetchall()

    def save_reward_settings(self, actor_id: str, reward_id: UUID | None, settings: RewardSettings) -> dict:
        terms = (settings.title, settings.description, settings.cost)
        with open_connection(self.url) as conn, conn.transaction():
            admin = conn.execute("""
                select 1 from users where id = %s and pilot_id = %s and active and role = 'admin' for share
            """, (actor_id, self.pilot_id)).fetchone()
            if admin is None:
                raise ForbiddenAction
            validated_at = datetime.now(timezone.utc) if settings.validated else None
            validated_by = actor_id if settings.validated else None
            if reward_id is None:
                stock = settings.stock or 0
                reward = conn.execute(f"""
                    insert into rewards
                        (pilot_id, code, name, description, points_cost, stock, active, validated_at, validated_by)
                    values (%s, gen_random_uuid()::text, %s, %s, %s, %s, %s, %s, %s)
                    returning {REWARD_SETTINGS_COLUMNS}
                """, (self.pilot_id, *terms, stock, settings.active, validated_at, validated_by)).fetchone()
                old_stock = None
            else:
                current = conn.execute("""
                    select name, description, points_cost, stock, validated_at, validated_by
                    from rewards where id = %s and pilot_id = %s for update
                """, (reward_id, self.pilot_id)).fetchone()
                if current is None:
                    raise CommunityNotFound
                old_stock = current["stock"]
                stock = old_stock if settings.stock is None else settings.stock
                if settings.validated and current["validated_at"] and terms == (
                    current["name"], current["description"], current["points_cost"],
                ):
                    validated_at, validated_by = current["validated_at"], current["validated_by"]
                reward = conn.execute(f"""
                    update rewards set name = %s, description = %s, points_cost = %s, stock = %s,
                        active = %s, validated_at = %s, validated_by = %s
                    where id = %s and pilot_id = %s returning {REWARD_SETTINGS_COLUMNS}
                """, (*terms, stock, settings.active, validated_at, validated_by, reward_id, self.pilot_id)).fetchone()
            if old_stock != stock:
                conn.execute("""
                    insert into reward_stock_audit (reward_id, pilot_id, author_id, quantity)
                    values (%s, %s, %s, %s)
                """, (reward["id"], self.pilot_id, actor_id, stock))
            return reward

    def request_code_for_user(self, owner_id: str, reward_id: str) -> RedemptionRecord:
        try:
            reward_uuid = UUID(reward_id)
        except ValueError:
            raise CommunityNotFound from None
        with open_connection(self.url) as conn, conn.transaction():
            owner = conn.execute("""
                select points_balance from users where id = %s and pilot_id = %s and active and role = 'cliente'
                for no key update
            """, (owner_id, self.pilot_id)).fetchone()
            if owner is None:
                raise CommunityNotFound
            reward = conn.execute("""
                select name, points_cost, validated_at from rewards
                where id = %s and pilot_id = %s and active and validated_at is not null and stock > 0 for share
            """, (reward_uuid, self.pilot_id)).fetchone()
            if reward is None:
                raise CommunityNotFound
            if owner["points_balance"] < reward["points_cost"]:
                raise InsufficientPoints
            pending = conn.execute("""
                select c.code, c.expires_at from redemption_codes c
                where c.client_id = %s and c.pilot_id = %s and c.reward_id = %s
                    and c.expires_at > clock_timestamp() and c.reward_validated_at = %s
                    and not exists (select 1 from redemptions r where r.code = c.code)
                order by c.expires_at desc, c.code limit 1
            """, (owner_id, self.pilot_id, reward_uuid, reward["validated_at"])).fetchone()
            if pending:
                return RedemptionRecord(owner_id, pending["code"], reward_id, reward["name"], pending["expires_at"])
            code = secrets.token_urlsafe(16)
            expires = conn.execute("""
                insert into redemption_codes (code, client_id, pilot_id, reward_id, expires_at, reward_validated_at)
                values (%s, %s, %s, %s, clock_timestamp() + interval '24 hours', %s) returning expires_at
            """, (code, owner_id, self.pilot_id, reward_uuid, reward["validated_at"])).fetchone()["expires_at"]
        return RedemptionRecord(owner_id, code, reward_id, reward["name"], expires)
