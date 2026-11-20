from typing import Protocol

from backend.app.accounts.models import AccountIdentity
from backend.app.community.models import (
    CollectionRecord,
    CreateCollectionCommand,
    NotificationRecord,
    PointsMovementRecord,
    PointsRecord,
    RedemptionRecord,
    RewardRecord,
)


class BusinessNotEnabled(Exception):
    """The collections module rejects a business outside the pilot."""


class InsufficientPoints(Exception):
    """The points module cannot issue a redemption code for this balance."""


class CommunityCollectionsGateway(Protocol):
    """Adapter contract for Codex 2; every query receives the authenticated owner."""

    def create_for_user(
        self, actor: AccountIdentity, request: CreateCollectionCommand
    ) -> CollectionRecord: ...

    def list_for_user(self, owner_id: str) -> list[CollectionRecord]: ...

    def get_for_user(self, owner_id: str, request_id: str) -> CollectionRecord | None: ...

    def list_notifications_for_user(self, owner_id: str) -> list[NotificationRecord]: ...

    def list_appointments_for_user(self, owner_id: str) -> list[CollectionRecord]: ...


class CommunityPointsGateway(Protocol):
    """Read and code-request contract for Codex 3; it intentionally has no debit call."""

    def get_points_for_user(self, owner_id: str) -> PointsRecord: ...

    def list_movements_for_user(self, owner_id: str) -> list[PointsMovementRecord]: ...

    def list_rewards(self) -> list[RewardRecord]: ...

    def request_code_for_user(self, owner_id: str, reward_id: str) -> RedemptionRecord: ...
