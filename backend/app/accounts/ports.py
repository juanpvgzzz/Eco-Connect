from datetime import datetime, timedelta
from typing import Protocol

from backend.app.accounts.models import AccountRecord, AccountRole, SessionRecord


class DuplicateNationalId(Exception):
    """Raised when the normalized identity document is already registered."""


class AccountStore(Protocol):
    """Persistence contract to be implemented by the shared PostgreSQL adapter."""

    def find_by_national_id(self, national_id: str) -> AccountRecord | None: ...

    def find_by_id(self, account_id: str) -> AccountRecord | None: ...

    def create_account(self, account: AccountRecord) -> AccountRecord: ...

    def set_authorization(
        self,
        account_id: str,
        role: AccountRole,
        pilot_enabled: bool,
        collective_id: str | None,
    ) -> AccountRecord | None: ...

    def is_login_locked(self, attempt_key: str, now: datetime) -> bool: ...

    def record_login_failure(
        self,
        attempt_key: str,
        now: datetime,
        max_attempts: int,
        window: timedelta,
        lockout: timedelta,
    ) -> None: ...

    def clear_login_failures(self, attempt_key: str) -> None: ...

    def save_session(self, session: SessionRecord) -> None: ...

    def find_session(self, token_digest: str) -> SessionRecord | None: ...

    def revoke_session(self, token_digest: str, revoked_at: datetime) -> None: ...
