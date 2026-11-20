"""Persistence for API accounts, login throttling, and sessions."""

from datetime import datetime, timedelta
from uuid import UUID

from backend.app.accounts.models import AccountKind, AccountRecord, AccountRole, SessionRecord
from backend.app.accounts.ports import DuplicateNationalId
from backend.app.errors import InvalidInput
from db.connection import open_connection


_DB_ROLE = {
    AccountRole.RESIDENT: "cliente",
    AccountRole.BUSINESS: "cliente",
    AccountRole.LEADER: "lider",
    AccountRole.ADMIN: "admin",
}


def _account(row):
    if row is None:
        return None
    kind = AccountKind(row["kind"])
    role = {
        "cliente": AccountRole.BUSINESS if kind == AccountKind.BUSINESS else AccountRole.RESIDENT,
        "lider": AccountRole.LEADER,
        "admin": AccountRole.ADMIN,
    }[row["role"]]
    return AccountRecord(
        id=str(row["id"]), national_id=row["document_number"], full_name=row["full_name"],
        address=row["address"], phone=row["phone"], kind=kind, pin_hash=row["password_hash"],
        role=role, pilot_enabled=row["pilot_enabled"],
        collective_id=str(row["collective_id"]) if row["collective_id"] else None,
    )


class PostgresAccountStore:
    def __init__(self, url: str, pilot_id: UUID):
        self.url = url
        self.pilot_id = pilot_id

    def find_by_national_id(self, national_id: str) -> AccountRecord | None:
        with open_connection(self.url) as conn:
            return _account(conn.execute("""
                select * from users where document_number = %s and pilot_id = %s and active
            """, (national_id, self.pilot_id)).fetchone())

    def find_by_id(self, account_id: str) -> AccountRecord | None:
        with open_connection(self.url) as conn:
            return _account(conn.execute("""
                select * from users where id::text = %s and pilot_id = %s
                    and active and document_number is not null
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
    ) -> AccountRecord | None:
        collective = None
        with open_connection(self.url) as conn, conn.transaction():
            if collective_id or role == AccountRole.LEADER:
                collective = conn.execute("""
                    select id from collectives where id::text = %s and pilot_id = %s for key share
                """, (collective_id, self.pilot_id)).fetchone()
                if collective is None:
                    raise InvalidInput("Unknown collective for the configured pilot")
            return _account(conn.execute("""
                update users set role = %s, pilot_enabled = %s, collective_id = %s
                where id::text = %s and pilot_id = %s and active and document_number is not null
                returning *
            """, (_DB_ROLE[role], pilot_enabled, collective["id"] if collective else None,
                  account_id, self.pilot_id)).fetchone())

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
