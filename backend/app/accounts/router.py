from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.security import HTTPAuthorizationCredentials

from backend.app.accounts.dependencies import (
    bearer_scheme,
    get_account_service,
    get_current_identity,
)
from backend.app.accounts.models import AccountIdentity, AccountRole
from backend.app.accounts.schemas import (
    AccountIdentityResponse,
    AccountAuthorizationResponse,
    AccountActiveRequest,
    AdminAccountResponse,
    AdminPointRuleRequest,
    AdminPointRuleResponse,
    AdminCollectionReportResponse,
    CollectiveResponse,
    AuthorizationRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
)
from backend.app.accounts.service import AccountService


router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post(
    "",
    response_model=AccountIdentityResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_account(
    request: RegisterRequest,
    service: AccountService = Depends(get_account_service),
) -> AccountIdentity:
    return service.register(**request.model_dump())


@router.post("/login", response_model=LoginResponse)
def login(
    request: LoginRequest,
    service: AccountService = Depends(get_account_service),
) -> LoginResponse:
    result = service.login(request.national_id, request.pin)
    return LoginResponse(access_token=result.access_token)


@router.get("/me", response_model=AccountIdentityResponse)
def read_own_profile(
    identity: AccountIdentity = Depends(get_current_identity),
) -> AccountIdentity:
    return identity


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    identity: AccountIdentity = Depends(get_current_identity),
    service: AccountService = Depends(get_account_service),
) -> Response:
    service.logout(credentials.credentials)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/users", response_model=list[AdminAccountResponse])
def list_accounts(
    search: str | None = Query(default=None, max_length=100),
    role: AccountRole | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actor: AccountIdentity = Depends(get_current_identity),
    service: AccountService = Depends(get_account_service),
):
    return service.admin_accounts(actor=actor, search=search, role=role, limit=limit, offset=offset)


@router.get("/admin/collectives", response_model=list[CollectiveResponse])
def list_collectives(
    actor: AccountIdentity = Depends(get_current_identity),
    service: AccountService = Depends(get_account_service),
):
    return service.admin_collectives(actor=actor)


@router.get("/admin/collectives/{collective_id}/members")
def collective_members(
    collective_id: str,
    actor: AccountIdentity = Depends(get_current_identity),
    service: AccountService = Depends(get_account_service),
):
    """Integrantes operativos de un colectivo, para vincular cuentas de recolector."""
    return service.admin_collective_members(actor=actor, collective_id=collective_id)


@router.post("/admin/point-rules", response_model=AdminPointRuleResponse, status_code=status.HTTP_201_CREATED)
def create_point_rule(
    request: AdminPointRuleRequest,
    actor: AccountIdentity = Depends(get_current_identity),
    service: AccountService = Depends(get_account_service),
):
    return service.admin_create_point_rule(
        actor=actor, material_code=request.material_code, material_name=request.material_name,
        points_per_kg=request.points_per_kg, note=request.note,
    )


@router.get("/admin/point-rules", response_model=list[AdminPointRuleResponse])
def list_point_rules(
    actor: AccountIdentity = Depends(get_current_identity),
    service: AccountService = Depends(get_account_service),
):
    return service.admin_point_rules(actor=actor)


@router.get("/admin/reports", response_model=AdminCollectionReportResponse)
def collection_report(
    desde: datetime,
    hasta: datetime,
    actor: AccountIdentity = Depends(get_current_identity),
    service: AccountService = Depends(get_account_service),
):
    return service.admin_collection_report(actor=actor, start=desde, end=hasta)


@router.put(
    "/admin/{account_id}/authorization",
    response_model=AccountAuthorizationResponse,
)
def update_authorization(
    account_id: str,
    request: AuthorizationRequest,
    actor: AccountIdentity = Depends(get_current_identity),
    service: AccountService = Depends(get_account_service),
) -> AccountIdentity:
    return service.set_authorization(
        actor=actor,
        account_id=account_id,
        role=request.role,
        pilot_enabled=request.pilot_enabled,
        collective_id=request.collective_id,
        worker_id=request.worker_id,
    )


@router.patch("/admin/{account_id}/active", response_model=AccountAuthorizationResponse)
def set_account_active(
    account_id: str,
    request: AccountActiveRequest,
    actor: AccountIdentity = Depends(get_current_identity),
    service: AccountService = Depends(get_account_service),
) -> AccountIdentity:
    return service.set_account_active(actor=actor, account_id=account_id, active=request.active)
