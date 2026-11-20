from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CollectionStatus(StrEnum):
    RECEIVED = "received"
    SCHEDULED = "scheduled"
    COLLECTED = "collected"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class CreateCollectionCommand:
    description: str
    contact: str
    address: str
    preferred_from: datetime
    preferred_until: datetime


@dataclass(frozen=True, slots=True)
class AppointmentRecord:
    scheduled_at: datetime
    responsible_name: str | None


@dataclass(frozen=True, slots=True)
class CollectionRecord:
    id: str
    owner_id: str
    status: CollectionStatus
    description: str
    address: str
    created_at: datetime
    appointment: AppointmentRecord | None = None


@dataclass(frozen=True, slots=True)
class NotificationRecord:
    id: str
    owner_id: str
    title: str
    message: str
    created_at: datetime


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
class RewardRecord:
    id: str
    title: str
    description: str
    cost: int


@dataclass(frozen=True, slots=True)
class RedemptionRecord:
    owner_id: str
    code: str
    reward_id: str
    reward_title: str
    expires_at: datetime
