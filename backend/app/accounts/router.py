from fastapi import APIRouter, Depends, Response, status
from fastapi.security import HTTPAuthorizationCredentials

from backend.app.accounts.dependencies import (
    bearer_scheme,
    get_account_service,
    get_current_identity,
)
from backend.app.accounts.models import AccountIdentity
from backend.app.accounts.schemas import (
    AccountIdentityResponse,
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


@router.put(
    "/admin/{account_id}/authorization",
    response_model=AccountIdentityResponse,
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
    )
