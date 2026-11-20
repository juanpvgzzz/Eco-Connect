from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
from uuid import uuid4

from pwdlib import PasswordHash

from backend.app.accounts.models import (
    AccountIdentity,
    AccountKind,
    AccountRecord,
    AccountRole,
    SessionRecord,
)
from backend.app.accounts.ports import AccountStore, DuplicateNationalId


class AccountError(Exception):
    """Base class for controlled account use-case errors."""


class AccountAlreadyExists(AccountError):
    pass


class InvalidCredentials(AccountError):
    pass


class TooManyLoginAttempts(AccountError):
    pass


class InvalidSession(AccountError):
    pass


class ForbiddenAction(AccountError):
    pass


class AccountNotFound(AccountError):
    pass


class AccountService:
    def __init__(
        self,
        store: AccountStore,
        *,
        max_attempts: int = 5,
        failure_window: timedelta = timedelta(minutes=15),
        lockout: timedelta = timedelta(minutes=15),
        session_ttl: timedelta = timedelta(hours=12),
    ) -> None:
        self.store = store
        self.max_attempts = max_attempts
        self.failure_window = failure_window
        self.lockout = lockout
        self.session_ttl = session_ttl
        self.password_hash = PasswordHash.recommended()
        self._dummy_hash = self.password_hash.hash(secrets.token_urlsafe(16))

    def register(
        self,
        *,
        national_id: str,
        full_name: str,
        address: str,
        phone: str,
        kind: AccountKind,
        pin: str,
    ) -> AccountIdentity:
        normalized_id = normalize_national_id(national_id)
        validate_pin(pin)
        cleaned = {
            "full_name": full_name.strip(),
            "address": address.strip(),
            "phone": phone.strip(),
        }
        if not all(cleaned.values()):
            raise ValueError("name, address, and phone are required")
        role = AccountRole.BUSINESS if kind is AccountKind.BUSINESS else AccountRole.RESIDENT
        account = AccountRecord(
            id=str(uuid4()),
            national_id=normalized_id,
            full_name=cleaned["full_name"],
            address=cleaned["address"],
            phone=cleaned["phone"],
            kind=kind,
            pin_hash=self.password_hash.hash(pin),
            role=role,
        )
        try:
            saved = self.store.create_account(account)
        except DuplicateNationalId:
            raise AccountAlreadyExists from None
        return saved.identity()

    def login(self, national_id: str, pin: str) -> "LoginResult":
        normalized_id = normalize_national_id(national_id)
        now = datetime.now(timezone.utc)
        if self.store.is_login_locked(normalized_id, now):
            raise TooManyLoginAttempts

        account = self.store.find_by_national_id(normalized_id)
        if account is None:
            self.password_hash.verify(pin, self._dummy_hash)
            raise InvalidCredentials
        if not self.password_hash.verify(pin, account.pin_hash):
            self.store.record_login_failure(
                normalized_id,
                now,
                self.max_attempts,
                self.failure_window,
                self.lockout,
            )
            raise InvalidCredentials

        self.store.clear_login_failures(normalized_id)
        token = secrets.token_urlsafe(32)
        self.store.save_session(
            SessionRecord(
                token_digest=self._digest_token(token),
                account_id=account.id,
                created_at=now,
                expires_at=now + self.session_ttl,
            )
        )
        return LoginResult(access_token=token, identity=account.identity())

    def authenticate(self, token: str) -> AccountIdentity:
        now = datetime.now(timezone.utc)
        session = self.store.find_session(self._digest_token(token))
        if (
            session is None
            or session.revoked_at is not None
            or session.expires_at <= now
        ):
            raise InvalidSession
        account = self.store.find_by_id(session.account_id)
        if account is None:
            raise InvalidSession
        return account.identity()

    def logout(self, token: str) -> None:
        now = datetime.now(timezone.utc)
        session = self.store.find_session(self._digest_token(token))
        if session is not None and session.revoked_at is None:
            self.store.revoke_session(session.token_digest, now)

    def set_authorization(
        self,
        *,
        actor: AccountIdentity,
        account_id: str,
        role: AccountRole,
        pilot_enabled: bool,
    ) -> AccountIdentity:
        if actor.profile.role is not AccountRole.ADMIN:
            raise ForbiddenAction
        current = self.store.find_by_id(account_id)
        if current is None:
            raise AccountNotFound
        if (
            role is AccountRole.BUSINESS and current.kind is not AccountKind.BUSINESS
        ) or (role is AccountRole.RESIDENT and current.kind is not AccountKind.HOUSEHOLD):
            raise ValueError("account role must match its registered kind")
        if pilot_enabled and current.kind is not AccountKind.BUSINESS:
            raise ValueError("only businesses can be enabled for the pilot")
        account = self.store.set_authorization(account_id, role, pilot_enabled)
        if account is None:
            raise AccountNotFound
        return account.identity()

    @staticmethod
    def _digest_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_national_id(value: str) -> str:
    normalized = re.sub(r"[.\-\s]", "", value)
    if not normalized or not re.fullmatch(r"[0-9]{1,20}", normalized):
        raise ValueError("national id must contain only digits and common separators")
    return normalized


def validate_pin(pin: str) -> None:
    if not re.fullmatch(r"[0-9]{4,12}", pin):
        raise ValueError("PIN must contain between 4 and 12 digits")


@dataclass(frozen=True, slots=True)
class LoginResult:
    access_token: str
    identity: AccountIdentity
