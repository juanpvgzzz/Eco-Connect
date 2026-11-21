from datetime import datetime, timedelta, timezone

import pytest

from backend.app.accounts.models import AccountKind, AccountRole, AdminAccountSummary
from backend.app.accounts.ports import DuplicateNationalId
from backend.app.errors import InvalidInput
from backend.app.accounts.service import (
    AccountAlreadyExists,
    AccountService,
    ForbiddenAction,
    InvalidCredentials,
    InvalidSession,
    TooManyLoginAttempts,
)


class MemoryAccountStore:
    def __init__(self):
        self.accounts = {}
        self.sessions = {}
        self.failures = {}
        self.locked_until = {}

    def find_by_national_id(self, national_id):
        return self.accounts.get(national_id)

    def find_by_id(self, account_id):
        return next((item for item in self.accounts.values() if item.id == account_id), None)

    def create_account(self, account):
        if account.national_id in self.accounts:
            raise DuplicateNationalId
        self.accounts[account.national_id] = account
        return account

    def set_authorization(self, account_id, role, pilot_enabled, collective_id, actor_id=None, worker_id=None):
        account = next(item for item in self.accounts.values() if item.id == account_id)
        account.role = role
        account.pilot_enabled = pilot_enabled
        account.collective_id = collective_id
        return account

    def list_accounts(self, search=None, role=None, limit=50, offset=0):
        result = []
        for account in self.accounts.values():
            if role is not None and account.role is not role:
                continue
            if search and search.lower() not in account.full_name.lower() and search not in account.national_id:
                continue
            result.append(AdminAccountSummary(
                id=account.id, national_id=account.national_id, full_name=account.full_name,
                kind=account.kind, role=account.role,
                pilot_enabled=account.pilot_enabled, collective_id=account.collective_id,
                collective_flow=None, worker_id=account.worker_id, active=True,
            ))
        return result[offset:offset + limit]

    def list_collectives(self):
        return []

    def list_point_rules(self):
        return []

    def collection_report(self, start, end):
        return {"solicitudes": {}, "recogidas_completadas": 0, "puntos_acreditados": 0,
                "desde": start, "hasta": end}

    def is_login_locked(self, national_id, now):
        return self.locked_until.get(national_id, now) > now

    def record_login_failure(self, national_id, now, max_attempts, window, lockout):
        cutoff = now - window
        attempts = [when for when in self.failures.get(national_id, []) if when > cutoff]
        attempts.append(now)
        self.failures[national_id] = attempts
        if len(attempts) >= max_attempts:
            self.locked_until[national_id] = now + lockout

    def clear_login_failures(self, national_id):
        self.failures.pop(national_id, None)
        self.locked_until.pop(national_id, None)

    def save_session(self, session):
        self.sessions[session.token_digest] = session

    def find_session(self, token_digest):
        return self.sessions.get(token_digest)

    def revoke_session(self, token_digest, revoked_at):
        session = self.sessions.get(token_digest)
        if session is not None:
            session.revoked_at = revoked_at


@pytest.fixture
def service_and_store():
    store = MemoryAccountStore()
    return AccountService(store), store


def test_register_normalizes_document_and_never_grants_privileges(service_and_store):
    service, store = service_and_store

    identity = service.register(
        national_id="12.345.678-9",
        full_name="María Pérez",
        address="Calle 1",
        phone="3001234567",
        kind=AccountKind.HOUSEHOLD,
        pin="1234",
    )

    saved = store.find_by_national_id("123456789")
    assert identity.profile.national_id == "123456789"
    assert identity.profile.role is AccountRole.RESIDENT
    assert identity.collective_id is None
    assert saved.pilot_enabled is False
    assert saved.pin_hash != "1234"


