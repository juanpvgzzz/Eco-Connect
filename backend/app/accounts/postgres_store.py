"""Persistence for API accounts, login throttling, and sessions."""

from datetime import datetime, timedelta
from uuid import UUID

from backend.app.accounts.models import (
    AccountKind, AccountRecord, AccountRole, AdminAccountSummary, AdminPointRule, SessionRecord,
)
from backend.app.accounts.ports import DuplicateNationalId
from backend.app.accounts.service import ForbiddenAction
from backend.app.errors import InvalidInput
from db.connection import open_connection


_DB_ROLE = {
    AccountRole.RESIDENT: "cliente",
    AccountRole.BUSINESS: "cliente",
    AccountRole.LEADER: "lider",
    AccountRole.FIELD_WORKER: "recolector",
    AccountRole.ADMIN: "admin",
}

_ACCOUNT_SELECT = """
    select u.*, fw.id as field_worker_id, c.flow as collective_flow
    from users u
    left join field_workers fw on fw.account_id = u.id and fw.active
    left join collectives c on c.id = u.collective_id and c.pilot_id = u.pilot_id
"""


def _account(row):
    if row is None:
        return None
    kind = AccountKind(row["kind"])
    role = {
        "cliente": AccountRole.BUSINESS if kind == AccountKind.BUSINESS else AccountRole.RESIDENT,
        "lider": AccountRole.LEADER,
        "recolector": AccountRole.FIELD_WORKER,
        "admin": AccountRole.ADMIN,
    }[row["role"]]
    return AccountRecord(
        id=str(row["id"]), national_id=row["document_number"], full_name=row["full_name"],
        address=row["address"], phone=row["phone"], kind=kind, pin_hash=row["password_hash"],
        role=role, pilot_enabled=row["pilot_enabled"],
        collective_id=str(row["collective_id"]) if row["collective_id"] else None,
        worker_id=str(row.get("field_worker_id")) if row.get("field_worker_id") else None,
        collective_flow=row.get("collective_flow"),
    )


