from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.app.accounts.models import AccountIdentity
from backend.app.community.models import (
    CollectionStatus,
    CollectionRecord,
    CreateCollectionCommand,
    NotificationRecord,
    PointsMovementRecord,
    PointsRecord,
    RedemptionRecord,
    RewardRecord,
)
from backend.app.community.ports import (
    BusinessNotEnabled,
    CommunityCollectionsGateway,
    CommunityPointsGateway,
    InsufficientPoints,
)


BARRANQUILLA = ZoneInfo("America/Bogota")


class CommunityError(Exception):
    """Base class for controlled community-flow errors."""


class CommunityNotFound(CommunityError):
    pass


class CommunityNotEligible(CommunityError):
    pass


class CommunityInsufficientPoints(CommunityError):
    pass


class IntegrationContractError(CommunityError):
    pass


@dataclass(frozen=True, slots=True)
class RedemptionCode:
    code: str
    reward_id: str
    reward_title: str
    expires_at: datetime


class CommunityService:
    def __init__(
        self,
        collections: CommunityCollectionsGateway | None = None,
        points: CommunityPointsGateway | None = None,
    ) -> None:
        self.collections = collections
        self.points = points

    def request_collection(
        self, *, actor: AccountIdentity, request: CreateCollectionCommand
    ) -> CollectionRecord:
        try:
            item = self._collections().create_for_user(actor, request)
        except BusinessNotEnabled:
            raise CommunityNotEligible from None
        return self._owned(item, actor.id)

    def list_collections(self, *, actor: AccountIdentity) -> list[CollectionRecord]:
        return [
            self._owned(item, actor.id)
            for item in self._collections().list_for_user(actor.id)
            if item.owner_id == actor.id
        ]

    def get_collection(self, *, actor: AccountIdentity, request_id: str) -> CollectionRecord:
        item = self._collections().get_for_user(actor.id, request_id)
        if item is None or item.owner_id != actor.id:
            raise CommunityNotFound
        return self._owned(item, actor.id)

    def list_notifications(self, *, actor: AccountIdentity) -> list[NotificationRecord]:
        return [
            item
            for item in self._collections().list_notifications_for_user(actor.id)
            if item.owner_id == actor.id
        ]

    def list_appointments(self, *, actor: AccountIdentity) -> list[AppointmentView]:
        appointments = []
        for item in self._collections().list_appointments_for_user(actor.id):
            if item.owner_id == actor.id and item.status == CollectionStatus.SCHEDULED:
                appointments.append(self._appointment_view(item))
        return appointments

    def points_balance(self, *, actor: AccountIdentity) -> PointsRecord:
        points = self._points().get_points_for_user(actor.id)
        if points.owner_id != actor.id or points.balance < 0:
            raise IntegrationContractError
        return points

    def points_history(self, *, actor: AccountIdentity) -> list[PointsMovementRecord]:
        return [
            item
            for item in self._points().list_movements_for_user(actor.id)
            if item.owner_id == actor.id
        ]

    def rewards(self) -> list[RewardRecord]:
        rewards = self._points().list_rewards()
        if any(reward.cost < 0 for reward in rewards):
            raise IntegrationContractError
        return rewards

    def request_redemption(
        self, *, actor: AccountIdentity, reward_id: str
    ) -> RedemptionCode:
        try:
            result = self._points().request_code_for_user(actor.id, reward_id)
        except InsufficientPoints:
            raise CommunityInsufficientPoints from None
        if result.owner_id != actor.id:
            raise IntegrationContractError
        if result.reward_id != reward_id or not result.code.strip():
            raise IntegrationContractError
        return RedemptionCode(
            code=result.code,
            reward_id=result.reward_id,
            reward_title=result.reward_title,
            expires_at=result.expires_at,
        )

    @staticmethod
    def _owned(item: CollectionRecord, owner_id: str) -> CollectionRecord:
        if item.owner_id != owner_id:
            raise IntegrationContractError
        if item.status == CollectionStatus.SCHEDULED:
            if item.appointment is None:
                raise IntegrationContractError
            CommunityService._appointment_view(item)
        return item

    @staticmethod
    def _appointment_view(item: CollectionRecord) -> "AppointmentView":
        appointment = item.appointment
        if (
            appointment is None
            or not appointment.responsible_name
            or not appointment.responsible_name.strip()
        ):
            raise IntegrationContractError
        return AppointmentView(
            collection_id=item.id,
            status=item.status,
            scheduled_at=CommunityService._barranquilla(appointment.scheduled_at),
            responsible_name=appointment.responsible_name.strip(),
        )

    @staticmethod
    def _barranquilla(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise IntegrationContractError
        return value.astimezone(BARRANQUILLA)

    def _collections(self) -> CommunityCollectionsGateway:
        if self.collections is None:
            raise IntegrationContractError
        return self.collections

    def _points(self) -> CommunityPointsGateway:
        if self.points is None:
            raise IntegrationContractError
        return self.points


@dataclass(frozen=True, slots=True)
class AppointmentView:
    collection_id: str
    status: CollectionStatus
    scheduled_at: datetime
    responsible_name: str
