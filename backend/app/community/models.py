from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CollectionStatus(StrEnum):
    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    SCHEDULED = "scheduled"
    COLLECTED = "collected"
    CANCELLED = "cancelled"


class WasteFlow(StrEnum):
    ORGANIC = "organic"
    RECYCLABLE = "recyclable"


@dataclass(frozen=True, slots=True)
class CreateCollectionCommand:
    description: str
    contact: str
    address: str
    flow: WasteFlow
    preferred_from: datetime
    preferred_until: datetime


@dataclass(frozen=True, slots=True)
class AppointmentRecord:
    scheduled_at: datetime
    responsible_name: str


@dataclass(frozen=True, slots=True)
class CollectionRecord:
    id: str
    owner_id: str
    status: CollectionStatus
    description: str
    address: str
    created_at: datetime
    appointment: AppointmentRecord | None = None
    # Datos reales del formulario para que el vecino vea su propia solicitud.
    flow: WasteFlow | None = None
    material: str | None = None
    availability: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class NotificationRecord:
    id: str
    owner_id: str
    title: str
    message: str
    created_at: datetime
    scheduled_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PointsRecord:
    owner_id: str
    balance: int


@dataclass(frozen=True, slots=True)
class PointsMovementRecord:
    id: str
    owner_id: str
    points: int
    reason: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ParticipationMilestone:
    pickups: int
    title: str
    unlocked_at: datetime | None


@dataclass(frozen=True, slots=True)
class ParticipationRecord:
    completed: int
    milestones: list[ParticipationMilestone]


@dataclass(frozen=True, slots=True)
class RewardRecord:
    id: str
    title: str
    description: str
    cost: int
    stock: int = 0


@dataclass(frozen=True, slots=True)
class RewardSettings:
    title: str
    description: str
    cost: int
    stock: int | None
    active: bool
    validated: bool


@dataclass(frozen=True, slots=True)
class RedemptionRecord:
    owner_id: str
    code: str
    reward_id: str
    reward_title: str
    expires_at: datetime
