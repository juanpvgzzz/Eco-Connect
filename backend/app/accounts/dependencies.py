from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.accounts.models import AccountIdentity
from backend.app.accounts.service import AccountService, InvalidSession


bearer_scheme = HTTPBearer(auto_error=False)


def get_account_service(request: Request) -> AccountService:
    service = getattr(request.app.state, "account_service", None)
    if service is not None:
        return service
    store = getattr(request.app.state, "account_store", None)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Account persistence is not configured",
        )
    service = AccountService(store)
    request.app.state.account_service = service
    return service


def get_current_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    service: AccountService = Depends(get_account_service),
) -> AccountIdentity:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return service.authenticate(credentials.credentials)
    except InvalidSession:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
