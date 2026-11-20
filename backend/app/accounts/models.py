from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AccountKind(StrEnum):
    HOUSEHOLD = "household"
    BUSINESS = "business"


class AccountRole(StrEnum):
    RESIDENT = "resident"
    BUSINESS = "business"
    LEADER = "leader"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class AccountProfile:
    national_id: str
    full_name: str
    address: str
    phone: str
    kind: AccountKind
    role: AccountRole
    pilot_enabled: bool


@dataclass(frozen=True, slots=True)
class AccountIdentity:
    id: str
    profile: AccountProfile
    collective_id: str | None = None


@dataclass(slots=True)
class AccountRecord:
    id: str
    national_id: str
    full_name: str
    address: str
    phone: str
    kind: AccountKind
    pin_hash: str
    role: AccountRole
    pilot_enabled: bool = False
    collective_id: str | None = None

    def identity(self) -> AccountIdentity:
        return AccountIdentity(
            id=self.id,
            profile=AccountProfile(
                national_id=self.national_id,
                full_name=self.full_name,
                address=self.address,
                phone=self.phone,
                kind=self.kind,
                role=self.role,
                pilot_enabled=self.pilot_enabled,
            ),
            collective_id=self.collective_id,
        )


@dataclass(slots=True)
class SessionRecord:
    token_digest: str
    account_id: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