class PostgresAccountStore:
    def __init__(self, url: str, pilot_id: UUID):
        self.url = url
        self.pilot_id = pilot_id

    def _lock_authorization(self, conn, actor_id: str | None) -> None:
        conn.execute("select pg_advisory_xact_lock(854226, 2)")
        if actor_id is not None and conn.execute("""
            select 1 from users
            where id = %s and pilot_id = %s and role = 'admin' and active
        """, (UUID(actor_id), self.pilot_id)).fetchone() is None:
            raise ForbiddenAction

    def find_by_national_id(self, national_id: str) -> AccountRecord | None:
        with open_connection(self.url) as conn:
            return _account(conn.execute("""
                """ + _ACCOUNT_SELECT + """
                where u.document_number = %s and u.pilot_id = %s and u.active
            """, (national_id, self.pilot_id)).fetchone())

    def find_by_id(self, account_id: str) -> AccountRecord | None:
        with open_connection(self.url) as conn:
            return _account(conn.execute("""
                """ + _ACCOUNT_SELECT + """
                where u.id::text = %s and u.pilot_id = %s
                    and u.active and u.document_number is not null
            """, (account_id, self.pilot_id)).fetchone())

    def create_account(self, account: AccountRecord) -> AccountRecord:
        with open_connection(self.url) as conn:
            row = conn.execute("""
                insert into users
                    (id, pilot_id, email, document_number, full_name, address, phone, kind,
                     password_hash, role, pilot_enabled)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (document_number) where document_number is not null do nothing
                returning *
            """, (account.id, self.pilot_id, f"{account.id}@ecoconecta.invalid", account.national_id,
                  account.full_name, account.address, account.phone, account.kind, account.pin_hash,
                  _DB_ROLE[account.role], account.pilot_enabled)).fetchone()
        if row is None:
            raise DuplicateNationalId
        return _account(row)

    def set_authorization(
        self, account_id: str, role: AccountRole, pilot_enabled: bool, collective_id: str | None,
        actor_id: str | None = None,
        worker_id: str | None = None,
    ) -> AccountRecord | None:
        collective = None
        with open_connection(self.url) as conn, conn.transaction():
            self._lock_authorization(conn, actor_id)
            current = conn.execute("""
                select * from users where id::text = %s and pilot_id = %s for update
            """, (account_id, self.pilot_id)).fetchone()
            if current is None:
                return None
            new_db_role = _DB_ROLE[role]
            if current["role"] == "admin" and new_db_role != "admin":
                admins = conn.execute("""
                    select count(*) as total from users
                    where pilot_id = %s and role = 'admin' and active
                """, (self.pilot_id,)).fetchone()["total"]
                if admins <= 1:
                    raise InvalidInput("The last active administrator cannot be demoted")
            if collective_id or role is AccountRole.LEADER:
                collective = conn.execute("""
                    select id, flow from collectives
                    where id::text = %s and pilot_id = %s for key share
                """, (collective_id, self.pilot_id)).fetchone()
                if collective is None:
                    raise InvalidInput("Unknown collective for the configured pilot")
            updated = conn.execute("""
                update users set role = %s, pilot_enabled = %s, collective_id = %s
                where id::text = %s and pilot_id = %s and active and document_number is not null
                returning *
            """, (new_db_role, pilot_enabled, collective["id"] if collective else None,
                  account_id, self.pilot_id)).fetchone()
            if updated is None:
                return None
            # Vínculo cuenta ↔ integrante operativo: uno a uno y sin duplicados.
            conn.execute("update field_workers set account_id = null where account_id = %s", (updated["id"],))
            if role is AccountRole.FIELD_WORKER:
                linked = conn.execute("""
                    update field_workers set account_id = %s
                    where id::text = %s and pilot_id = %s and collective_id = %s and active
                      and (account_id is null or account_id = %s)
                    returning id
                """, (updated["id"], worker_id, self.pilot_id, collective["id"], updated["id"])).fetchone()
                if linked is None:
                    raise InvalidInput("The member must be active, belong to the collective and have no other account")

            conn.execute("""
                insert into account_authorization_audit
                    (pilot_id, actor_id, target_id, action, previous_role, new_role,
                     previous_collective_id, new_collective_id)
                values (%s, %s, %s, 'authorization_changed', %s, %s, %s, %s)
            """, (self.pilot_id, UUID(actor_id) if actor_id else None, updated["id"],
                  current["role"], new_db_role, current["collective_id"],
                  collective["id"] if collective else None))
            row = conn.execute(_ACCOUNT_SELECT + " where u.id = %s and u.pilot_id = %s",
                               (updated["id"], self.pilot_id)).fetchone()
            return _account(row)

    def list_accounts(
        self, search: str | None, role: AccountRole | None, limit: int = 50, offset: int = 0,
    ) -> list[AdminAccountSummary]:
        term = f"%{search.strip()}%" if search and search.strip() else None
        # The legacy schema stores residents and businesses under `cliente`;
        # filter by both role and kind so the admin UI does not mix them.
        role_clause = ""
        role_params: tuple[str, ...] = ()
        if role is AccountRole.RESIDENT:
            role_clause, role_params = "and u.role = 'cliente' and u.kind = 'household'", ()
        elif role is AccountRole.BUSINESS:
            role_clause, role_params = "and u.role = 'cliente' and u.kind = 'business'", ()
        elif role is not None:
            role_clause, role_params = "and u.role = %s", (_DB_ROLE[role],)
        with open_connection(self.url) as conn:
            rows = conn.execute("""
                select u.id, u.document_number, u.full_name, u.kind,
                       u.role, u.pilot_enabled, u.collective_id, c.flow as collective_flow,
                       fw.id as field_worker_id, u.active
                from users u
                left join collectives c on c.id = u.collective_id and c.pilot_id = u.pilot_id
                left join field_workers fw on fw.account_id = u.id and fw.active
                where u.pilot_id = %s and u.document_number is not null
            """ + role_clause + """
                  and (%s::text is null or u.full_name ilike %s
                       or u.document_number ilike %s or u.role ilike %s)
                order by u.active desc, u.full_name, u.id limit %s offset %s
            """, (self.pilot_id, *role_params, term, term, term, term, limit, offset)).fetchall()
        return [AdminAccountSummary(
            id=str(row["id"]), national_id=row["document_number"], full_name=row["full_name"],
            kind=AccountKind(row["kind"]),
            role=(AccountRole.BUSINESS if row["kind"] == AccountKind.BUSINESS else AccountRole.RESIDENT)
                if row["role"] == "cliente" else {
                    "lider": AccountRole.LEADER,
                    "recolector": AccountRole.FIELD_WORKER,
                    "admin": AccountRole.ADMIN,
                }[row["role"]],
            pilot_enabled=row["pilot_enabled"],
            collective_id=str(row["collective_id"]) if row["collective_id"] else None,
            collective_flow=row["collective_flow"],
            worker_id=str(row["field_worker_id"]) if row["field_worker_id"] else None,
            active=row["active"],
        ) for row in rows]

    def list_collectives(self) -> list[dict[str, str]]:
        with open_connection(self.url) as conn:
            rows = conn.execute("""
                select id, flow from collectives where pilot_id = %s order by flow, id
            """, (self.pilot_id,)).fetchall()
        return [{"id": str(row["id"]), "flow": row["flow"]} for row in rows]

    def list_collective_members(self, collective_id: str) -> list[dict] | None:
        with open_connection(self.url) as conn:
            exists = conn.execute("select 1 from collectives where id::text = %s and pilot_id = %s",
                                  (collective_id, self.pilot_id)).fetchone()
            if not exists:
                return None
            rows = conn.execute("""
                select id, full_name, active, account_id is not null as linked, account_id
                from field_workers where pilot_id = %s and collective_id::text = %s
                order by active desc, full_name, id
            """, (self.pilot_id, collective_id)).fetchall()
        return [{"id": str(r["id"]), "full_name": r["full_name"], "active": r["active"], "linked": r["linked"],
                 "account_id": str(r["account_id"]) if r["account_id"] else None} for r in rows]

    def list_point_rules(self) -> list[AdminPointRule]:
        with open_connection(self.url) as conn:
            rows = conn.execute("""
                select r.id, m.code, m.name, r.points_per_kg, r.valid_from, r.valid_until,
                       r.provisional, r.note
                from point_rules r join materials m on m.id = r.material_id
                order by m.name, r.valid_from desc, r.id desc
            """).fetchall()
        return [AdminPointRule(str(row["id"]), row["code"], row["name"],
                               str(row["points_per_kg"]), row["valid_from"], row["valid_until"],
                               row["provisional"], row["note"])
                for row in rows]

    def create_point_rule(self, code: str, name: str, points_per_kg, note: str | None,
                          actor_id: str) -> AdminPointRule:
        with open_connection(self.url) as conn, conn.transaction():
            material = conn.execute("""
                insert into materials (code, name) values (%s, %s)
                on conflict (code) do update set name = excluded.name, active = true
                returning id, code, name
            """, (code.strip().upper(), name.strip())).fetchone()
            conn.execute("select id from materials where id = %s for update", (material["id"],))
            # Cierra la regla vigente: el historial de reglas se conserva.
            conn.execute("""
                update point_rules set valid_until = now()
                where material_id = %s and valid_from <= now() and (valid_until is null or valid_until > now())
            """, (material["id"],))
            row = conn.execute("""
                insert into point_rules (material_id, points_per_kg, valid_from, provisional, note, created_by)
                values (%s, %s, now(), true, %s, %s)
                returning id, points_per_kg, valid_from, valid_until, provisional, note
            """, (material["id"], points_per_kg, note, UUID(actor_id))).fetchone()
        return AdminPointRule(str(row["id"]), material["code"], material["name"], str(row["points_per_kg"]),
                              row["valid_from"], row["valid_until"], row["provisional"], row["note"])

    def collection_report(self, start: datetime, end: datetime) -> dict:
        with open_connection(self.url) as conn:
            rows = conn.execute("""
                select flow, status, count(*) as total from pickup_requests
                where pilot_id = %s and created_at >= %s and created_at < %s
                group by flow, status order by flow, status
            """, (self.pilot_id, start, end)).fetchall()
            completed = conn.execute("""
                select count(*) as total from deliveries
                where pilot_id = %s and kind = 'pickup' and closed_at >= %s and closed_at < %s
            """, (self.pilot_id, start, end)).fetchone()["total"]
            points = conn.execute("""
                select coalesce(sum(m.amount), 0) as total from point_movements m
                join users u on u.id = m.client_id
                where u.pilot_id = %s and m.amount > 0 and m.created_at >= %s and m.created_at < %s
            """, (self.pilot_id, start, end)).fetchone()["total"]
        summary = {flow: {state: 0 for state in
                   ("recibida", "revision", "programada", "recolectada", "cancelada")}
                   for flow in ("huerta", "reciclaje")}
        for row in rows:
            if row["flow"] in summary and row["status"] in summary[row["flow"]]:
                summary[row["flow"]][row["status"]] = row["total"]
        return {"solicitudes": summary, "recogidas_completadas": completed,
                "puntos_acreditados": points, "desde": start, "hasta": end}

    def set_account_active(
        self, account_id: str, active: bool, actor_id: str | None = None,
    ) -> AccountRecord | None:
        with open_connection(self.url) as conn, conn.transaction():
            self._lock_authorization(conn, actor_id)
            current = conn.execute("""
                select * from users where id::text = %s and pilot_id = %s for update
            """, (account_id, self.pilot_id)).fetchone()
            if current is None:
                return None
            if current["role"] == "admin" and current["active"] and not active:
                admins = conn.execute("""
                    select count(*) as total from users
                    where pilot_id = %s and role = 'admin' and active
                """, (self.pilot_id,)).fetchone()["total"]
                if admins <= 1:
                    raise InvalidInput("The last active administrator cannot be deactivated")
            updated = conn.execute("""
                update users set active = %s where id = %s and pilot_id = %s returning id
            """, (active, current["id"], self.pilot_id)).fetchone()
            if not active:
                conn.execute("""
                    update account_sessions set revoked_at = now()
                    where account_id = %s and revoked_at is null
                """, (current["id"],))
            conn.execute("""
                insert into account_authorization_audit
                    (pilot_id, actor_id, target_id, action, previous_role, new_role,
                     previous_collective_id, new_collective_id)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (self.pilot_id, UUID(actor_id) if actor_id else None, current["id"],
                  "account_activated" if active else "account_deactivated", current["role"],
                  current["role"], current["collective_id"], current["collective_id"]))
            return _account(conn.execute(_ACCOUNT_SELECT + " where u.id = %s and u.pilot_id = %s",
                                         (updated["id"], self.pilot_id)).fetchone())

    def is_login_locked(self, attempt_key: str, now: datetime) -> bool:
        with open_connection(self.url) as conn:
            return conn.execute("""
                select 1 from account_login_attempts where attempt_key = %s and locked_until > %s
            """, (attempt_key, now)).fetchone() is not None

    def record_login_failure(
        self, attempt_key: str, now: datetime, max_attempts: int, window: timedelta, lockout: timedelta,
    ) -> None:
        with open_connection(self.url) as conn, conn.transaction():
            conn.execute("""
                delete from account_login_attempts
                where attempt_key in (
                    select attempt_key from account_login_attempts
                    where greatest(window_expires_at, locked_until) <= %s
                    order by greatest(window_expires_at, locked_until)
                    limit 100 for update skip locked
                )
            """, (now,))
            conn.execute("""
                insert into account_login_attempts as attempts
                    (attempt_key, failures, window_expires_at, locked_until)
                values (%(key)s, 1, %(expires)s,
                        case when %(max)s = 1 then %(lock)s::timestamptz end)
                on conflict (attempt_key) do update set
                    failures = case when %(now)s >= attempts.window_expires_at
                                    then 1 else attempts.failures + 1 end,
                    window_expires_at = case when %(now)s >= attempts.window_expires_at
                                             then excluded.window_expires_at
                                             else attempts.window_expires_at end,
                    locked_until = case
                        when %(max)s = 1 or (%(now)s < attempts.window_expires_at
                            and attempts.failures + 1 >= %(max)s) then %(lock)s::timestamptz
                    end
                where attempts.locked_until is null or attempts.locked_until <= %(now)s
            """, {"key": attempt_key, "now": now, "expires": now + window,
                  "max": max_attempts, "lock": now + lockout})

    def clear_login_failures(self, attempt_key: str) -> None:
        with open_connection(self.url) as conn:
            conn.execute("delete from account_login_attempts where attempt_key = %s", (attempt_key,))

    def save_session(self, session: SessionRecord) -> None:
        with open_connection(self.url) as conn:
            conn.execute("""
                insert into account_sessions (token_digest, account_id, created_at, expires_at, revoked_at)
                values (%s, %s, %s, %s, %s)
            """, (session.token_digest, session.account_id, session.created_at, session.expires_at,
                  session.revoked_at))

    def find_session(self, token_digest: str) -> SessionRecord | None:
        with open_connection(self.url) as conn:
            row = conn.execute("""
                select s.* from account_sessions s join users u on u.id = s.account_id
                where s.token_digest = %s and u.pilot_id = %s
            """, (token_digest, self.pilot_id)).fetchone()
        if row:
            row["account_id"] = str(row["account_id"])
            return SessionRecord(**row)
        return None

    def revoke_session(self, token_digest: str, revoked_at: datetime) -> None:
        with open_connection(self.url) as conn:
            conn.execute("""
                update account_sessions set revoked_at = %s
                from users where users.id = account_sessions.account_id and users.pilot_id = %s
                  and token_digest = %s and revoked_at is null
            """, (revoked_at, self.pilot_id, token_digest))
