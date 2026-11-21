from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.community.models import CollectionStatus, CreateCollectionCommand, WasteFlow


class CollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=5, max_length=2000)
    contact: str = Field(min_length=3, max_length=40)
    address: str = Field(min_length=5, max_length=240)
    flow: WasteFlow
    preferred_from: datetime
    preferred_until: datetime

    @field_validator("description", "contact", "address", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_availability(self) -> "CollectionRequest":
        for field_name in ("preferred_from", "preferred_until"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("availability times must include a timezone")
        if self.preferred_from >= self.preferred_until:
            raise ValueError("preferred_from must be earlier than preferred_until")
        if self.preferred_from <= datetime.now(timezone.utc):
            raise ValueError("availability must start in the future")
        return self

    def to_command(self) -> CreateCollectionCommand:
        return CreateCollectionCommand(
            description=self.description,
            contact=self.contact,
            address=self.address,
            flow=self.flow,
            preferred_from=self.preferred_from,
            preferred_until=self.preferred_until,
        )


class AppointmentResponse(BaseModel):
    collection_id: str
    status: CollectionStatus
    scheduled_at: datetime
    responsible_name: str


class CollectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: CollectionStatus
    description: str
    address: str
    created_at: datetime
    flow: WasteFlow | None = None
    material: str | None = None
    availability: str | None = None
    notes: str | None = None


class CollectionEventResponse(BaseModel):
    """Evento del historial visible para el vecino (sin datos de otras personas)."""
    event: str
    at: datetime
    scheduled_at: datetime | None = None
    responsible_name: str | None = None
    result: str | None = None
    material: str | None = None
    kilos: str | None = None
    collected_at: datetime | None = None
    points: int | None = None
    reason: str | None = None


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    message: str
    created_at: datetime
    scheduled_at: datetime | None = None


class PointsResponse(BaseModel):
    balance: int = Field(ge=0)


class PointsMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    points: int
    reason: str
    created_at: datetime


class ParticipationMilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pickups: int
    title: str
    unlocked_at: datetime | None


class ParticipationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    completed: int
    milestones: list[ParticipationMilestoneResponse]


class RewardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    cost: int = Field(ge=0)
    stock: int = Field(default=0, ge=0)


class AdminRewardResponse(RewardResponse):
    active: bool
    validated: bool


class RewardWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    cost: int = Field(gt=0, le=2**53 - 1, strict=True)
    stock: int | None = Field(default=None, ge=0, le=2**31 - 1, strict=True)
    active: bool = Field(default=False, strict=True)
    validated: bool = Field(default=False, strict=True)


class RedemptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reward_id: str = Field(min_length=1, max_length=64)


class RedemptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    reward_id: str
    reward_title: str
    expires_at: datetime
