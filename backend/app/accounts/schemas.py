from decimal import Decimal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.accounts.models import AccountKind, AccountRole


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    national_id: str = Field(min_length=1, max_length=32)
    full_name: str = Field(min_length=1, max_length=160)
    address: str = Field(min_length=1, max_length=240)
    phone: str = Field(min_length=1, max_length=32)
    kind: AccountKind
    pin: str = Field(pattern=r"^[0-9]{4,12}$")


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    national_id: str = Field(min_length=1, max_length=32)
    pin: str = Field(min_length=1, max_length=128)


class AccountAccessProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    national_id: str
    full_name: str
    kind: AccountKind
    role: AccountRole
    pilot_enabled: bool


class AccountProfileResponse(AccountAccessProfile):
    address: str
    phone: str


class AccountAuthorizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile: AccountAccessProfile
    collective_id: str | None
    worker_id: str | None = None
    collective_flow: str | None = None


class AccountIdentityResponse(AccountAuthorizationResponse):
    profile: AccountProfileResponse


class AdminAccountResponse(BaseModel):
    id: str
    national_id: str
    full_name: str
    kind: AccountKind
    role: AccountRole
    pilot_enabled: bool
    collective_id: str | None
    collective_flow: str | None
    worker_id: str | None
    active: bool


class CollectiveResponse(BaseModel):
    id: str
    flow: str


class AdminPointRuleResponse(BaseModel):
    id: str
    material_code: str
    material_name: str
    points_per_kg: str
    valid_from: datetime
    valid_until: datetime | None
    provisional: bool = True
    note: str | None = None


class AdminPointRuleRequest(BaseModel):
    """Nueva regla vigente desde ahora; reemplaza la anterior del mismo material."""
    model_config = ConfigDict(extra="forbid")

    material_code: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
    material_name: str = Field(min_length=2, max_length=80)
    points_per_kg: Decimal = Field(ge=0, le=10000, max_digits=12, decimal_places=3)
    note: str | None = Field(default=None, max_length=300)


class AdminCollectionReportResponse(BaseModel):
    solicitudes: dict[str, dict[str, int]]
    recogidas_completadas: int
    puntos_acreditados: int
    desde: datetime
    hasta: datetime


class AccountActiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: AccountRole
    pilot_enabled: bool
    collective_id: str | None
    # Solo para recolectores: integrante operativo (field_workers) que usará la cuenta.
    worker_id: str | None = None
