"""Atomic persistence operations; API routers translate DomainError to HTTP responses."""

from decimal import Decimal, InvalidOperation, ROUND_DOWN
from uuid import UUID

from db.connection import open_connection


class DomainError(ValueError):
    """A request cannot be fulfilled in the current business state."""


def _uuid(value: str | UUID) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError) as exc:
        raise DomainError("invalid identifier") from exc


def _items(items: list[dict]) -> list[tuple[UUID, Decimal]]:
    if not isinstance(items, list) or not items:
        raise DomainError("at least one material is required")
    parsed = []
    seen = set()
    for item in items:
        if not isinstance(item, dict) or "material_id" not in item or "weight_kg" not in item:
            raise DomainError("material_id and weight_kg are required")
        material_id = _uuid(item["material_id"])
        try:
            weight = Decimal(str(item["weight_kg"]))
        except (InvalidOperation, ValueError) as exc:
            raise DomainError("invalid weight") from exc
        if not weight.is_finite() or weight <= 0 or weight > 10000 or weight.as_tuple().exponent < -3:
            raise DomainError("weight must be between 0.001 and 10000 kg, to three decimals")
        if material_id in seen:
            raise DomainError("duplicate material")
        seen.add(material_id)
        parsed.append((material_id, weight))
    return parsed


def _authorized_close(conn, actor_id: UUID, field_worker_id: UUID, pilot_id: UUID) -> None:
    actor = conn.execute(
        "select role, active from users where id = %s and pilot_id = %s",
        (actor_id, pilot_id),
    ).fetchone()
    if not actor or actor["role"] != "lider" or not actor["active"]:
        raise DomainError("active pilot leader required")
    worker = conn.execute(
        "select active from field_workers where id = %s and pilot_id = %s",
        (field_worker_id, pilot_id),
    ).fetchone()
    if not worker or not worker["active"]:
        raise DomainError("active field worker required")


def _credit_items(conn, delivery_id: UUID, client_id: UUID,
                  items: list[tuple[UUID, Decimal]]) -> int:
    total = 0
    for material_id, weight in items:
        rule = conn.execute("""
            select r.id, r.points_per_kg from point_rules r
            join materials m on m.id = r.material_id
            where r.material_id = %s and m.active
              and r.valid_from <= now()
              and (r.valid_until is null or r.valid_until > now())
            order by r.valid_from desc, r.id desc limit 1
        """, (material_id,)).fetchone()
        if not rule:
            raise DomainError("material has no current points rule")
        points = int((weight * rule["points_per_kg"]).to_integral_value(rounding=ROUND_DOWN))
        conn.execute("""
            insert into delivery_items
                (delivery_id, material_id, rule_id, weight_kg, points_per_kg, awarded_points)
            values (%s, %s, %s, %s, %s, %s)
        """, (delivery_id, material_id, rule["id"], weight, rule["points_per_kg"], points))
        total += points
    if total <= 0:
        raise DomainError("delivery must earn at least one point")
    conn.execute("""
        insert into point_movements (client_id, delivery_id, amount)
        values (%s, %s, %s)
    """, (client_id, delivery_id, total))
    return total


def close_pickup(database_url: str, request_id: str | UUID, actor_id: str | UUID,
                 field_worker_id: str | UUID, items: list[dict]) -> tuple[UUID, int]:
    """Close a programmed request once; retries return the original delivery and credit."""
    request_id, actor_id, field_worker_id = map(_uuid, (request_id, actor_id, field_worker_id))
    parsed = _items(items)
    with open_connection(database_url) as conn:
        with conn.transaction():
            request = conn.execute("""
                select id, client_id, pilot_id, status from pickup_requests
                where id = %s for update
            """, (request_id,)).fetchone()
            if not request:
                raise DomainError("request does not exist")
            _authorized_close(conn, actor_id, field_worker_id, request["pilot_id"])
            existing = conn.execute("""
                select d.id, pm.amount from deliveries d
                join point_movements pm on pm.delivery_id = d.id
                where d.request_id = %s
            """, (request_id,)).fetchone()
            if existing:
                return existing["id"], existing["amount"]
            if request["status"] != "programada":
                raise DomainError("request must be programmed")
            appointment = conn.execute(
                "select 1 from pickup_appointments where request_id = %s", (request_id,)
            ).fetchone()
            if not appointment:
                raise DomainError("complete appointment required")
            delivery_id = conn.execute("""
                insert into deliveries
                    (kind, request_id, client_id, pilot_id, field_worker_id, closed_by_id)
                values ('pickup', %s, %s, %s, %s, %s) returning id
            """, (request_id, request["client_id"], request["pilot_id"],
                  field_worker_id, actor_id)).fetchone()["id"]
            points = _credit_items(conn, delivery_id, request["client_id"], parsed)
            conn.execute("""
                update pickup_requests set status = 'recolectada', updated_at = now()
                where id = %s
            """, (request_id,))
            conn.execute("""
                insert into request_audit
                    (request_id, pilot_id, actor_id, from_status, to_status)
                values (%s, %s, %s, 'programada', 'recolectada')
            """, (request_id, request["pilot_id"], actor_id))
            return delivery_id, points


