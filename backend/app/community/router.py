from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.app.accounts.dependencies import get_current_identity
from backend.app.accounts.models import AccountIdentity
from backend.app.community.ports import CommunityCollectionsGateway, CommunityPointsGateway
from backend.app.community.schemas import (
    AppointmentResponse,
    CollectionRequest,
    CollectionResponse,
    NotificationResponse,
    PointsMovementResponse,
    PointsResponse,
    RedemptionRequest,
    RedemptionResponse,
    RewardResponse,
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
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_collections_service),
) -> CollectionResponse:
    return service.request_collection(actor=actor, request=request.to_command())


@router.get("/collections", response_model=list[CollectionResponse])
def list_own_collections(
    actor: AccountIdentity = Depends(get_current_identity),
    service: CommunityService = Depends(get_collections_service),
) -> list[CollectionResponse]:
    return service.list_collections(actor=actor)


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
