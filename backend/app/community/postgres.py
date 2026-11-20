"""Adapt the public community API to the shared collections and points data."""

import secrets
from datetime import datetime, timezone
from uuid import UUID

from backend.app.accounts.models import AccountIdentity, AccountKind
from backend.app.collections.postgres import EVENT_TITLES, PICKUPS
from backend.app.collections.service import Actor, Collections, Problem, Request
from backend.app.community.models import (
    AppointmentRecord, CollectionRecord, CollectionStatus, CreateCollectionCommand,
    NotificationRecord, PointsMovementRecord, PointsRecord, RedemptionRecord, RewardRecord,
    WasteFlow,
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


def _collection(row):
    appointment = None
    if row["scheduled_at"] and row["responsible_name"]:
        appointment = AppointmentRecord(row["scheduled_at"], row["responsible_name"])
    return CollectionRecord(
        id=str(row["id"]), owner_id=str(row["client_id"]), status=STATUS[row["status"]],
        description=row["notes"] or (row["form"] or {}).get("material") or "Recolección",
        address=row["address"], created_at=row["created_at"], appointment=appointment,
    )


def _notice(row):
    title = EVENT_TITLES.get(row["kind"], "Aviso de recolección")
    snapshot = row["snapshot"]
    message_parts = [row["message"] or title]
    if snapshot.get("cita") and row["kind"] in ("programada", "reprogramada", "visita_fallida"):
        appointment = datetime.fromisoformat(snapshot["cita"])
        message_parts.append(appointment.strftime("%d/%m/%Y %H:%M"))
        if snapshot.get("nombre_responsable"):
            message_parts.append(snapshot["nombre_responsable"])
    if row["reason"]:
        message_parts.append(row["reason"])
    return NotificationRecord(
        str(row["id"]), str(row["client_id"]), title, ". ".join(message_parts), row["created_at"],
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
                union all
                select n.id, p.client_id, 'legacy', '{}'::jsonb, null, n.created_at, n.message
                from pickup_notices n join pickup_requests p on p.id = n.request_id
                where p.pilot_id = %s and p.client_id = %s
                order by created_at desc, id desc
            """, (self.pilot_id, owner_id, self.pilot_id, owner_id)).fetchall()
        return [_notice(row) for row in rows]

    def list_appointments_for_user(self, owner_id: str) -> list[CollectionRecord]:
        with open_connection(self.url) as conn:
            rows = conn.execute(PICKUPS + """
                where p.pilot_id = %s and p.client_id = %s and p.status = 'programada'
                    and a.id is not null
                order by s.starts_at, p.id
            """, (self.pilot_id, owner_id)).fetchall()
        return [_collection(row) for row in rows]


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
                select id, name, description, points_cost from rewards
                where pilot_id = %s and active and stock > 0 order by name, id
            """, (self.pilot_id,)).fetchall()
        return [RewardRecord(str(row["id"]), row["name"], row["description"], row["points_cost"])
                for row in rows]

    def request_code_for_user(self, owner_id: str, reward_id: str) -> RedemptionRecord:
        try:
            reward_uuid = UUID(reward_id)
        except ValueError:
            raise CommunityNotFound from None
        with open_connection(self.url) as conn, conn.transaction():
            row = conn.execute("""
                select r.name, r.points_cost, u.points_balance from rewards r
                join users u on u.pilot_id = r.pilot_id
                where r.id = %s and u.id = %s and u.pilot_id = %s
                    and r.active and r.stock > 0 and u.active and u.role = 'cliente'
            """, (reward_uuid, owner_id, self.pilot_id)).fetchone()
            if row is None:
                raise CommunityNotFound
            if row["points_balance"] < row["points_cost"]:
                raise InsufficientPoints
            code = secrets.token_urlsafe(16)
            expires = conn.execute("""
                insert into redemption_codes (code, client_id, pilot_id, reward_id, expires_at)
                values (%s, %s, %s, %s, now() + interval '24 hours') returning expires_at
            """, (code, owner_id, self.pilot_id, reward_uuid)).fetchone()["expires_at"]
        return RedemptionRecord(owner_id, code, reward_id, row["name"], expires)
