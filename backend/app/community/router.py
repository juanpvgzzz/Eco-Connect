from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from backend.app.accounts.dependencies import get_current_identity
from backend.app.accounts.models import AccountIdentity
from backend.app.community.models import RewardSettings
from backend.app.community.ports import CommunityCollectionsGateway, CommunityPointsGateway
from backend.app.community.schemas import (
    AdminRewardResponse,
    CollectionEventResponse,
    AppointmentResponse,
    CollectionRequest,
    CollectionResponse,
    NotificationResponse,
    ParticipationResponse,
    PointsMovementResponse,
    PointsResponse,
    RedemptionRequest,
    RedemptionResponse,
    RewardResponse,
    RewardWrite,
)
from backend.app.community.service import CommunityNotFound, CommunityService


router = APIRouter(prefix="/community", tags=["community"])


def get_collections_service(request: Request) -> CommunityService:
    service = getattr(request.app.state, "collections_service", None)
    if service is not None:
        return service
    collections: CommunityCollectionsGateway | None = getattr(
        request.app.state, "collections_gateway", None
    )
    if collections is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Collections service contract is not configured",
        )
    service = CommunityService(collections=collections)
    request.app.state.collections_service = service
    return service


def get_points_service(request: Request) -> CommunityService:
    service = getattr(request.app.state, "points_service", None)
    if service is not None:
        return service
    points: CommunityPointsGateway | None = getattr(request.app.state, "points_gateway", None)
    if points is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Points service contract is not configured",
        )
    service = CommunityService(points=points)
    request.app.state.points_service = service
    return service


@router.post(
    "/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_collection(
    request: CollectionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_collections_service),
) -> CollectionResponse:
    return service.request_collection(
        actor=actor,
        request=request.to_command(),
        idempotency_key=idempotency_key,
    )


@router.get("/collections", response_model=list[CollectionResponse])
def list_own_collections(
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_collections_service),
) -> list[CollectionResponse]:
    return service.list_collections(actor=actor)


@router.get("/collections/{request_id}/history", response_model=list[CollectionEventResponse])
def get_own_collection_history(
    request_id: str,
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_collections_service),
) -> list[CollectionEventResponse]:
    try:
        return service.collection_history(actor=actor, request_id=request_id)
    except CommunityNotFound:
        raise HTTPException(status_code=404, detail="Collection request not found") from None


@router.get("/collections/{request_id}", response_model=CollectionResponse)
def get_own_collection(
    request_id: str,
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_collections_service),
) -> CollectionResponse:
    try:
        return service.get_collection(actor=actor, request_id=request_id)
    except CommunityNotFound:
        raise HTTPException(status_code=404, detail="Collection request not found") from None


@router.get("/notifications", response_model=list[NotificationResponse])
def list_own_notifications(
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_collections_service),
) -> list[NotificationResponse]:
    return service.list_notifications(actor=actor)


@router.get("/appointments", response_model=list[AppointmentResponse])
def list_own_appointments(
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_collections_service),
) -> list[AppointmentResponse]:
    return service.list_appointments(actor=actor)


@router.get("/points", response_model=PointsResponse)
def own_points_balance(
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_points_service),
) -> PointsResponse:
    return PointsResponse(balance=service.points_balance(actor=actor).balance)


@router.get("/points/movements", response_model=list[PointsMovementResponse])
def own_points_history(
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_points_service),
) -> list[PointsMovementResponse]:
    return service.points_history(actor=actor)


@router.get("/rewards", response_model=list[RewardResponse])
def list_rewards(
    service: CommunityService = Depends(get_points_service),
) -> list[RewardResponse]:
    return service.rewards()


@router.get("/points/participation", response_model=ParticipationResponse)
def own_participation(
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_points_service),
):
    return service.participation(actor=actor)


@router.get("/admin/rewards", response_model=list[AdminRewardResponse])
def admin_rewards(
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_points_service),
):
    return service.reward_settings(actor=actor)


@router.post("/admin/rewards", response_model=AdminRewardResponse, status_code=status.HTTP_201_CREATED)
def create_reward(
    request: RewardWrite,
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_points_service),
):
    return service.configure_reward(actor=actor, reward_id=None, settings=RewardSettings(**request.model_dump()))


@router.put("/admin/rewards/{reward_id}", response_model=AdminRewardResponse)
def update_reward(
    reward_id: UUID,
    request: RewardWrite,
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_points_service),
):
    return service.configure_reward(actor=actor, reward_id=reward_id, settings=RewardSettings(**request.model_dump()))


@router.post(
    "/redemptions",
    response_model=RedemptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_redemption_code(
    request: RedemptionRequest,
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_points_service),
) -> RedemptionResponse:
    return service.request_redemption(actor=actor, reward_id=request.reward_id)