@pytest.mark.parametrize("phone", ["+57 300 123 4567", "300-123-4567", "(300) 1234567", "573001234567", "6053456789"])
def test_register_normalizes_colombian_phone(service_and_store, phone):
    service, store = service_and_store

    service.register(
        national_id="555", full_name="  Ana   María  Núñez ", address=" Manzana 12,  Casa 8 ",
        phone=phone, kind=AccountKind.HOUSEHOLD, pin="1234",
    )

    saved = store.find_by_national_id("555")
    assert saved.phone == phone.replace("+57", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")[-10:]
    assert saved.full_name == "Ana María Núñez"
    assert saved.address == "Manzana 12, Casa 8"


@pytest.mark.parametrize("name", ["A", "Ana 123", "Ana_Elena"])
def test_register_rejects_invalid_name(service_and_store, name):
    service, store = service_and_store
    with pytest.raises(InvalidInput):
        service.register(national_id="557", full_name=name, address="Calle 1",
                         phone="3001234567", kind=AccountKind.HOUSEHOLD, pin="1234")
    assert store.find_by_national_id("557") is None


def test_register_rejects_short_address(service_and_store):
    service, store = service_and_store
    with pytest.raises(InvalidInput):
        service.register(national_id="558", full_name="Ana Pérez", address="A",
                         phone="3001234567", kind=AccountKind.HOUSEHOLD, pin="1234")
    assert store.find_by_national_id("558") is None


@pytest.mark.parametrize("phone", ["12345", "2001234567", "30012345678", "300abc4567", "+1 300 123 4567"])
def test_register_rejects_invalid_colombian_phone(service_and_store, phone):
    service, store = service_and_store

    with pytest.raises(InvalidInput):
        service.register(
            national_id="556", full_name="Ana", address="Calle 1", phone=phone,
            kind=AccountKind.HOUSEHOLD, pin="1234",
        )
    assert store.find_by_national_id("556") is None


def test_duplicate_registration_is_controlled(service_and_store):
    service, _ = service_and_store
    values = dict(
        national_id="123456789",
        full_name="María Pérez",
        address="Calle 1",
        phone="3001234567",
        kind=AccountKind.HOUSEHOLD,
        pin="1234",
    )
    service.register(**values)

    with pytest.raises(AccountAlreadyExists):
        service.register(**values)


def test_admin_directory_is_server_authorized(service_and_store):
    service, store = service_and_store
    resident = service.register(
        national_id="123456789", full_name="María Pérez", address="Calle 1",
        phone="3001234567", kind=AccountKind.HOUSEHOLD, pin="1234",
    )
    with pytest.raises(ForbiddenAction):
        service.admin_accounts(actor=resident)

    account = store.find_by_id(resident.id)
    account.role = AccountRole.ADMIN
    admin = account.identity()
    listed = service.admin_accounts(actor=admin, search="María")
    assert len(listed) == 1
    assert listed[0].role is AccountRole.ADMIN


def test_unknown_and_wrong_credentials_have_same_error(service_and_store):
    service, store = service_and_store
    with pytest.raises(InvalidCredentials):
        service.login("123456789", "9999")
    assert len(next(iter(store.failures.values()))) == 1

    service.register(
        national_id="123456789",
        full_name="María Pérez",
        address="Calle 1",
        phone="3001234567",
        kind=AccountKind.HOUSEHOLD,
        pin="1234",
    )
    with pytest.raises(InvalidCredentials):
        service.login("123456789", "9999")
    assert len(next(iter(store.failures.values()))) == 2


def test_unknown_document_attempts_hit_same_lockout_threshold(service_and_store):
    service, _ = service_and_store
    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            service.login("123456789", "9999")
    with pytest.raises(TooManyLoginAttempts):
        service.login("123456789", "9999")


def test_failed_logins_are_limited_and_valid_pin_is_blocked_during_lockout(service_and_store):
    service, _ = service_and_store
    service.register(
        national_id="123456789",
        full_name="María Pérez",
        address="Calle 1",
        phone="3001234567",
        kind=AccountKind.HOUSEHOLD,
        pin="1234",
    )

    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            service.login("123456789", "9999")

    with pytest.raises(TooManyLoginAttempts):
        service.login("123456789", "1234")


def test_login_returns_identity_and_logout_revokes_session(service_and_store):
    service, _ = service_and_store
    service.register(
        national_id="123456789",
        full_name="María Pérez",
        address="Calle 1",
        phone="3001234567",
        kind=AccountKind.BUSINESS,
        pin="1234",
    )

    login = service.login("123456789", "1234")

    assert service.authenticate(login.access_token).id == login.identity.id
    assert login.identity.profile.role is AccountRole.BUSINESS
    service.logout(login.access_token)
    with pytest.raises(InvalidSession):
        service.authenticate(login.access_token)


def test_expired_session_is_rejected(service_and_store):
    service, store = service_and_store
    service.register(
        national_id="123456789",
        full_name="María Pérez",
        address="Calle 1",
        phone="3001234567",
        kind=AccountKind.HOUSEHOLD,
        pin="1234",
    )
    login = service.login("123456789", "1234")
    digest = service._digest_token(login.access_token)
    store.sessions[digest].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    with pytest.raises(InvalidSession):
        service.authenticate(login.access_token)


def test_admin_cannot_enable_pilot_or_business_role_for_household(service_and_store):
    service, store = service_and_store
    user = service.register(
        national_id="123456789",
        full_name="María Pérez",
        address="Calle 1",
        phone="3001234567",
        kind=AccountKind.HOUSEHOLD,
        pin="1234",
    )
    admin = service.register(
        national_id="987654321",
        full_name="Admin",
        address="Centro",
        phone="3000000000",
        kind=AccountKind.HOUSEHOLD,
        pin="1234",
    )
    store.find_by_id(admin.id).role = AccountRole.ADMIN
    admin = store.find_by_id(admin.id).identity()

    with pytest.raises(InvalidInput):
        service.set_authorization(
            actor=admin,
            account_id=user.id,
            role=AccountRole.BUSINESS,
            pilot_enabled=True,
            collective_id=None,
        )
    with pytest.raises(InvalidInput):
        service.set_authorization(
            actor=admin,
            account_id=user.id,
            role=AccountRole.BUSINESS,
            pilot_enabled=False,
            collective_id=None,
        )
    with pytest.raises(InvalidInput):
        service.set_authorization(
            actor=admin,
            account_id=user.id,
            role=AccountRole.LEADER,
            pilot_enabled=False,
            collective_id=None,
        )

    saved = store.find_by_id(user.id)
    assert saved.role is AccountRole.RESIDENT
    assert saved.pilot_enabled is False


def test_non_admin_cannot_change_authorization(service_and_store):
    service, store = service_and_store
    resident = service.register(
        national_id="123456789",
        full_name="María Pérez",
        address="Calle 1",
        phone="3001234567",
        kind=AccountKind.HOUSEHOLD,
        pin="1234",
    )
    target = service.register(
        national_id="987654321",
        full_name="Vecino",
        address="Calle 2",
        phone="3000000000",
        kind=AccountKind.HOUSEHOLD,
        pin="1234",
    )

    with pytest.raises(ForbiddenAction):
        service.set_authorization(
            actor=resident,
            account_id=target.id,
            role=AccountRole.LEADER,
            pilot_enabled=False,
            collective_id="collective-1",
        )

    assert store.find_by_id(target.id).role is AccountRole.RESIDENT