def record_direct_delivery(database_url: str, client_id: str | UUID,
                           actor_id: str | UUID, field_worker_id: str | UUID,
                           external_key: str, items: list[dict]) -> tuple[UUID, int]:
    """Credit a direct delivery using a caller-generated stable idempotency key."""
    client_id, actor_id, field_worker_id = map(_uuid, (client_id, actor_id, field_worker_id))
    parsed = _items(items)
    if not external_key or len(external_key) > 200:
        raise DomainError("external_key is required and must be at most 200 characters")
    with open_connection(database_url) as conn:
        with conn.transaction():
            client = conn.execute("""
                select pilot_id, role, active from users where id = %s for update
            """, (client_id,)).fetchone()
            if not client or client["role"] != "cliente" or not client["active"]:
                raise DomainError("active client required")
            _authorized_close(conn, actor_id, field_worker_id, client["pilot_id"])
            existing = conn.execute("""
                select d.id, d.client_id, pm.amount from deliveries d
                join point_movements pm on pm.delivery_id = d.id
                where d.external_key = %s
            """, (external_key,)).fetchone()
            if existing:
                if existing["client_id"] != client_id:
                    raise DomainError("external_key belongs to another client")
                return existing["id"], existing["amount"]
            delivery_id = conn.execute("""
                insert into deliveries
                    (kind, client_id, pilot_id, field_worker_id, closed_by_id, external_key)
                values ('direct', %s, %s, %s, %s, %s) returning id
            """, (client_id, client["pilot_id"], field_worker_id, actor_id,
                  external_key)).fetchone()["id"]
            points = _credit_items(conn, delivery_id, client_id, parsed)
            return delivery_id, points


def confirm_redemption(database_url: str, client_id: str | UUID,
                       reward_id: str | UUID, code: str) -> tuple[UUID, int]:
    """Debit points and stock together; code is the idempotency key."""
    client_id, reward_id = map(_uuid, (client_id, reward_id))
    if not code or len(code) > 100:
        raise DomainError("code is required and must be at most 100 characters")
    with open_connection(database_url) as conn:
        with conn.transaction():
            client = conn.execute("""
                select pilot_id, points_balance, role, active from users
                where id = %s for update
            """, (client_id,)).fetchone()
            if not client or client["role"] != "cliente" or not client["active"]:
                raise DomainError("active client required")
            existing = conn.execute("""
                select id, client_id, reward_id, points_cost from redemptions where code = %s
            """, (code,)).fetchone()
            if existing:
                if existing["client_id"] != client_id or existing["reward_id"] != reward_id:
                    raise DomainError("code already used")
                return existing["id"], existing["points_cost"]
            reward = conn.execute("""
                select points_cost, stock, active from rewards
                where id = %s and pilot_id = %s for update
            """, (reward_id, client["pilot_id"])).fetchone()
            if not reward or not reward["active"] or reward["stock"] < 1:
                raise DomainError("reward unavailable")
            if client["points_balance"] < reward["points_cost"]:
                raise DomainError("insufficient points")
            redemption_id = conn.execute("""
                insert into redemptions
                    (client_id, pilot_id, reward_id, code, points_cost)
                values (%s, %s, %s, %s, %s) returning id
            """, (client_id, client["pilot_id"], reward_id, code,
                  reward["points_cost"])).fetchone()["id"]
            conn.execute("""
                insert into point_movements (client_id, redemption_id, amount)
                values (%s, %s, %s)
            """, (client_id, redemption_id, -reward["points_cost"]))
            return redemption_id, reward["points_cost"]
