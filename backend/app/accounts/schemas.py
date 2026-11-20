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


class AccountProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    national_id: str
    full_name: str
    address: str
    phone: str
    kind: AccountKind
    role: AccountRole
    pilot_enabled: bool


class AccountIdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile: AccountProfileResponse
    collective_id: str | None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: AccountRole
    pilot_enabled: bool
    collective_id: str | None
