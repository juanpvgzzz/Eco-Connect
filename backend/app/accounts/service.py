from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
from uuid import uuid4

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from backend.app.errors import InvalidInput
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
            raise InvalidInput("name, address, and phone are required")
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
        attempt_key = self._attempt_key(normalized_id)
        now = datetime.now(timezone.utc)
        if self.store.is_login_locked(attempt_key, now):
            raise TooManyLoginAttempts

        account = self.store.find_by_national_id(normalized_id)
        valid_pin = self._verify_pin(pin, account.pin_hash if account else self._dummy_hash)
        if account is None or not valid_pin:
            self.store.record_login_failure(
                attempt_key,
                now,
                self.max_attempts,
                self.failure_window,
                self.lockout,
            )
            raise InvalidCredentials

        self.store.clear_login_failures(attempt_key)
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
        collective_id: str | None,
    ) -> AccountIdentity:
        if actor.profile.role is not AccountRole.ADMIN:
            raise ForbiddenAction
        current = self.store.find_by_id(account_id)
        if current is None:
            raise AccountNotFound
        if (
            role is AccountRole.BUSINESS and current.kind is not AccountKind.BUSINESS
        ) or (role is AccountRole.RESIDENT and current.kind is not AccountKind.HOUSEHOLD):
            raise InvalidInput("account role must match its registered kind")
        if pilot_enabled and current.kind is not AccountKind.BUSINESS:
            raise InvalidInput("only businesses can be enabled for the pilot")
        collective_id = collective_id.strip() if collective_id else None
        if role is AccountRole.LEADER and collective_id is None:
            raise InvalidInput("leader profiles must be assigned to a collective")
        account = self.store.set_authorization(
            account_id, role, pilot_enabled, collective_id
        )
        if account is None:
            raise AccountNotFound
        return account.identity()

    def _verify_pin(self, pin: str, stored_hash: str) -> bool:
        try:
            return self.password_hash.verify(pin, stored_hash)
        except UnknownHashError:
            # Imports can contain accounts without an API PIN.
            self.password_hash.verify(pin, self._dummy_hash)
            return False

    @staticmethod
    def _digest_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _attempt_key(national_id: str) -> str:
        return hashlib.sha256(national_id.encode("ascii")).hexdigest()


def normalize_national_id(value: str) -> str:
    normalized = re.sub(r"[.\-\s]", "", value)
    if not normalized or not re.fullmatch(r"[0-9]{1,20}", normalized):
        raise InvalidInput("national id must contain only digits and common separators")
    return normalized


def validate_pin(pin: str) -> None:
    if not re.fullmatch(r"[0-9]{4,12}", pin):
        raise InvalidInput("PIN must contain between 4 and 12 digits")


@dataclass(frozen=True, slots=True)
class LoginResult:
    access_token: str
    identity: AccountIdentity
